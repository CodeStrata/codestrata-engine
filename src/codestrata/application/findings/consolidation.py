"""Consolidate duplicate Findings without first-wins loss (Slice 5.11)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.application.traceability.merge import merge_finding_traceability
from codestrata.domain.findings.consolidation import (
    FindingConsolidationBasis,
    FindingConsolidationDiagnostics,
    FindingConsolidationResult,
    FindingDuplicateGroup,
    FindingDuplicateKind,
    canonical_finding_condition_key,
    mapped_shared_rule_id,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence, RuleEvaluationResult
from codestrata.domain.traceability import TraceabilityValidationError
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids

_SEVERITY_RANK: dict[FindingSeverity, int] = {
    FindingSeverity.INFORMATIONAL: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def consolidate_findings(
    findings: Sequence[Finding],
    *,
    unresolved_candidates: Sequence[str] = (),
) -> FindingConsolidationResult:
    """Consolidate exact and equivalent same-rule Findings.

    Different rules remain separate except explicit legacy→Shared mappings where
    location/subject identity also agrees. Title-only matches never consolidate.
    """

    items = tuple(findings)
    if not items:
        return FindingConsolidationResult(
            findings=(),
            diagnostics=FindingConsolidationDiagnostics(),
        )

    # Pass 1: exact Finding ID groups.
    by_id: dict[str, list[Finding]] = {}
    for item in items:
        by_id.setdefault(item.id, []).append(item)

    id_merged: list[Finding] = []
    groups: list[FindingDuplicateGroup] = []
    original_to_canonical: dict[str, str] = {}
    limitations: list[str] = []
    exact_count = 0

    for finding_id in sorted(by_id):
        group = by_id[finding_id]
        if len(group) == 1:
            id_merged.append(group[0])
            original_to_canonical[finding_id] = finding_id
            continue
        try:
            merged, group_limits = _merge_exact_group(group)
        except TraceabilityValidationError as exc:
            # Fail closed: keep members separate with limitation.
            limitations.append(
                f"exact duplicate identity contradiction for {finding_id}: {exc}"
            )
            for item in sorted(group, key=lambda f: f.id):
                id_merged.append(item)
                original_to_canonical[item.id] = item.id
            continue
        id_merged.append(merged)
        member_ids = tuple(sorted({item.id for item in group}))
        for member_id in member_ids:
            original_to_canonical[member_id] = merged.id
        exact_count += len(group) - 1
        groups.append(
            FindingDuplicateGroup(
                canonical_finding_id=merged.id,
                member_finding_ids=member_ids,
                duplicate_kind=FindingDuplicateKind.EXACT,
                consolidation_basis=(FindingConsolidationBasis.SAME_FINDING_ID,),
                merged_evidence_ids=tuple(
                    sorted({ref.evidence_id for ref in merged.evidence_refs})
                ),
                member_severities=tuple(
                    sorted({item.severity.value for item in group})
                ),
                limitations=group_limits,
            )
        )

    # Pass 2: equivalent same-rule / legacy-mapped groups by condition key.
    by_condition: dict[str, list[Finding]] = {}
    for item in id_merged:
        key = _grouping_key(item)
        by_condition.setdefault(key, []).append(item)

    canonical: list[Finding] = []
    equivalent_count = 0
    legacy_count = 0

    for key in sorted(by_condition):
        group = by_condition[key]
        if len(group) == 1:
            canonical.append(group[0])
            original_to_canonical.setdefault(group[0].id, group[0].id)
            continue
        kind, basis = _classify_group(group)
        try:
            merged, group_limits = _merge_equivalent_group(group, kind=kind)
        except TraceabilityValidationError as exc:
            limitations.append(f"equivalent consolidation rejected for {key}: {exc}")
            for item in sorted(group, key=lambda f: (f.rule_id, f.id)):
                canonical.append(item)
                original_to_canonical.setdefault(item.id, item.id)
            continue
        canonical.append(merged)
        member_ids = tuple(sorted({item.id for item in group}))
        for member_id in member_ids:
            original_to_canonical[member_id] = merged.id
        if kind is FindingDuplicateKind.LEGACY_OVERLAP:
            legacy_count += len(group) - 1
        else:
            equivalent_count += len(group) - 1
        groups.append(
            FindingDuplicateGroup(
                canonical_finding_id=merged.id,
                member_finding_ids=member_ids,
                duplicate_kind=kind,
                consolidation_basis=basis,
                merged_evidence_ids=tuple(
                    sorted({ref.evidence_id for ref in merged.evidence_refs})
                ),
                member_severities=tuple(
                    sorted({item.severity.value for item in group})
                ),
                limitations=group_limits,
            )
        )

    ordered = tuple(
        sorted(canonical, key=lambda item: (item.rule_id, item.id, item.title))
    )
    # Ensure every original ID maps somewhere.
    for item in items:
        original_to_canonical.setdefault(item.id, item.id)

    diagnostics = FindingConsolidationDiagnostics(
        original_finding_count=len(items),
        canonical_finding_count=len(ordered),
        duplicate_group_count=len(groups),
        exact_duplicate_count=exact_count,
        equivalent_duplicate_count=equivalent_count,
        legacy_overlap_count=legacy_count,
        unresolved_duplicate_candidate_count=len(tuple(unresolved_candidates)),
    )
    return FindingConsolidationResult(
        findings=ordered,
        duplicate_groups=tuple(
            sorted(groups, key=lambda item: item.canonical_finding_id)
        ),
        original_to_canonical=dict(sorted(original_to_canonical.items())),
        diagnostics=diagnostics,
        limitations=tuple(normalize_limitations(limitations)),
    )


def consolidate_rule_evaluation(
    evaluation: RuleEvaluationResult,
) -> tuple[RuleEvaluationResult, FindingConsolidationResult]:
    """Consolidate Findings inside a RuleEvaluationResult."""

    result = consolidate_findings(evaluation.findings)
    updated = RuleEvaluationResult.from_findings(
        findings=result.findings,  # type: ignore[arg-type]
        rules_evaluated=evaluation.rules_evaluated,
        rules_skipped=evaluation.rules_skipped,
    )
    return updated, result


def remap_finding_ids(
    finding_ids: Sequence[str],
    original_to_canonical: Mapping[str, str],
) -> tuple[str, ...]:
    """Map member Finding IDs to canonical IDs and dedupe."""

    remapped = [
        original_to_canonical.get(str(item), str(item))
        for item in finding_ids
        if str(item).strip()
    ]
    return sorted_unique_ids(remapped, label="finding_id")


def _grouping_key(finding: Finding) -> str:
    """Group by condition key; legacy-mapped rules share the Shared Rule key."""

    mapped = mapped_shared_rule_id(finding.rule_id)
    if mapped is None:
        return canonical_finding_condition_key(finding)
    # Build a synthetic peer for condition comparison under the Shared Rule ID.
    peer = finding.model_copy(update={"rule_id": mapped})
    return canonical_finding_condition_key(peer)


def _classify_group(
    group: Sequence[Finding],
) -> tuple[FindingDuplicateKind, tuple[FindingConsolidationBasis, ...]]:
    rule_ids = {item.rule_id for item in group}
    if len(rule_ids) == 1:
        return (
            FindingDuplicateKind.EQUIVALENT_SAME_RULE,
            (
                FindingConsolidationBasis.SAME_RULE_ID,
                FindingConsolidationBasis.SAME_SUBJECT_IDENTITY,
            ),
        )
    return (
        FindingDuplicateKind.LEGACY_OVERLAP,
        (
            FindingConsolidationBasis.LEGACY_TO_SHARED_RULE_MAPPING,
            FindingConsolidationBasis.SAME_SUBJECT_IDENTITY,
        ),
    )


def _merge_exact_group(group: Sequence[Finding]) -> tuple[Finding, tuple[str, ...]]:
    rule_ids = {item.rule_id for item in group}
    if len(rule_ids) != 1:
        raise TraceabilityValidationError(
            f"same Finding ID with contradictory rule_ids: {sorted(rule_ids)}"
        )
    preferred = sorted(group, key=lambda item: item.id)[0]
    limits: list[str] = []
    merged = preferred
    for other in sorted(group, key=lambda item: item.id)[1:]:
        _assert_compatible_identity(merged, other)
        merged = _merge_pair(merged, other, limits=limits)
    return merged, tuple(normalize_limitations(limits))


def _merge_equivalent_group(
    group: Sequence[Finding],
    *,
    kind: FindingDuplicateKind,
) -> tuple[Finding, tuple[str, ...]]:
    # Shared Rule Finding is canonical for legacy overlap; otherwise smallest ID.
    if kind is FindingDuplicateKind.LEGACY_OVERLAP:
        shared = [
            item
            for item in group
            if mapped_shared_rule_id(item.rule_id) is None
            and str(item.id).startswith("finding:")
        ]
        preferred = sorted(shared or list(group), key=lambda item: item.id)[0]
    else:
        preferred = sorted(group, key=lambda item: item.id)[0]
    limits: list[str] = [
        f"consolidated {kind.value} duplicates into {preferred.id}",
    ]
    if kind is FindingDuplicateKind.LEGACY_OVERLAP:
        limits.append("legacy_to_shared_rule_mapping applied; Shared Rule Finding is canonical")
    merged = preferred
    for other in sorted(group, key=lambda item: item.id):
        if other.id == preferred.id and other is preferred:
            continue
        if other.rule_id != merged.rule_id and kind is FindingDuplicateKind.LEGACY_OVERLAP:
            # Keep Shared Rule identity; still union evidence from legacy member.
            other_as_shared = other.model_copy(
                update={"rule_id": merged.rule_id, "id": other.id}
            )
            _assert_compatible_location(merged, other_as_shared)
            merged = _merge_pair(merged, other_as_shared, limits=limits, allow_id_alias=True)
            continue
        _assert_compatible_identity(merged, other)
        merged = _merge_pair(merged, other, limits=limits, allow_id_alias=True)
    member_ids = tuple(sorted({item.id for item in group if item.id != merged.id}))
    metadata = dict(merged.metadata)
    if member_ids:
        metadata["duplicate_member_finding_ids"] = ",".join(member_ids)
        metadata["consolidation_kind"] = kind.value
    merged = merged.model_copy(
        update={
            "metadata": metadata,
            "limitations": normalize_limitations((*merged.limitations, *limits)),
        }
    )
    return merged, tuple(normalize_limitations(limits))


def _merge_pair(
    preferred: Finding,
    other: Finding,
    *,
    limits: list[str],
    allow_id_alias: bool = False,
) -> Finding:
    if preferred.id != other.id and not allow_id_alias:
        raise TraceabilityValidationError("exact merge requires identical finding IDs")
    if preferred.rule_id != other.rule_id:
        raise TraceabilityValidationError(
            f"cannot merge contradictory rule_ids: {preferred.rule_id!r} vs {other.rule_id!r}"
        )

    # Prefer Shared-rule / richer preferred for non-traceability fields, then union.
    base = preferred
    if other.id < preferred.id and allow_id_alias:
        # Keep preferred.id as canonical; still accept other's evidence via merge below.
        pass

    severity, severity_limits = _resolve_severity(base, other)
    limits.extend(severity_limits)

    # Union legacy FindingEvidence rows (path/source scoped).
    evidence = _union_finding_evidence(base.evidence, other.evidence)
    nodes = tuple(
        sorted(
            set(base.affected_assessment_node_ids) | set(other.affected_assessment_node_ids),
            key=lambda node: str(node.root),
        )
    )
    # Merge EvidenceRefs + recompute Finding Confidence.
    # Temporarily align IDs for merge_finding_traceability identity assumption.
    other_aligned = other.model_copy(update={"id": base.id, "rule_id": base.rule_id})
    merged_trace = merge_finding_traceability(base, other_aligned)
    merged = merged_trace.model_copy(
        update={
            "severity": severity,
            "evidence": evidence,
            "affected_assessment_node_ids": nodes,
            "description": base.description or other.description,
            "title": base.title or other.title,
        }
    )
    # Slice 5.13 — recalibrate from canonical evidence/context; duplicate count
    # never escalates severity.
    from codestrata.application.findings.severity_calibration import calibrate_finding

    recalibrated = calibrate_finding(merged)
    if severity_limits and recalibrated.severity is not severity:
        limits.append(
            "severity recalibrated after consolidation using Finding severity policy; "
            f"pre-calibration={severity.value}, calibrated={recalibrated.severity.value}"
        )
    return recalibrated


def _assert_compatible_identity(left: Finding, right: Finding) -> None:
    if left.rule_id != right.rule_id:
        raise TraceabilityValidationError(
            f"contradictory rule_id: {left.rule_id!r} vs {right.rule_id!r}"
        )
    left_paths = _location_fingerprint(left)
    right_paths = _location_fingerprint(right)
    if left_paths and right_paths and left_paths != right_paths:
        # Compatible when one is a subset (partial projection) — otherwise fail.
        if not left_paths.issubset(right_paths) and not right_paths.issubset(left_paths):
            raise TraceabilityValidationError(
                "contradictory repository locations for consolidated Finding"
            )
    left_metric = (left.metadata or {}).get("measurement_metric_id")
    right_metric = (right.metadata or {}).get("measurement_metric_id")
    if left_metric and right_metric and str(left_metric) != str(right_metric):
        raise TraceabilityValidationError("contradictory measurement_metric_id")
    left_scope = (left.metadata or {}).get("measurement_scope_ref")
    right_scope = (right.metadata or {}).get("measurement_scope_ref")
    if left_scope and right_scope and str(left_scope) != str(right_scope):
        raise TraceabilityValidationError("contradictory measurement_scope_ref")
    left_graph = (left.metadata or {}).get("graph_edge_id") or (
        left.metadata or {}
    ).get("graph_cycle_id")
    right_graph = (right.metadata or {}).get("graph_edge_id") or (
        right.metadata or {}
    ).get("graph_cycle_id")
    if left_graph and right_graph and str(left_graph) != str(right_graph):
        raise TraceabilityValidationError("contradictory graph identity")


def _assert_compatible_location(left: Finding, right: Finding) -> None:
    left_paths = _location_fingerprint(left)
    right_paths = _location_fingerprint(right)
    if left_paths and right_paths and left_paths.isdisjoint(right_paths):
        raise TraceabilityValidationError(
            "legacy overlap requires agreeing repository location identity"
        )


def _location_fingerprint(finding: Finding) -> set[str]:
    paths: set[str] = set()
    for item in finding.evidence:
        if item.path:
            paths.add(item.path.replace("\\", "/").strip().lower())
    for item in finding.evidence_refs:
        loc = getattr(item, "safe_location", None)
        if loc:
            paths.add(str(loc).replace("\\", "/").strip().lower())
    subjects = str((finding.metadata or {}).get("subject_keys") or "")
    for part in subjects.split(","):
        token = part.strip().lower()
        if "/" in token or token.endswith((".py", ".ts", ".js", ".java", ".cs", ".php", ".json", ".yml", ".yaml", ".env", ".toml", ".xml")):
            paths.add(token)
    return paths


def _resolve_severity(
    left: Finding, right: Finding
) -> tuple[FindingSeverity, list[str]]:
    if left.severity is right.severity:
        return left.severity, []
    # Same-rule identical subjects: provisional highest until Slice 5.13
    # recalibration validates against the severity policy (not duplicate count).
    winner = left.severity
    if _SEVERITY_RANK[right.severity] > _SEVERITY_RANK[left.severity]:
        winner = right.severity
    return winner, [
        "severity conflict during consolidation; provisional highest severity "
        f"({winner.value}) before policy recalibration; "
        f"members={left.severity.value},{right.severity.value}"
    ]


def _union_finding_evidence(
    left: Sequence[FindingEvidence],
    right: Sequence[FindingEvidence],
) -> tuple[FindingEvidence, ...]:
    by_key: dict[tuple[str, str, str], FindingEvidence] = {}
    for item in (*left, *right):
        key = (
            item.evidence_type.strip().lower(),
            item.source_id.strip().lower(),
            (item.path or "").strip().lower().replace("\\", "/"),
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = item
            continue
        # Prefer non-empty excerpt.
        if not existing.excerpt and item.excerpt:
            by_key[key] = item
    return tuple(sorted(by_key.values(), key=lambda item: (item.evidence_type, item.source_id, item.path or "")))
