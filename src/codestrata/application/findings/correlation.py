"""Build deterministic cross-rule Finding correlations (Slice 5.12)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any

from codestrata.application.findings.correlation_policies import (
    FindingCorrelationPolicy,
    all_correlation_policies,
    policies_for_rules,
)
from codestrata.domain.findings.correlation import (
    CorrelationConfidence,
    CorrelationConfidenceLevel,
    CorrelationDirection,
    FindingCorrelation,
    FindingCorrelationBasis,
    FindingCorrelationCluster,
    FindingCorrelationDiagnostics,
    FindingCorrelationResult,
    FindingCorrelationType,
    build_correlation_id,
    min_correlation_confidence,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.findings.models import Finding, RuleEvaluationResult
from codestrata.domain.traceability.location import EvidenceLocation

_EVIDENCE_ID_RE = re.compile(r"^ev:[0-9a-f]{16,}$", re.IGNORECASE)
_SEVERITY_RANK = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.HIGH: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 3,
    FindingSeverity.INFORMATIONAL: 4,
}


def correlate_findings(
    findings: Sequence[Finding],
    *,
    policies: Sequence[FindingCorrelationPolicy] | None = None,
) -> FindingCorrelationResult:
    """Correlate distinct Findings after Slice 5.11 consolidation.

    Does not merge, delete, or change Finding IDs / severity / Finding Confidence.
    """

    items = tuple(findings)
    if len(items) < 2:
        return FindingCorrelationResult(
            findings=items,
            diagnostics=FindingCorrelationDiagnostics(finding_count=len(items)),
        )

    by_id = {item.id: item for item in items}
    active_policies = tuple(policies) if policies is not None else all_correlation_policies()
    correlations: list[FindingCorrelation] = []
    rejected = 0
    policy_matches = 0

    # 1) Shared evidence correlations (material evidence_id + compatible subject).
    for left, right, shared_ids in _shared_evidence_pairs(items):
        if left.rule_id == right.rule_id:
            continue  # same-rule handled by consolidation
        subject_ok, subject_ids, bases = _compatible_subjects(left, right)
        if not subject_ok and not shared_ids:
            rejected += 1
            continue
        if not subject_ok:
            # Broad aggregate evidence without subject compatibility — reject.
            rejected += 1
            continue
        corr = _build_correlation(
            left,
            right,
            correlation_type=FindingCorrelationType.SHARED_EVIDENCE,
            bases=(FindingCorrelationBasis.SAME_EVIDENCE_ID, *bases),
            shared_evidence_ids=shared_ids,
            shared_subject_ids=subject_ids,
            confidence_level=CorrelationConfidenceLevel.HIGH,
            shared_identity=",".join(shared_ids),
        )
        correlations.append(corr)

    # 2) Explicit policy correlations.
    ordered = sorted(items, key=lambda item: (item.rule_id, item.id))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if left.rule_id == right.rule_id:
                continue
            matched = policies_for_rules(left.rule_id, right.rule_id)
            if not matched:
                # Path-only without policy is never enough.
                continue
            for policy in matched:
                if policy not in active_policies and policies is not None:
                    continue
                ok, shared_subjects, bases, level, shared_identity = _policy_match(
                    left, right, policy
                )
                if not ok:
                    rejected += 1
                    continue
                policy_matches += 1
                bases = tuple(
                    dict.fromkeys((*policy.required_bases, *bases))
                )
                # Ensure explicit rule relationship basis for policy hits.
                if FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP not in bases:
                    bases = (
                        *bases,
                        FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
                    )
                level = min_correlation_confidence(level, policy.minimum_confidence)
                if _CONFIDENCE_RANK[level] < _CONFIDENCE_RANK[policy.minimum_confidence]:
                    rejected += 1
                    continue
                corr = _build_correlation(
                    left,
                    right,
                    correlation_type=policy.correlation_type,
                    bases=bases,
                    shared_subject_ids=shared_subjects,
                    confidence_level=level,
                    shared_identity=shared_identity or policy.policy_id,
                    policy_id=policy.policy_id,
                    limitations=policy.limitations,
                    direction=policy.direction,
                    metadata={"policy_id": policy.policy_id},
                )
                correlations.append(corr)

    deduped = _dedupe_correlations(correlations)
    clusters = _build_clusters(deduped, by_id)
    annotated = _attach_correlation_refs(items, deduped)

    by_type: dict[str, int] = {}
    cross_head = 0
    correlated_ids: set[str] = set()
    for item in deduped:
        by_type[item.correlation_type.value] = (
            by_type.get(item.correlation_type.value, 0) + 1
        )
        correlated_ids.update(item.finding_ids)
        if len(set(item.assessment_head_ids)) > 1:
            cross_head += 1

    unresolved = 0
    for item in deduped:
        for fid in item.finding_ids:
            if fid not in by_id:
                unresolved += 1

    diagnostics = FindingCorrelationDiagnostics(
        finding_count=len(items),
        correlation_count=len(deduped),
        correlated_finding_count=len(correlated_ids),
        correlations_by_type=dict(sorted(by_type.items())),
        cross_head_correlation_count=cross_head,
        unresolved_reference_count=unresolved,
        policy_match_count=policy_matches,
        rejected_candidate_count=rejected,
    )
    return FindingCorrelationResult(
        findings=annotated,
        correlations=tuple(sorted(deduped, key=lambda item: item.correlation_id)),
        clusters=tuple(sorted(clusters, key=lambda item: item.cluster_id)),
        diagnostics=diagnostics,
        limitations=(
            "Cross-rule correlation does not merge Findings or change severity.",
            "Title similarity never creates a correlation.",
        ),
    )


def correlate_rule_evaluation(
    evaluation: RuleEvaluationResult,
    *,
    policies: Sequence[FindingCorrelationPolicy] | None = None,
) -> tuple[RuleEvaluationResult, FindingCorrelationResult]:
    """Correlate Findings inside a RuleEvaluationResult and rewrite findings."""

    result = correlate_findings(evaluation.findings, policies=policies)
    updated = RuleEvaluationResult.from_findings(
        findings=result.findings,  # type: ignore[arg-type]
        rules_evaluated=evaluation.rules_evaluated,
        rules_skipped=evaluation.rules_skipped,
    )
    return updated, result


_CONFIDENCE_RANK = {
    CorrelationConfidenceLevel.HIGH: 3,
    CorrelationConfidenceLevel.MODERATE: 2,
    CorrelationConfidenceLevel.LIMITED: 1,
    CorrelationConfidenceLevel.UNAVAILABLE: 0,
}


def _build_correlation(
    left: Finding,
    right: Finding,
    *,
    correlation_type: FindingCorrelationType,
    bases: tuple[FindingCorrelationBasis, ...],
    confidence_level: CorrelationConfidenceLevel,
    shared_identity: str,
    shared_evidence_ids: tuple[str, ...] = (),
    shared_subject_ids: tuple[str, ...] = (),
    policy_id: str = "",
    limitations: tuple[str, ...] = (),
    direction: CorrelationDirection = CorrelationDirection.UNDIRECTED,
    metadata: dict[str, Any] | None = None,
) -> FindingCorrelation:
    if direction is CorrelationDirection.UNDIRECTED:
        finding_ids = tuple(sorted({left.id, right.id}))
    else:
        finding_ids = (left.id, right.id)
    primary = select_primary_finding((left, right))
    locations = _shared_locations(left, right)
    heads = tuple(
        sorted(
            {
                _assessment_head_for_rule(left.rule_id),
                _assessment_head_for_rule(right.rule_id),
            }
        )
    )
    corr_id = build_correlation_id(
        correlation_type=correlation_type,
        finding_ids=finding_ids,
        direction=direction,
        shared_identity=shared_identity,
        policy_id=policy_id,
    )
    return FindingCorrelation(
        correlation_id=corr_id,
        correlation_type=correlation_type,
        finding_ids=finding_ids,
        primary_finding_id=primary.id,
        assessment_head_ids=heads,
        shared_evidence_ids=tuple(sorted(set(shared_evidence_ids))),
        shared_location_refs=locations,
        shared_subject_ids=tuple(sorted(set(shared_subject_ids))),
        confidence=CorrelationConfidence(
            level=confidence_level,
            basis=bases,
            limitations=limitations,
        ),
        basis=bases,
        direction=direction,
        limitations=limitations,
        metadata=metadata or {},
    )


def select_primary_finding(findings: Sequence[Finding]) -> Finding:
    """Display/navigation primary only — does not change member Findings."""

    return sorted(
        findings,
        key=lambda item: (
            _SEVERITY_RANK.get(item.severity, 99),
            -_finding_confidence_rank(item),
            -len(item.evidence_refs),
            item.rule_id,
            item.id,
        ),
    )[0]


def _finding_confidence_rank(finding: Finding) -> int:
    level = getattr(getattr(finding, "finding_confidence", None), "level", None)
    value = getattr(level, "value", str(level or "unavailable")).lower()
    order = {"high": 3, "moderate": 2, "limited": 1, "unavailable": 0}
    return order.get(value, 0)


def _shared_evidence_pairs(
    findings: Sequence[Finding],
) -> list[tuple[Finding, Finding, tuple[str, ...]]]:
    by_evidence: dict[str, list[Finding]] = {}
    for item in findings:
        ids = {ref.evidence_id for ref in item.evidence_refs if ref.evidence_id}
        if item.primary_evidence_id:
            ids.add(item.primary_evidence_id)
        for evidence_id in ids:
            by_evidence.setdefault(evidence_id, []).append(item)
    pairs: list[tuple[Finding, Finding, tuple[str, ...]]] = []
    seen: set[tuple[str, str]] = set()
    for evidence_id, group in by_evidence.items():
        unique = {item.id: item for item in group}
        ordered = sorted(unique.values(), key=lambda item: item.id)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                key = tuple(sorted((left.id, right.id)))
                if key in seen:
                    continue
                seen.add(key)
                left_ids = {ref.evidence_id for ref in left.evidence_refs}
                right_ids = {ref.evidence_id for ref in right.evidence_refs}
                shared = tuple(sorted(left_ids & right_ids))
                if shared:
                    pairs.append((left, right, shared))
    return pairs


def _compatible_subjects(
    left: Finding, right: Finding
) -> tuple[bool, tuple[str, ...], tuple[FindingCorrelationBasis, ...]]:
    left_idx = _subject_index(left)
    right_idx = _subject_index(right)
    bases: list[FindingCorrelationBasis] = []
    subjects: list[str] = []

    shared_keys = left_idx["config_keys"] & right_idx["config_keys"]
    shared_paths = left_idx["paths"] & right_idx["paths"]
    if shared_keys and shared_paths:
        bases.append(FindingCorrelationBasis.SAME_CONFIGURATION_KEY)
        bases.append(FindingCorrelationBasis.SAME_PATH)
        subjects.extend(f"config:{item}" for item in sorted(shared_keys))
        return True, tuple(subjects), tuple(bases)

    shared_deps = left_idx["dependencies"] & right_idx["dependencies"]
    if shared_deps:
        bases.append(FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY)
        subjects.extend(f"dep:{item}" for item in sorted(shared_deps))
        return True, tuple(subjects), tuple(bases)

    shared_symbols = left_idx["symbols"] & right_idx["symbols"]
    if shared_symbols and shared_paths:
        bases.append(FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE)
        bases.append(FindingCorrelationBasis.SAME_PATH)
        subjects.extend(f"symbol:{item}" for item in sorted(shared_symbols))
        return True, tuple(subjects), tuple(bases)

    shared_edges = left_idx["graph_edges"] & right_idx["graph_edges"]
    if shared_edges:
        bases.append(FindingCorrelationBasis.SAME_GRAPH_EDGE)
        subjects.extend(f"edge:{item}" for item in sorted(shared_edges))
        return True, tuple(subjects), tuple(bases)

    shared_nodes = left_idx["graph_nodes"] & right_idx["graph_nodes"]
    if shared_nodes:
        bases.append(FindingCorrelationBasis.SAME_GRAPH_NODE)
        subjects.extend(f"node:{item}" for item in sorted(shared_nodes))
        return True, tuple(subjects), tuple(bases)

    shared_metrics = left_idx["measurement_scopes"] & right_idx["measurement_scopes"]
    if shared_metrics and shared_paths:
        bases.append(FindingCorrelationBasis.SAME_MEASUREMENT_SCOPE_REF)
        bases.append(FindingCorrelationBasis.SAME_PATH)
        subjects.extend(f"measure:{item}" for item in sorted(shared_metrics))
        return True, tuple(subjects), tuple(bases)

    return False, (), ()


def _policy_match(
    left: Finding,
    right: Finding,
    policy: FindingCorrelationPolicy,
) -> tuple[
    bool,
    tuple[str, ...],
    tuple[FindingCorrelationBasis, ...],
    CorrelationConfidenceLevel,
    str,
]:
    left_idx = _subject_index(left)
    right_idx = _subject_index(right)
    bases: list[FindingCorrelationBasis] = []
    subjects: list[str] = []
    level = CorrelationConfidenceLevel.HIGH
    shared_identity_parts: list[str] = []

    required = set(policy.required_bases)

    if FindingCorrelationBasis.SAME_CONFIGURATION_KEY in required:
        shared = left_idx["config_keys"] & right_idx["config_keys"]
        shared_paths = left_idx["paths"] & right_idx["paths"]
        if not shared or not shared_paths:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.extend(
            (
                FindingCorrelationBasis.SAME_CONFIGURATION_KEY,
                FindingCorrelationBasis.SAME_PATH,
            )
        )
        subjects.extend(sorted(shared))
        shared_identity_parts.extend(sorted(shared))

    if FindingCorrelationBasis.SAME_PATH in required:
        shared_paths = left_idx["paths"] & right_idx["paths"]
        if not shared_paths:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        if FindingCorrelationBasis.SAME_PATH not in bases:
            bases.append(FindingCorrelationBasis.SAME_PATH)
        subjects.extend(f"path:{item}" for item in sorted(shared_paths))
        shared_identity_parts.extend(sorted(shared_paths))

    if FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE in required:
        shared_symbols = left_idx["symbols"] & right_idx["symbols"]
        if not shared_symbols:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.append(FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE)
        subjects.extend(sorted(shared_symbols))
        shared_identity_parts.extend(sorted(shared_symbols))

    if FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY in required:
        shared_deps = left_idx["dependencies"] & right_idx["dependencies"]
        if not shared_deps:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.append(FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY)
        subjects.extend(sorted(shared_deps))
        shared_identity_parts.extend(sorted(shared_deps))

    if FindingCorrelationBasis.SAME_GRAPH_EDGE in required:
        shared_edges = left_idx["graph_edges"] & right_idx["graph_edges"]
        # Fall back to symbolic edge-like subjects (source->target).
        if not shared_edges:
            shared_edges = left_idx["edge_symbols"] & right_idx["edge_symbols"]
        if not shared_edges:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.append(FindingCorrelationBasis.SAME_GRAPH_EDGE)
        subjects.extend(sorted(shared_edges))
        shared_identity_parts.extend(sorted(shared_edges))

    if FindingCorrelationBasis.SAME_GRAPH_NODE in required:
        shared_nodes = left_idx["graph_nodes"] & right_idx["graph_nodes"]
        if not shared_nodes:
            shared_nodes = left_idx["symbols"] & right_idx["symbols"]
        if not shared_nodes:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.append(FindingCorrelationBasis.SAME_GRAPH_NODE)
        subjects.extend(sorted(shared_nodes))
        shared_identity_parts.extend(sorted(shared_nodes))
        level = min_correlation_confidence(level, CorrelationConfidenceLevel.MODERATE)

    if FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP in required:
        bases.append(FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP)

    if FindingCorrelationBasis.REVIEWED_CROSS_HEAD_POLICY in required:
        if not policy.cross_head_allowed:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        bases.append(FindingCorrelationBasis.REVIEWED_CROSS_HEAD_POLICY)

    # Path-only policies without another identity are insufficient unless
    # EXPLICIT_RULE_RELATIONSHIP + SAME_PATH for reviewed pairs (TLS/hostname).
    identity_bases = set(bases) - {
        FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        FindingCorrelationBasis.REVIEWED_CROSS_HEAD_POLICY,
    }
    if identity_bases <= {FindingCorrelationBasis.SAME_PATH} and (
        FindingCorrelationBasis.SAME_CONFIGURATION_KEY not in required
        and FindingCorrelationBasis.SAME_SYMBOLIC_REFERENCE not in required
        and FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY not in required
        and FindingCorrelationBasis.SAME_GRAPH_EDGE not in required
        and FindingCorrelationBasis.SAME_GRAPH_NODE not in required
    ):
        # Allow reviewed SAME_PATH + EXPLICIT_RULE_RELATIONSHIP (transport pair).
        if FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP not in bases:
            return False, (), (), CorrelationConfidenceLevel.UNAVAILABLE, ""
        level = min_correlation_confidence(level, CorrelationConfidenceLevel.HIGH)

    return (
        True,
        tuple(sorted(set(subjects))),
        tuple(dict.fromkeys(bases)),
        level,
        "|".join(shared_identity_parts),
    )


def _subject_index(finding: Finding) -> dict[str, set[str]]:
    metadata = finding.metadata or {}
    paths: set[str] = set()
    symbols: set[str] = set()
    config_keys: set[str] = set()
    dependencies: set[str] = set()
    graph_edges: set[str] = set()
    graph_nodes: set[str] = set()
    edge_symbols: set[str] = set()
    measurement_scopes: set[str] = set()

    def _add_path(value: object | None) -> None:
        if value is None:
            return
        text = str(value).strip().replace("\\", "/").lower()
        if text and not text.startswith("/") and "://" not in text:
            paths.add(text)

    for item in finding.evidence:
        _add_path(item.path)
        source = str(item.source_id or "").strip()
        if source and not _EVIDENCE_ID_RE.match(source):
            symbols.add(source.lower())
            if "->" in source:
                edge_symbols.add(source.lower())

    for ref in finding.evidence_refs:
        location = getattr(ref, "location", None)
        if location is not None:
            _add_path(getattr(location, "path", None))
        # Legacy/alternate attribute bags (not on EvidenceRef contract).
        loc = getattr(ref, "safe_location", None) or getattr(ref, "path", None)
        _add_path(loc)
        subject = str(getattr(ref, "subject_reference", "") or "").strip()
        if subject and not _EVIDENCE_ID_RE.match(subject):
            symbols.add(subject.lower())
            if "->" in subject:
                edge_symbols.add(subject.lower())
        domain_ref = str(getattr(ref, "domain_ref", "") or "").strip()
        if domain_ref and not _EVIDENCE_ID_RE.match(domain_ref):
            symbols.add(domain_ref.lower())
            if "_" in domain_ref or domain_ref.isupper():
                config_keys.add(domain_ref.lower())
        graph = getattr(ref, "graph_ref", None)
        if graph is not None:
            for key in ("edge_id", "node_id", "unit_id", "cycle_id"):
                value = getattr(graph, key, None)
                if value:
                    token = str(value).strip().lower()
                    if "edge" in key:
                        graph_edges.add(token)
                        edge_symbols.add(token)
                    elif "cycle" in key:
                        graph_nodes.add(token)
                    else:
                        graph_nodes.add(token)
        attrs = getattr(ref, "attributes", None) or {}
        if isinstance(attrs, dict):
            for key in ("normalized_key", "key", "configuration_key"):
                if attrs.get(key):
                    config_keys.add(str(attrs[key]).strip().lower())
            for key in ("dependency_identity", "package", "coordinate"):
                if attrs.get(key):
                    dependencies.add(str(attrs[key]).strip().lower())
            if attrs.get("source") and attrs.get("target"):
                edge = f"{attrs['source']}->{attrs['target']}".lower()
                graph_edges.add(edge)
                edge_symbols.add(edge)
            for key in ("unit_id", "node_id", "component_id"):
                if attrs.get(key):
                    graph_nodes.add(str(attrs[key]).strip().lower())

    for key in ("normalized_key", "configuration_key"):
        if metadata.get(key):
            config_keys.add(str(metadata[key]).strip().lower())
    for key in ("dependency_identity", "package_identity", "coordinate"):
        if metadata.get(key):
            dependencies.add(str(metadata[key]).strip().lower())
    for key in ("graph_edge_id",):
        if metadata.get(key):
            graph_edges.add(str(metadata[key]).strip().lower())
    for key in ("graph_subject_id", "graph_node_id", "unit_id"):
        if metadata.get(key):
            graph_nodes.add(str(metadata[key]).strip().lower())
    for key in ("measurement_scope_ref", "qualified_signature", "qualified_name"):
        if metadata.get(key):
            measurement_scopes.add(str(metadata[key]).strip().lower())
            symbols.add(str(metadata[key]).strip().lower())

    raw_subjects = str(metadata.get("subject_keys") or "")
    for part in raw_subjects.split(","):
        token = part.strip().lower()
        if not token or _EVIDENCE_ID_RE.match(token):
            continue
        if "/" in token or token.endswith(
            (".py", ".ts", ".js", ".java", ".cs", ".php", ".json", ".yml", ".yaml", ".env", ".toml")
        ):
            paths.add(token)
        elif "->" in token:
            edge_symbols.add(token)
            symbols.add(token)
        else:
            symbols.add(token)
            # Heuristic: all-caps / snake config keys.
            if "_" in token or token.isupper():
                config_keys.add(token)

    return {
        "paths": paths,
        "symbols": symbols,
        "config_keys": config_keys,
        "dependencies": dependencies,
        "graph_edges": graph_edges,
        "graph_nodes": graph_nodes,
        "edge_symbols": edge_symbols,
        "measurement_scopes": measurement_scopes,
    }


def _shared_locations(left: Finding, right: Finding) -> tuple[EvidenceLocation, ...]:
    left_paths = _subject_index(left)["paths"]
    right_paths = _subject_index(right)["paths"]
    shared = sorted(left_paths & right_paths)
    locations: list[EvidenceLocation] = []
    for path in shared[:8]:
        try:
            locations.append(EvidenceLocation(path=path))
        except Exception:  # noqa: BLE001
            continue
    return tuple(locations)


def _assessment_head_for_rule(rule_id: str) -> str:
    text = rule_id.strip().lower()
    for prefix, head in (
        ("security.", "security"),
        ("dependency.", "dependency"),
        ("architecture.", "architecture"),
        ("technical_debt.", "technical_debt"),
        ("cloud.", "cloud"),
        ("ai_readiness.", "ai_readiness"),
        ("testing.", "testing"),
        ("performance.", "performance"),
    ):
        if text.startswith(prefix):
            return head
    return "other"


def _dedupe_correlations(
    correlations: Sequence[FindingCorrelation],
) -> list[FindingCorrelation]:
    by_id: dict[str, FindingCorrelation] = {}
    for item in correlations:
        existing = by_id.get(item.correlation_id)
        if existing is None:
            by_id[item.correlation_id] = item
            continue
        # Prefer higher confidence / richer basis.
        if _CONFIDENCE_RANK[item.confidence.level] > _CONFIDENCE_RANK[
            existing.confidence.level
        ]:
            by_id[item.correlation_id] = item
    return list(by_id.values())


def _build_clusters(
    correlations: Sequence[FindingCorrelation],
    by_id: dict[str, Finding],
) -> list[FindingCorrelationCluster]:
    """Connected components; do not fabricate transitive direct correlations."""

    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for item in correlations:
        # Keep coupling/boundary families from over-merging across incompatible types.
        if item.correlation_type is FindingCorrelationType.ARCHITECTURE_CLUSTER:
            # Still cluster within compatible architecture edges.
            pass
        members = item.finding_ids
        for i in range(len(members) - 1):
            union(members[i], members[i + 1])

    groups: dict[str, list[str]] = {}
    for fid in {fid for item in correlations for fid in item.finding_ids}:
        groups.setdefault(find(fid), []).append(fid)

    clusters: list[FindingCorrelationCluster] = []
    for root, members in sorted(groups.items()):
        member_ids = tuple(sorted(set(members)))
        if len(member_ids) < 2:
            continue
        corr_ids = tuple(
            sorted(
                {
                    item.correlation_id
                    for item in correlations
                    if set(item.finding_ids).issubset(set(member_ids))
                    or set(item.finding_ids) & set(member_ids)
                }
            )
        )
        findings = tuple(by_id[fid] for fid in member_ids if fid in by_id)
        if len(findings) < 2:
            continue
        primary = select_primary_finding(findings)
        heads = tuple(sorted({_assessment_head_for_rule(item.rule_id) for item in findings}))
        material = "\n".join(("cluster", *member_ids, *corr_ids))
        cluster_id = f"cluster:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"
        clusters.append(
            FindingCorrelationCluster(
                cluster_id=cluster_id,
                finding_ids=member_ids,
                correlation_ids=corr_ids,
                primary_finding_id=primary.id,
                assessment_head_ids=heads,
                limitations=(
                    "Cluster membership does not invent direct correlations "
                    "between all members.",
                ),
            )
        )
    return clusters


def _attach_correlation_refs(
    findings: Sequence[Finding],
    correlations: Sequence[FindingCorrelation],
) -> tuple[Finding, ...]:
    corr_by_finding: dict[str, list[str]] = {}
    related_by_finding: dict[str, list[str]] = {}
    for item in correlations:
        for fid in item.finding_ids:
            corr_by_finding.setdefault(fid, []).append(item.correlation_id)
            related_by_finding.setdefault(fid, []).extend(
                other for other in item.finding_ids if other != fid
            )
    updated: list[Finding] = []
    for finding in findings:
        corr_ids = tuple(sorted(set(corr_by_finding.get(finding.id, ()))))
        related = tuple(sorted(set(related_by_finding.get(finding.id, ()))))
        metadata = dict(finding.metadata)
        if corr_ids:
            metadata["correlation_ids"] = ",".join(corr_ids)
            metadata["correlated_finding_ids"] = ",".join(related)
        # Prefer additive model fields when present; always keep metadata.
        updates: dict[str, Any] = {"metadata": metadata}
        if hasattr(finding, "correlation_ids"):
            updates["correlation_ids"] = corr_ids
        if hasattr(finding, "correlated_finding_ids"):
            updates["correlated_finding_ids"] = related
        updated.append(finding.model_copy(update=updates))
    return tuple(sorted(updated, key=lambda item: (item.rule_id, item.id, item.title)))
