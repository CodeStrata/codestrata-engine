"""Safe repository walk for inventory. Never executes discovered files."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from codestrata.application.evidence.inventory.classification import (
    INVENTORY_PRUNE_DIR_NAMES,
    InventoryPrimaryClassifier,
    ignore_reason_for_path,
    is_binary_bytes,
    is_binary_path,
    normalize_relative_path,
)
from codestrata.application.evidence.inventory.models import (
    CLASSIFIER_VERSION,
    ClassificationCounts,
    ClassificationMetric,
    FileClassificationRecord,
    InventoryMetricStatus,
)
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass

ByteReader = Callable[[Path], bytes]

DEFAULT_MAX_FILE_BYTES = 1_048_576

_PRUNE_DIR_NAMES = INVENTORY_PRUNE_DIR_NAMES
_ELIGIBLE_CLASSES = frozenset({InventoryPrimaryClass.SOURCE, InventoryPrimaryClass.TEST})


@dataclass(frozen=True, slots=True)
class WalkResult:
    files: tuple[FileClassificationRecord, ...]
    metric: ClassificationMetric
    symlink_escapes: tuple[str, ...]
    executed_repository_code: bool = False


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_escape(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        return True
    return False


def walk_repository(
    repository_root: Path,
    *,
    classifier: InventoryPrimaryClassifier | None = None,
    read_bytes: ByteReader | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> WalkResult:
    """Inventory files under ``repository_root`` without executing them.

    Directory and file symlinks that resolve outside the root are recorded as
    unknown with ignore reason ``symlink-escape`` and are not followed.
    """

    root = repository_root.expanduser().resolve()
    classifier = classifier or InventoryPrimaryClassifier()
    reader = read_bytes or (lambda path: path.read_bytes())
    records: list[FileClassificationRecord] = []
    escapes: list[str] = []

    if not root.is_dir():
        metric = _metric(records)
        return WalkResult(files=(), metric=metric, symlink_escapes=())

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in sorted(dirnames):
            child = current / name
            relative_dir = _relative(root, child)
            if child.is_symlink():
                if _is_escape(root, child):
                    escapes.append(relative_dir)
                    records.append(
                        _record(
                            relative_dir.rstrip("/") + "/",
                            classifier,
                            data=None,
                            ignore_reason="symlink-escape",
                            unreadable=True,
                        )
                    )
                    continue
                # In-repo directory symlink: do not follow (os.walk followlinks=False).
                continue
            if name in _PRUNE_DIR_NAMES:
                records.append(
                    _record(
                        relative_dir.rstrip("/") + "/",
                        classifier,
                        data=None,
                        ignore_reason=f"default-exclude:{name}",
                        unreadable=True,
                    )
                )
                continue
            kept.append(name)
        dirnames[:] = kept

        for name in sorted(filenames):
            path = current / name
            relative = _relative(root, path)
            if path.is_symlink():
                if _is_escape(root, path):
                    escapes.append(relative)
                    records.append(
                        _record(
                            relative,
                            classifier,
                            data=None,
                            ignore_reason="symlink-escape",
                            unreadable=True,
                        )
                    )
                continue
            if not path.is_file():
                continue
            ignore = ignore_reason_for_path(relative)
            try:
                size = path.stat().st_size
            except OSError:
                records.append(
                    _record(
                        relative,
                        classifier,
                        data=None,
                        ignore_reason=ignore or "unreadable",
                        unreadable=True,
                    )
                )
                continue
            if size > max_file_bytes:
                records.append(
                    _record(
                        relative,
                        classifier,
                        data=None,
                        ignore_reason="oversize",
                        unreadable=False,
                        unread_reason="oversize",
                    )
                )
                continue
            try:
                data = reader(path)
            except OSError:
                records.append(
                    _record(
                        relative,
                        classifier,
                        data=None,
                        ignore_reason=ignore or "unreadable",
                        unreadable=True,
                    )
                )
                continue
            records.append(
                _record(
                    relative,
                    classifier,
                    data=data,
                    ignore_reason=ignore,
                    unreadable=False,
                )
            )

    ordered = tuple(sorted(records, key=lambda item: item.relative_path))
    return WalkResult(
        files=ordered,
        metric=_metric(ordered),
        symlink_escapes=tuple(sorted(set(escapes))),
        executed_repository_code=False,
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return normalize_relative_path(str(path))


def _record(
    relative_path: str,
    classifier: InventoryPrimaryClassifier,
    *,
    data: bytes | None,
    ignore_reason: str | None,
    unreadable: bool,
    unread_reason: str | None = None,
) -> FileClassificationRecord:
    binary = False
    digest = ""
    if unreadable and data is None:
        unread_reason = unread_reason or ignore_reason or "unreadable"
    elif data is not None:
        binary = is_binary_bytes(data) or is_binary_path(relative_path)
        digest = _digest(data)
    primary = classifier.classify(
        relative_path, binary=binary, unreadable=unreadable and data is None
    )
    language = classifier.detect_language(relative_path)
    structural = classifier.structural_language(relative_path)
    detected = language is not None
    blocked = ignore_reason in {"oversize", "symlink-escape"} or unread_reason == "oversize"
    structurally_supported = structural is not None and primary in _ELIGIBLE_CLASSES and not blocked
    return FileClassificationRecord(
        relative_path=normalize_relative_path(relative_path),
        primary_class=primary,
        language=language,
        content_digest=digest,
        classifier_version=CLASSIFIER_VERSION,
        ignore_reason=ignore_reason,
        manifest_location=classifier.manifest_location(relative_path),
        structural_language=structural,
        detected=detected,
        structurally_supported=structurally_supported,
        unread_reason=unread_reason,
    )


def _metric(
    records: tuple[FileClassificationRecord, ...] | list[FileClassificationRecord],
) -> ClassificationMetric:
    counts = {item.value: 0 for item in InventoryPrimaryClass}
    ignored = 0
    eligible = 0
    supported = 0
    for record in records:
        counts[record.primary_class.value] += 1
        if record.ignore_reason:
            ignored += 1
            continue
        if record.unread_reason:
            continue
        if record.primary_class in _ELIGIBLE_CLASSES:
            eligible += 1
            if record.structurally_supported:
                supported += 1
    class_counts = ClassificationCounts(
        source=counts["source"],
        test=counts["test"],
        config=counts["config"],
        infra=counts["infra"],
        docs=counts["docs"],
        generated=counts["generated"],
        vendor=counts["vendor"],
        binary=counts["binary"],
        unknown=counts["unknown"],
    )
    if eligible == 0:
        return ClassificationMetric(
            status=InventoryMetricStatus.NOT_APPLICABLE,
            class_counts=class_counts,
            eligible_files=0,
            supported_eligible_files=0,
            numerator=0,
            denominator=0,
            ratio=None,
            ignored_in_inventory=ignored,
        )
    ratio = supported / eligible
    return ClassificationMetric(
        status=InventoryMetricStatus.OBSERVED,
        class_counts=class_counts,
        eligible_files=eligible,
        supported_eligible_files=supported,
        numerator=supported,
        denominator=eligible,
        ratio=f"{ratio:.6f}",
        ignored_in_inventory=ignored,
    )
