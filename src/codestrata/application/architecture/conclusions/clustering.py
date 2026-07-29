"""Deterministic finding clustering and primary selection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.application.architecture.conclusions.rule_catalog import (
    BOUNDARY_RULES,
    COUPLING_RULES,
)
from codestrata.domain.architecture.conclusions.enums import FindingRelationshipType
from codestrata.domain.architecture.conclusions.identifiers import (
    CAT_BOUNDARY_INTEGRITY,
    CAT_COUPLING,
    CAT_DEPENDENCY_STRUCTURE,
    CAT_ENTERPRISE_CONFORMANCE,
    CAT_FRAMEWORK_INDEPENDENCE,
    build_cluster_id,
)
from codestrata.domain.architecture.conclusions.relationships import (
    FindingCluster,
    FindingRelationship,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.rules.enums import RuleConfidence

_SEVERITY_RANK = {
    FindingSeverity.INFORMATIONAL: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}

_RULE_PRECEDENCE = {
    RULE_INVALID_DEPENDENCY_DIRECTION: 10,
    RULE_LAYER_BOUNDARY_VIOLATION: 9,
    RULE_DEPENDENCY_CYCLE: 8,
    RULE_FRAMEWORK_LEAKAGE: 7,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING: 6,
    RULE_COMPONENT_CONCENTRATION: 5,
    RULE_ENTERPRISE_STANDARD_MISMATCH: 4,
}

_CONFIDENCE_RANK = {
    RuleConfidence.LOW: 0,
    RuleConfidence.MEDIUM: 1,
    RuleConfidence.HIGH: 2,
    RuleConfidence.CERTAIN: 3,
}


def _subject_keys(finding: Finding) -> tuple[str, ...]:
    raw = finding.metadata.get("subject_keys")
    if isinstance(raw, (list, tuple)):
        return tuple(sorted({str(item).lower() for item in raw if str(item).strip()}))
    if isinstance(raw, str) and raw.strip():
        return tuple(sorted({part.strip().lower() for part in raw.split(",") if part.strip()}))
    return ()


def _scope_key(finding: Finding) -> str:
    subjects = [
        token
        for token in _subject_keys(finding)
        if token not in {"cycle", "out"} and not token.startswith("out:")
    ]
    if not subjects:
        return finding.rule_id
    return "|".join(sorted(subjects)[:4])


def _category_for_rule(rule_id: str) -> str:
    if rule_id in BOUNDARY_RULES - {RULE_FRAMEWORK_LEAKAGE}:
        return CAT_BOUNDARY_INTEGRITY
    if rule_id == RULE_FRAMEWORK_LEAKAGE:
        return CAT_FRAMEWORK_INDEPENDENCE
    if rule_id in COUPLING_RULES:
        return CAT_COUPLING
    if rule_id == RULE_ENTERPRISE_STANDARD_MISMATCH:
        return CAT_ENTERPRISE_CONFORMANCE
    if rule_id == RULE_DEPENDENCY_CYCLE:
        return CAT_DEPENDENCY_STRUCTURE
    return CAT_DEPENDENCY_STRUCTURE


def select_primary_finding(findings: Sequence[Finding]) -> Finding:
    """Transparent deterministic primary selection."""

    def sort_key(finding: Finding) -> tuple[object, ...]:
        confidence_raw = str(finding.metadata.get("confidence", "medium")).lower()
        try:
            confidence = RuleConfidence(confidence_raw)
        except ValueError:
            confidence = RuleConfidence.MEDIUM
        return (
            -_SEVERITY_RANK.get(finding.severity, 0),
            -_RULE_PRECEDENCE.get(finding.rule_id, 0),
            -_CONFIDENCE_RANK.get(confidence, 1),
            finding.rule_id,
            finding.id,
        )

    ordered = sorted(findings, key=sort_key)
    return ordered[0]


def cluster_findings(
    findings: Sequence[Finding],
    relationships: Sequence[FindingRelationship],
) -> tuple[FindingCluster, ...]:
    architecture = [
        finding
        for finding in findings
        if finding.rule_id.startswith("architecture.")
    ]
    by_id: dict[str, Finding] = {finding.id: finding for finding in architecture}
    if not architecture:
        return ()

    # Union-find over related findings that share category family.
    parent: dict[str, str] = {finding.id: finding.id for finding in architecture}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        root_l, root_r = find(left), find(right)
        if root_l == root_r:
            return
        if root_l < root_r:
            parent[root_r] = root_l
        else:
            parent[root_l] = root_r

    related_pairs = {
        (rel.source_finding_id, rel.target_finding_id): rel for rel in relationships
    }
    for (left_id, right_id), rel in related_pairs.items():
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if left is None or right is None:
            continue
        # Keep coupling separate from boundary (Option A), unless relationship
        # explicitly says same_root_cause (we don't emit that for coupling+boundary).
        left_boundary = left.rule_id in BOUNDARY_RULES
        right_boundary = right.rule_id in BOUNDARY_RULES
        left_coupling = left.rule_id in COUPLING_RULES
        right_coupling = right.rule_id in COUPLING_RULES
        if (left_boundary and right_coupling) or (right_boundary and left_coupling):
            continue
        if rel.relationship_type is FindingRelationshipType.INDEPENDENT:
            continue
        union(left_id, right_id)

    groups: dict[str, list[Finding]] = defaultdict(list)
    for finding in architecture:
        groups[find(finding.id)].append(finding)

    clusters: list[FindingCluster] = []
    for members in groups.values():
        ordered_members = sorted(members, key=lambda item: (item.rule_id, item.id))
        finding_ids = tuple(item.id for item in ordered_members)
        # Category selection:
        # - mixed boundary family (direction/layer + optional cycle) → boundary integrity
        # - cycle alone → dependency structure
        # - framework leakage alone → framework independence
        # - coupling family → coupling
        rule_ids = {item.rule_id for item in ordered_members}
        has_direct_boundary = bool(
            rule_ids.intersection(
                {
                    RULE_INVALID_DEPENDENCY_DIRECTION,
                    RULE_LAYER_BOUNDARY_VIOLATION,
                }
            )
        )
        has_cycle = RULE_DEPENDENCY_CYCLE in rule_ids
        has_framework = RULE_FRAMEWORK_LEAKAGE in rule_ids
        has_coupling = bool(rule_ids.intersection(COUPLING_RULES))
        has_enterprise = RULE_ENTERPRISE_STANDARD_MISMATCH in rule_ids

        if has_direct_boundary or (has_cycle and has_direct_boundary):
            category = CAT_BOUNDARY_INTEGRITY
        elif has_direct_boundary and has_framework:
            category = CAT_BOUNDARY_INTEGRITY
        elif has_cycle and has_framework:
            category = CAT_BOUNDARY_INTEGRITY
        elif has_cycle and not has_direct_boundary and not has_framework:
            category = CAT_DEPENDENCY_STRUCTURE
        elif has_framework:
            category = CAT_FRAMEWORK_INDEPENDENCE
        elif has_coupling:
            category = CAT_COUPLING
        elif has_enterprise:
            category = CAT_ENTERPRISE_CONFORMANCE
        else:
            category = _category_for_rule(ordered_members[0].rule_id)

        from codestrata.application.architecture.conclusions.helpers import scope_from_findings

        scope = scope_from_findings(ordered_members)
        reason_codes = tuple(
            sorted(
                {
                    rel.reason_code
                    for rel in relationships
                    if rel.source_finding_id in finding_ids
                    and rel.target_finding_id in finding_ids
                }
            )
        )
        primary = select_primary_finding(ordered_members)
        cluster_id = build_cluster_id(
            category=category,
            scope_keys=scope,
            finding_ids=finding_ids,
        )
        clusters.append(
            FindingCluster(
                cluster_id=cluster_id,
                category=category,
                finding_ids=finding_ids,
                affected_scope=scope,
                relationship_reason_codes=reason_codes,
                primary_finding_id=primary.id,
            )
        )

    return tuple(sorted(clusters, key=lambda item: (item.category, item.cluster_id)))
