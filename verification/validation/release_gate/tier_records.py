"""Per-repository tier execution records for E15.3 / G50 (M33).

A record is written by ``verification.validation.release_gate.tier_execute``
after the installed Engine assesses one pinned repository. The release gate
reads these records instead of trusting pin identity. A record is bound to the
exact Engine source bytes that were assessed through ``source_tree_digest``;
a later source change makes the record stale and the tier unexecuted again.
Docs-only commits do not change that digest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from verification.validation.models import CheckStatus, CorpusTier

RESULTS_DIRNAME = "results"
SUMMARY_NAME = "summary.json"
RECORD_SCHEMA = "codestrata.m33.tier-record.v1"
SUMMARY_SCHEMA = "codestrata.m33.tier-summary.v1"

# Files whose bytes decide whether an assessment record still describes HEAD.
_SOURCE_ROOTS = ("src/codestrata",)
_SOURCE_FILES = (
    "pyproject.toml",
    "MANIFEST.in",
    "verification/validation/corpus/dogfood.yaml",
    "verification/validation/corpus/external-large.yaml",
)
_SKIP_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
_SKIP_SUFFIXES = (".pyc", ".pyo")

# M33 file-count buckets. Budgets are published per bucket only from measured runs.
BUCKET_LE_10K = "le_10k_files"
BUCKET_LE_100K = "le_100k_files"
BUCKET_GT_100K = "gt_100k_files"


def default_results_dir(engine_root: Path) -> Path:
    return engine_root / "verification" / "validation" / "corpus" / RESULTS_DIRNAME


def bucket_for_files(eligible_files: int | None) -> str:
    if eligible_files is None:
        return "unknown"
    if eligible_files <= 10_000:
        return BUCKET_LE_10K
    if eligible_files <= 100_000:
        return BUCKET_LE_100K
    return BUCKET_GT_100K


def source_tree_digest(engine_root: Path) -> str:
    """SHA-256 over the Engine source files that reach the wheel plus the corpus pins."""

    parts: list[bytes] = []
    for rel in _SOURCE_FILES:
        path = engine_root / rel
        if path.is_file():
            parts.append(_entry(rel, path))
    for root_rel in _SOURCE_ROOTS:
        root = engine_root / root_rel
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in _SKIP_DIR_NAMES for part in path.relative_to(engine_root).parts):
                continue
            if path.suffix in _SKIP_SUFFIXES:
                continue
            parts.append(_entry(path.relative_to(engine_root).as_posix(), path))
    return hashlib.sha256(b"".join(parts)).hexdigest()


def _entry(rel: str, path: Path) -> bytes:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{rel}\0{digest}\n".encode()


@dataclass(frozen=True, slots=True)
class TierRecord:
    schema: str
    repository_id: str
    tier: str
    pin_sha: str
    checked_out_sha: str | None
    status: str
    detail: str
    stage: str
    exit_code: int | None
    wall_seconds: float | None
    peak_rss_bytes: int | None
    eligible_files: int | None
    bucket: str
    depth_class: str
    source_tree_digest: str
    engine_git_sha: str
    engine_tree_dirty: bool
    wheel_sha256: str
    canonical_sha256: str | None
    findings_sha256: str | None
    host: str
    python: str
    recorded_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @property
    def check_status(self) -> CheckStatus:
        try:
            return CheckStatus(self.status)
        except ValueError:
            return CheckStatus.ERROR


def record_path(results_dir: Path, repository_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in repository_id)
    return results_dir / f"{safe}.json"


def write_record(results_dir: Path, record: TierRecord) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    target = record_path(results_dir, record.repository_id)
    target.write_text(record.to_json(), encoding="utf-8")
    return target


def load_record(path: Path) -> TierRecord | None:
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("schema") != RECORD_SCHEMA:
        return None
    try:
        return TierRecord(
            schema=str(raw["schema"]),
            repository_id=str(raw["repository_id"]),
            tier=str(raw["tier"]),
            pin_sha=str(raw["pin_sha"]),
            checked_out_sha=_opt_str(raw.get("checked_out_sha")),
            status=str(raw["status"]),
            detail=str(raw.get("detail") or ""),
            stage=str(raw.get("stage") or ""),
            exit_code=_opt_int(raw.get("exit_code")),
            wall_seconds=_opt_float(raw.get("wall_seconds")),
            peak_rss_bytes=_opt_int(raw.get("peak_rss_bytes")),
            eligible_files=_opt_int(raw.get("eligible_files")),
            bucket=str(raw.get("bucket") or "unknown"),
            depth_class=str(raw.get("depth_class") or ""),
            source_tree_digest=str(raw["source_tree_digest"]),
            engine_git_sha=str(raw.get("engine_git_sha") or ""),
            engine_tree_dirty=bool(raw.get("engine_tree_dirty", True)),
            wheel_sha256=str(raw.get("wheel_sha256") or ""),
            canonical_sha256=_opt_str(raw.get("canonical_sha256")),
            findings_sha256=_opt_str(raw.get("findings_sha256")),
            host=str(raw.get("host") or ""),
            python=str(raw.get("python") or ""),
            recorded_at=str(raw.get("recorded_at") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_records(results_dir: Path) -> dict[str, TierRecord]:
    if not results_dir.is_dir():
        return {}
    records: dict[str, TierRecord] = {}
    for path in sorted(results_dir.glob("*.json")):
        if path.name == SUMMARY_NAME:
            continue
        record = load_record(path)
        if record is not None:
            records[record.repository_id] = record
    return records


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


@dataclass(frozen=True, slots=True)
class RecordFreshness:
    fresh: bool
    reason: str


def freshness(record: TierRecord, *, current_digest: str, pin_sha: str) -> RecordFreshness:
    if record.pin_sha != pin_sha:
        return RecordFreshness(False, "pin changed since the record was written")
    if record.source_tree_digest != current_digest:
        return RecordFreshness(False, "engine source changed since the record was written")
    return RecordFreshness(True, "record matches current source and pin")


def tier_for(record: TierRecord) -> CorpusTier:
    try:
        return CorpusTier(record.tier)
    except ValueError:
        return CorpusTier.EXTERNAL_LARGE


def measured_budgets(records: dict[str, TierRecord]) -> dict[str, dict[str, Any]]:
    """Per bucket: max wall seconds and peak RSS over executed records."""

    buckets: dict[str, dict[str, Any]] = {}
    for record in records.values():
        # Only completed assessments set a budget. A timeout records the cap, not a measurement.
        if record.check_status not in {CheckStatus.PASS, CheckStatus.UNSUPPORTED}:
            continue
        item = buckets.setdefault(
            record.bucket,
            {"count": 0, "max_wall_seconds": None, "max_peak_rss_bytes": None, "slowest": None},
        )
        item["count"] += 1
        if record.wall_seconds is not None and (
            item["max_wall_seconds"] is None or record.wall_seconds > item["max_wall_seconds"]
        ):
            item["max_wall_seconds"] = record.wall_seconds
            item["slowest"] = record.repository_id
        if record.peak_rss_bytes is not None and (
            item["max_peak_rss_bytes"] is None or record.peak_rss_bytes > item["max_peak_rss_bytes"]
        ):
            item["max_peak_rss_bytes"] = record.peak_rss_bytes
    return buckets


def write_summary(results_dir: Path, payload: dict[str, Any]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    target = results_dir / SUMMARY_NAME
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_summary(results_dir: Path) -> dict[str, Any] | None:
    target = results_dir / SUMMARY_NAME
    if not target.is_file():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("schema") != SUMMARY_SCHEMA:
        return None
    return raw
