"""R2-P08 adjacent and span comparison wiring.

Reuses ``ScanComparisonService.compare_results`` and M27 RANGE inputs.
Writes only under ``comparisons/``. Does not mutate snapshot artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from codestrata.application.incremental.git_inputs import (
    GitInputError,
    GitInputMode,
    GitInputRequest,
    GitInputResolution,
    resolve_git_inputs,
)
from codestrata.application.incremental.trend_bundle import (
    ANALYSIS_RESULT_FILENAME,
    COMPARISON_FILENAME,
    COMPARISON_PAIRS,
    TrendBundlePaths,
)
from codestrata.application.incremental.trend_series import (
    PinnedEvaluationProfile,
    TrendSeriesResult,
    TrendSlotRecord,
)
from codestrata.models import AnalysisResult
from codestrata.services.scan_comparison_service import ScanComparisonService

TREND_COMPARISON_SCHEMA = "codestrata.trend-comparison.v1"
TREND_COMPARISON_SCHEMA_VERSION = "1.0.0"
PUBLIC_OUTCOME_FAMILIES = (
    "architecture",
    "security",
    "quality",
    "maintainability",
)
TESTING_MAPS_UNDER = "quality"
STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_COMPUTABLE = "not_computable"
STATUS_INCOMPATIBLE = "incompatible"


def write_trend_comparisons(
    bundle: TrendBundlePaths,
    result: TrendSeriesResult,
) -> list[dict[str, Any]]:
    """Compute all five comparison slots. Never skip a pair."""

    by_slot = {slot.slot: slot for slot in result.slots}
    written: list[dict[str, Any]] = []
    for left, right, name in COMPARISON_PAIRS:
        payload = compare_trend_pair(
            bundle,
            result,
            base=by_slot[left],
            candidate=by_slot[right],
            name=name,
        )
        path = bundle.comparison_directory(name) / COMPARISON_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(payload)
    return written


def compare_trend_pair(
    bundle: TrendBundlePaths,
    result: TrendSeriesResult,
    *,
    base: TrendSlotRecord,
    candidate: TrendSlotRecord,
    name: str,
) -> dict[str, Any]:
    """Build one comparison payload from existing comparison contracts."""

    envelope = _envelope(name, base, candidate, result.profile)
    gate_status, gate_reason, compatibility = pair_gate(base, candidate)
    envelope["compatibility_status"] = compatibility
    if gate_status != STATUS_AVAILABLE:
        envelope["status"] = gate_status
        envelope["unavailable_reason"] = gate_reason
        envelope["computed"] = False
        return envelope

    m27, m27_reason = _resolve_m27(
        result.git_root,
        base,
        candidate,
        assessment_relpath=result.assessment_relpath,
    )
    envelope["m27"] = m27
    if m27 is None:
        envelope["status"] = STATUS_NOT_COMPUTABLE
        envelope["unavailable_reason"] = m27_reason or "m27_unavailable"
        envelope["computed"] = False
        return envelope

    base_analysis = load_slot_analysis(bundle.slot_directory(base.slot))
    candidate_analysis = load_slot_analysis(bundle.slot_directory(candidate.slot))
    if base_analysis is None or candidate_analysis is None:
        envelope["status"] = STATUS_NOT_COMPUTABLE
        envelope["unavailable_reason"] = "missing_assessment_artifact"
        envelope["computed"] = False
        return envelope

    changed_files = [
        str(item.get("path"))
        for item in m27.get("files") or ()
        if isinstance(item, dict) and item.get("path")
    ]
    try:
        comparison = ScanComparisonService().compare_results(
            current=candidate_analysis,
            baseline=base_analysis,
            current_timestamp=candidate.evaluation_time,
            baseline_timestamp=base.evaluation_time,
            evaluate_lifecycle=True,
            base_graph=load_slot_graph(bundle.slot_directory(base.slot)),
            candidate_graph=load_slot_graph(bundle.slot_directory(candidate.slot)),
            changed_files=changed_files,
            source_changed=_values_differ(base.source_digest, candidate.source_digest),
            feed_changed=_values_differ(base.feed_digest, candidate.feed_digest),
            config_changed=_values_differ(base.config_digest, candidate.config_digest),
            engine_changed=_values_differ(base.engine_version, candidate.engine_version),
            base_digests=_slot_digests(base),
            candidate_digests=_slot_digests(candidate),
        )
    except Exception as error:  # noqa: BLE001 - pair failure must not drop the slot
        envelope["status"] = STATUS_NOT_COMPUTABLE
        envelope["unavailable_reason"] = f"comparison_failed:{error}"
        envelope["computed"] = False
        return envelope

    dumped = comparison.model_dump(mode="json")
    envelope["status"] = STATUS_AVAILABLE
    envelope["unavailable_reason"] = None
    envelope["computed"] = True
    envelope["comparison"] = dumped
    envelope["metric_deltas"] = dumped.get("metric_deltas") or []
    envelope["public_outcome_verdicts"] = public_outcome_verdicts(dumped.get("outcome_verdicts"))
    return envelope


def pair_gate(base: TrendSlotRecord, candidate: TrendSlotRecord) -> tuple[str, str | None, str]:
    """Decide whether a pair may run. Failed/missing/incompatible stay explicit."""

    if base.status != "available" or candidate.status != "available":
        return STATUS_UNAVAILABLE, "slot_unavailable_or_failed", "unknown"
    if base.sha is None or candidate.sha is None:
        return STATUS_NOT_COMPUTABLE, "missing_revision", "unknown"
    if _values_differ(base.engine_version, candidate.engine_version) or _values_differ(
        base.config_digest, candidate.config_digest
    ):
        return STATUS_INCOMPATIBLE, "incompatible_profile", "incompatible"
    return STATUS_AVAILABLE, None, "compatible"


def load_slot_analysis(slot_directory: Path) -> AnalysisResult | None:
    matches = [path for path in slot_directory.rglob(ANALYSIS_RESULT_FILENAME) if path.is_file()]
    if not matches:
        return None
    try:
        payload = json.loads(sorted(matches)[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    payload.pop("comparison", None)
    try:
        return AnalysisResult.model_validate(payload)
    except ValidationError:
        return None


def load_slot_graph(slot_directory: Path) -> Any | None:
    matches = sorted(
        path for path in slot_directory.rglob("graphs/repository-graph.json") if path.is_file()
    )
    if not matches:
        matches = sorted(
            path for path in slot_directory.rglob("repository-graph.json") if path.is_file()
        )
    if not matches:
        return None
    try:
        payload = json.loads(matches[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _envelope(
    name: str,
    base: TrendSlotRecord,
    candidate: TrendSlotRecord,
    profile: PinnedEvaluationProfile,
) -> dict[str, Any]:
    return {
        "schema_name": TREND_COMPARISON_SCHEMA,
        "schema_version": TREND_COMPARISON_SCHEMA_VERSION,
        "id": name,
        "base_slot": base.slot,
        "candidate_slot": candidate.slot,
        "base_sha": base.sha,
        "candidate_sha": candidate.sha,
        "base_source_revision": base.source_revision,
        "candidate_source_revision": candidate.source_revision,
        "base_engine_version": base.engine_version,
        "candidate_engine_version": candidate.engine_version,
        "base_ruleset_version": profile.ruleset_version,
        "candidate_ruleset_version": profile.ruleset_version,
        "base_config_digest": base.config_digest,
        "candidate_config_digest": candidate.config_digest,
        "base_feed_digest": base.feed_digest,
        "candidate_feed_digest": candidate.feed_digest,
        "base_source_digest": base.source_digest,
        "candidate_source_digest": candidate.source_digest,
        "base_result_digest": base.result_digest,
        "candidate_result_digest": candidate.result_digest,
        "status": STATUS_NOT_COMPUTABLE,
        "unavailable_reason": None,
        "computed": False,
        "compatibility_status": "unknown",
        "m27": None,
        "comparison": None,
        "metric_deltas": [],
        "public_outcome_families": list(PUBLIC_OUTCOME_FAMILIES),
        "testing_maps_under": TESTING_MAPS_UNDER,
        "public_outcome_verdicts": {},
    }


def _resolve_m27(
    git_root: Path | None,
    base: TrendSlotRecord,
    candidate: TrendSlotRecord,
    *,
    assessment_relpath: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    if git_root is None or base.sha is None or candidate.sha is None:
        return None, "m27_missing_git_revisions"
    try:
        resolution = resolve_git_inputs(
            GitInputRequest(
                repository_root=git_root,
                mode=GitInputMode.RANGE,
                base=base.sha,
                head=candidate.sha,
            )
        )
    except (GitInputError, OSError, ValueError) as error:
        return None, f"m27_failed:{error}"
    return _scope_m27(_m27_payload(resolution), assessment_relpath), None


def _scope_m27(payload: dict[str, Any], assessment_relpath: str) -> dict[str, Any]:
    """Keep Git range identity, but project only the requested assess root."""

    prefix = assessment_relpath.strip().strip("/")
    if not prefix:
        return payload
    scoped_prefix = f"{prefix}/"

    def in_scope(path: str | None) -> bool:
        if not path:
            return False
        return path == prefix or path.startswith(scoped_prefix)

    def strip_prefix(path: str | None) -> str | None:
        if not path:
            return path
        if path == prefix:
            return ""
        if path.startswith(scoped_prefix):
            return path[len(scoped_prefix) :]
        return path

    files: list[dict[str, Any]] = []
    for item in payload.get("files") or ():
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "") or None
        old_path = str(item.get("old_path") or "") or None
        if not (in_scope(path) or in_scope(old_path)):
            continue
        files.append(
            {
                **item,
                "path": strip_prefix(str(path) if path else None),
                "old_path": strip_prefix(str(old_path) if old_path else None),
            }
        )
    changed_ids = [str(item.get("path")) for item in files if item.get("path")]
    test_paths = [
        stripped
        for raw in payload.get("test_touch_paths") or ()
        if in_scope(str(raw))
        for stripped in (strip_prefix(str(raw)),)
        if stripped
    ]
    scoped = dict(payload)
    scoped["files"] = files
    scoped["changed_file_ids"] = changed_ids
    scoped["changed_file_count"] = len(changed_ids)
    scoped["changed_text_lines"] = _scoped_text_lines(files)
    components = sorted(
        {str(item.get("component_id")) for item in files if item.get("component_id")}
    )
    scoped["changed_component_ids"] = components
    scoped["test_touch_paths"] = test_paths
    scoped["test_touch"] = bool(test_paths)
    limitations = [str(item) for item in payload.get("limitations") or ()]
    if "assessment_scope_filter" not in limitations:
        limitations.append("assessment_scope_filter")
    scoped["limitations"] = limitations
    return scoped


def _scoped_text_lines(files: list[dict[str, Any]]) -> int | None:
    """Sum added and deleted lines for files that remain in the assess scope.

    An empty scoped file list is zero in-scope text, not the unscoped total.
    A binary file or a missing line count stays unknown.
    """

    total = 0
    for item in files:
        if item.get("binary"):
            return None
        added = item.get("added_lines")
        deleted = item.get("deleted_lines")
        if added is None or deleted is None:
            return None
        total += int(added) + int(deleted)
    return total


def _m27_payload(resolution: GitInputResolution) -> dict[str, Any]:
    summary = resolution.change_summary
    return {
        "schema_name": resolution.schema_name,
        "mode": resolution.mode.value,
        "resolved_base": resolution.resolved_base,
        "resolved_head": resolution.resolved_head,
        "comparison_completeness": resolution.comparison_completeness.value,
        "full_comparison": resolution.full_comparison,
        "changed_file_ids": list(summary.changed_file_ids),
        "changed_file_count": summary.changed_file_count,
        "changed_component_ids": list(summary.changed_component_ids),
        "changed_text_lines": summary.changed_text_lines,
        "test_touch": summary.test_touch,
        "test_touch_paths": list(summary.test_touch_paths),
        "boundary_spread_status": summary.boundary_spread_status.value,
        "boundary_spread_count": summary.boundary_spread_count,
        "binary_partial": summary.binary_partial,
        "mapping_coverage": summary.mapping_coverage,
        "files": [
            {
                "path": item.path,
                "old_path": item.old_path,
                "status": item.status.value,
                "unit_class": item.unit_class.value,
                "binary": item.binary,
                "added_lines": item.added_lines,
                "deleted_lines": item.deleted_lines,
                "component_id": item.component_id,
            }
            for item in resolution.files
        ],
        "canonical_digest": resolution.canonical_digest,
        "limitations": list(resolution.limitations),
    }


def _slot_digests(slot: TrendSlotRecord) -> dict[str, str | None]:
    return {
        "source": slot.source_digest,
        "feed": slot.feed_digest,
        "config": slot.config_digest,
        "engine": slot.engine_version,
        "coverage": None,
    }


def public_outcome_verdicts(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    public: dict[str, Any] = {}
    for family in PUBLIC_OUTCOME_FAMILIES:
        value = raw.get(family)
        if isinstance(value, dict):
            public[family] = dict(value)
    testing = raw.get("testing")
    quality = public.get("quality")
    if isinstance(testing, dict) and isinstance(quality, dict):
        public["quality"] = {
            **quality,
            "testing_mapped_under_quality": testing,
        }
    return public


def _values_differ(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left != right
