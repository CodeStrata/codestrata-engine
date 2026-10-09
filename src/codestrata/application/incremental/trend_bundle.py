"""R2-P07 durable five-slot trend artifact bundle.

File-only persistence under ``.codestrata-artifacts/trends/``. Does not rotate
through assessments ``current/previous``. P08 writes comparisons under
``comparisons/`` without mutating snapshot artifacts.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.incremental.source_states import SERIES_SLOT_COUNT
from codestrata.application.incremental.trend_series import (
    PinnedEvaluationProfile,
    TrendSeriesResult,
    TrendSlotRecord,
)
from codestrata.artifacts.layout import (
    ARTIFACT_ROOT_NAME,
    ASSESSMENTS_DIRNAME,
    TRENDS_DIRNAME,
    format_run_timestamp,
    sanitize_repository_slug,
)
from codestrata.artifacts.repository_identity import build_local_repository_artifact_id
from codestrata.reporting.journey_observations import FEED_RELATIVE
from codestrata.repository_auth.read_only_git import ReadOnlyGitError, run_readonly_git

TREND_INDEX_SCHEMA = "codestrata.trend-index.v1"
TREND_INDEX_SCHEMA_VERSION = "1.0.0"
TREND_SLOT_SCHEMA = "codestrata.trend-slot.v1"
TREND_INDEX_FILENAME = "trend-index.json"
TREND_SERIES_FILENAME = "trend-series.json"
TREND_HTML_FILENAME = "five-commit-trend.html"
SLOT_STATUS_FILENAME = "slot.json"
COMPARISON_FILENAME = "comparison.json"
ANALYSIS_RESULT_FILENAME = "analysis-result.json"
STAGING_DIRNAME = ".staging"
SNAPSHOTS_DIRNAME = "snapshots"
COMPARISONS_DIRNAME = "comparisons"
RETENTION_POLICY = "keep_all_series"
RETENTION_NOTE = (
    "Each trend run writes a new series-id. Prior series directories are kept. "
    "Slots are never rotated through assessments current/previous."
)
COMPARISON_PAIRS: tuple[tuple[int, int, str], ...] = (
    (1, 2, "s1-s2"),
    (2, 3, "s2-s3"),
    (3, 4, "s3-s4"),
    (4, 5, "s4-s5"),
    (1, 5, "s1-s5"),
)
SLOT_NAMES = tuple(f"s{index}" for index in range(1, SERIES_SLOT_COUNT + 1))
COMPARISON_NAMES = tuple(name for _, _, name in COMPARISON_PAIRS)


class TrendBundleError(ValueError):
    """Raised when a trend bundle path or identifier is unsafe."""


@dataclass(frozen=True, slots=True)
class TrendBundlePaths:
    root: Path
    repository_id: str
    series_id: str
    index_json: Path
    series_json: Path
    trend_html: Path
    snapshots: Path
    comparisons: Path
    staging: Path

    def slot_directory(self, slot: int) -> Path:
        return self.snapshots / validate_bundle_segment(f"s{slot}", kind="slot")

    def comparison_directory(self, name: str) -> Path:
        return self.comparisons / validate_bundle_segment(name, kind="comparison")


def validate_bundle_segment(value: str, *, kind: str) -> str:
    compact = value.strip()
    if not compact or compact in {".", ".."} or "/" in compact or "\\" in compact:
        raise TrendBundleError(f"unsafe trend {kind}: {value!r}")
    if ".." in compact or compact.startswith(".") and kind != "series_id":
        raise TrendBundleError(f"unsafe trend {kind}: {value!r}")
    if kind == "slot" and compact not in SLOT_NAMES:
        raise TrendBundleError(f"unknown trend slot: {value!r}")
    if kind == "comparison" and compact not in COMPARISON_NAMES:
        raise TrendBundleError(f"unknown trend comparison: {value!r}")
    return compact


def allocate_series_id(parent: Path, *, moment: datetime | None = None) -> str:
    """Allocate a unique series-id that does not replace an existing series."""

    stamp = format_run_timestamp(moment)
    candidate = stamp
    suffix = 2
    while (parent / candidate).exists():
        candidate = f"{stamp}-{suffix}"
        suffix += 1
    return candidate


def repository_trend_id(repository_root: Path) -> str:
    resolved = repository_root.expanduser().resolve()
    return build_local_repository_artifact_id(
        resolved.name,
        collision_seed=str(resolved),
    )


def resolve_series_directory(
    output: Path,
    repository_root: Path,
    *,
    series_id: str | None = None,
) -> Path:
    """Resolve the durable series directory.

    ``.codestrata-artifacts`` or ``trends`` outputs nest ``<repo>/<series>``.
    Any other path is treated as an explicit series directory.
    """

    resolved = output.expanduser().resolve()
    repo_id = repository_trend_id(repository_root)
    if resolved.name == ARTIFACT_ROOT_NAME:
        parent = resolved / TRENDS_DIRNAME / repo_id
        parent.mkdir(parents=True, exist_ok=True)
        return parent / (series_id or allocate_series_id(parent))
    if resolved.name == TRENDS_DIRNAME:
        parent = resolved / repo_id
        parent.mkdir(parents=True, exist_ok=True)
        return parent / (series_id or allocate_series_id(parent))
    return resolved


def create_trend_bundle(
    series_directory: Path,
    *,
    repository_id: str,
    series_id: str,
) -> TrendBundlePaths:
    root = series_directory.expanduser().resolve()
    if root.name in {"current", "previous"} or ASSESSMENTS_DIRNAME in root.parts:
        raise TrendBundleError("trend bundle must not use assessments current/previous")
    snapshots = root / SNAPSHOTS_DIRNAME
    comparisons = root / COMPARISONS_DIRNAME
    staging = root / STAGING_DIRNAME
    snapshots.mkdir(parents=True, exist_ok=True)
    comparisons.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    for name in SLOT_NAMES:
        (snapshots / name).mkdir(parents=True, exist_ok=True)
    for name in COMPARISON_NAMES:
        (comparisons / name).mkdir(parents=True, exist_ok=True)
    return TrendBundlePaths(
        root=root,
        repository_id=validate_bundle_segment(repository_id, kind="repository_id")
        if _is_simple(repository_id)
        else sanitize_repository_slug(repository_id),
        series_id=series_id,
        index_json=root / TREND_INDEX_FILENAME,
        series_json=root / TREND_SERIES_FILENAME,
        trend_html=root / TREND_HTML_FILENAME,
        snapshots=snapshots,
        comparisons=comparisons,
        staging=staging,
    )


def persist_slot(
    bundle: TrendBundlePaths,
    record: TrendSlotRecord,
    profile: PinnedEvaluationProfile,
    *,
    staging_directory: Path | None,
) -> TrendSlotRecord:
    """Copy one slot into ``snapshots/sN`` without deleting sibling slots."""

    destination = bundle.slot_directory(record.slot)
    destination.mkdir(parents=True, exist_ok=True)
    if staging_directory is not None and staging_directory.exists():
        _copy_assessment_artifacts(staging_directory, destination)
    feed_bytes_digest = record.feed_digest or profile.feed_digest
    payload = {
        "schema_name": TREND_SLOT_SCHEMA,
        "slot": record.slot,
        "status": _public_status(record.status),
        "unavailable_reason": record.unavailable_reason,
        "sha": record.sha,
        "source_revision": record.source_revision,
        "git_head": record.git_head,
        "dirty": record.dirty,
        "source_digest": record.source_digest,
        "result_digest": record.result_digest,
        "engine_version": record.engine_version,
        "ruleset_version": profile.ruleset_version,
        "config_digest": record.config_digest,
        "feed_digest": record.feed_digest,
        "feed_bytes_digest": feed_bytes_digest,
        "evaluation_time": record.evaluation_time,
        "limitations": list(record.limitations),
        "file_paths": list(record.file_paths),
        "addressable": True,
    }
    (destination / SLOT_STATUS_FILENAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return replace(record, output_directory=str(destination))


def finalize_trend_bundle(
    bundle: TrendBundlePaths,
    result: TrendSeriesResult,
) -> dict[str, object]:
    """Write comparisons, reserved HTML/JSON, then drop staging."""

    from codestrata.application.incremental.trend_comparisons import write_trend_comparisons

    write_trend_comparisons(bundle, result)
    series_json = result.to_json()
    bundle.series_json.write_text(
        json.dumps(series_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    index = build_trend_index(bundle, result)
    bundle.index_json.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    from codestrata.reporting.engineering_health.trend_report import render_trend_html

    bundle.trend_html.write_text(render_trend_html(bundle), encoding="utf-8")
    cleanup_staging(bundle)
    return index


def build_trend_index(bundle: TrendBundlePaths, result: TrendSeriesResult) -> dict[str, object]:
    available = [slot for slot in result.slots if slot.status == "available"]
    feed_digests = [slot.feed_digest or "" for slot in available]
    feed_identical = bool(available) and len(set(feed_digests)) == 1
    return {
        "schema_name": TREND_INDEX_SCHEMA,
        "schema_version": TREND_INDEX_SCHEMA_VERSION,
        "repository_id": bundle.repository_id,
        "series_id": bundle.series_id,
        "repository_root": str(result.repository_root),
        "head_sha": result.head_sha,
        "head_branch": _checked_out_branch(result.repository_root),
        "dirty_worktree": result.dirty_worktree,
        "dirty_notice": result.dirty_notice,
        "retention": {
            "policy": RETENTION_POLICY,
            "namespace": TRENDS_DIRNAME,
            "rotates_current_previous": False,
            "note": RETENTION_NOTE,
        },
        "profile": {
            "engine_version": result.profile.engine_version,
            "ruleset_version": result.profile.ruleset_version,
            "evaluation_time": _iso(result.profile.evaluation_time),
            "config_digest": result.profile.config_digest,
            "feed_digest": result.profile.feed_digest,
            "feed_bytes_digest": result.profile.feed_digest,
        },
        "feed_bytes_identical_across_available_slots": feed_identical,
        "slots": [_index_slot(bundle, slot) for slot in result.slots],
        "comparisons": [
            {
                "id": name,
                "base_slot": left,
                "candidate_slot": right,
                "directory": str(bundle.comparison_directory(name)),
                "status": _comparison_status(bundle, result, left, right, name),
            }
            for left, right, name in COMPARISON_PAIRS
        ],
        "trend_html": str(bundle.trend_html),
        "trend_json": str(bundle.index_json),
        "series_digest": result.series_digest,
    }


def _checked_out_branch(repository_root: Path) -> str | None:
    """Record the checked-out branch name. Detached HEAD stays unknown."""

    try:
        name = run_readonly_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repository_root,
        ).strip()
    except (OSError, ReadOnlyGitError):
        return None
    if not name or name == "HEAD":
        return None
    return name


def hash_feed_bytes(payload: bytes | None) -> str:
    if payload is None:
        return ""
    return hashlib.sha256(payload).hexdigest()


def hash_feed_file(root: Path) -> str:
    path = root / FEED_RELATIVE
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cleanup_staging(bundle: TrendBundlePaths) -> None:
    if bundle.staging.exists():
        shutil.rmtree(bundle.staging, ignore_errors=True)


def _copy_assessment_artifacts(source: Path, destination: Path) -> None:
    current_slots = [path for path in source.rglob("current") if path.is_dir()]
    origin = current_slots[0] if current_slots else source
    for path in origin.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(origin)
        if any(part in {"current", "previous"} for part in relative.parts):
            continue
        target = destination / relative
        if not _is_within(target, destination):
            raise TrendBundleError(f"refusing to write outside slot: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _comparison_status(
    bundle: TrendBundlePaths,
    result: TrendSeriesResult,
    left: int,
    right: int,
    name: str,
) -> str:
    path = bundle.comparison_directory(name) / COMPARISON_FILENAME
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        status = payload.get("status") if isinstance(payload, dict) else None
        if isinstance(status, str) and status:
            return status
    by_slot = {slot.slot: slot for slot in result.slots}
    base = by_slot[left]
    candidate = by_slot[right]
    if base.status != "available" or candidate.status != "available":
        return "unavailable"
    return "not_computable"


def _index_slot(bundle: TrendBundlePaths, slot: TrendSlotRecord) -> dict[str, object]:
    return {
        "slot": slot.slot,
        "name": f"s{slot.slot}",
        "status": _public_status(slot.status),
        "unavailable_reason": slot.unavailable_reason,
        "sha": slot.sha,
        "source_revision": slot.source_revision,
        "engine_version": slot.engine_version,
        "config_digest": slot.config_digest,
        "feed_digest": slot.feed_digest,
        "feed_bytes_digest": slot.feed_digest,
        "source_digest": slot.source_digest,
        "result_digest": slot.result_digest,
        "directory": str(bundle.slot_directory(slot.slot)),
        "addressable": True,
    }


def _public_status(status: str) -> str:
    if status == "unavailable":
        return "UNKNOWN"
    if status == "failed":
        return "failed"
    return status


def _is_simple(value: str) -> bool:
    try:
        validate_bundle_segment(value, kind="repository_id")
    except TrendBundleError:
        return False
    return True


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value
