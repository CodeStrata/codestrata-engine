"""E05.1 inventory service: classify, pin depth, observe manifests and CI."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from codestrata.application.evidence.inventory.catalog import build_extractor_depth_pin
from codestrata.application.evidence.inventory.ci import observe_ci
from codestrata.application.evidence.inventory.classification import InventoryPrimaryClassifier
from codestrata.application.evidence.inventory.manifests import observe_manifests
from codestrata.application.evidence.inventory.models import (
    ExtractorDepthPin,
    FileClassificationRecord,
    RepositoryInventorySnapshot,
)
from codestrata.application.evidence.inventory.walk import (
    DEFAULT_MAX_FILE_BYTES,
    _metric,
    walk_repository,
)


class ExtractorInventoryService:
    """Early discovery. Does not require the YAML rule runtime."""

    def __init__(self, classifier: InventoryPrimaryClassifier | None = None) -> None:
        self._classifier = classifier or InventoryPrimaryClassifier()

    def pin(self) -> ExtractorDepthPin:
        return build_extractor_depth_pin()

    def inspect_tree(
        self,
        repository_root: Path,
        *,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> RepositoryInventorySnapshot:
        walked = walk_repository(
            repository_root,
            classifier=self._classifier,
            max_file_bytes=max_file_bytes,
        )
        texts = _safe_texts(repository_root, walked.files)
        paths = tuple(
            item.relative_path for item in walked.files if not item.relative_path.endswith("/")
        )
        return RepositoryInventorySnapshot(
            files=walked.files,
            metric=walked.metric,
            manifests=observe_manifests(paths, texts),
            ci=observe_ci(paths, texts),
            executed_repository_code=False,
        )

    def inspect_memory(
        self,
        *,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
    ) -> RepositoryInventorySnapshot:
        """Classify supplied paths without walking a real tree (unit tests)."""

        records: list[FileClassificationRecord] = []
        for path in relative_paths:
            text = file_texts.get(path)
            unreadable = text is None
            data: bytes | None = None
            if text is not None:
                data = text.encode("utf-8")
            binary = bool(data is not None and b"\x00" in data)
            primary = self._classifier.classify(path, binary=binary, unreadable=unreadable)
            language = self._classifier.detect_language(path)
            structural = self._classifier.structural_language(path)
            digest = hashlib.sha256(data).hexdigest() if data is not None else ""
            records.append(
                FileClassificationRecord(
                    relative_path=path.replace("\\", "/"),
                    primary_class=primary,
                    language=language,
                    content_digest=digest,
                    ignore_reason="unreadable" if unreadable else None,
                    manifest_location=self._classifier.manifest_location(path),
                    structural_language=structural,
                    detected=language is not None,
                    structurally_supported=structural is not None
                    and primary.value in {"source", "test"},
                    unread_reason="unreadable" if unreadable else None,
                )
            )
        ordered = tuple(sorted(records, key=lambda item: item.relative_path))
        return RepositoryInventorySnapshot(
            files=ordered,
            metric=_metric(ordered),
            manifests=observe_manifests(relative_paths, file_texts),
            ci=observe_ci(relative_paths, file_texts),
            executed_repository_code=False,
        )


def _safe_texts(root: Path, files: Sequence[FileClassificationRecord]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in files:
        if item.relative_path.endswith("/"):
            continue
        if item.primary_class.value == "binary":
            continue
        if item.ignore_reason in {"symlink-escape", "oversize"}:
            continue
        path = root / item.relative_path
        try:
            texts[item.relative_path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return texts
