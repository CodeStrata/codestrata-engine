"""Security assessment inventory and hotspot projection (Phase 4.5.4).

Organizes in-memory repository-sensitive evidence and shared Security Findings
into deterministic inventories. Does not re-collect evidence, re-run rules,
synthesize conclusions, or score risk.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationKeyFamily,
    ContentClassification,
    InspectionStatus,
    PlaceholderStatus,
    SensitiveArtifactKind,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import (
    REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
)
from codestrata.domain.findings.models import Finding
from codestrata.domain.security.assessment.enums import (
    SecuritySourceRole,
    SecurityTraceabilityRelation,
)
from codestrata.domain.security.assessment.identifiers import (
    MAX_HOTSPOT_FINDING_REFS,
    MAX_SECURITY_HOTSPOTS,
    MAX_TRACEABILITY_ENTRIES,
    SECTION_ID,
    build_diagnostic_id,
    build_hotspot_id,
    build_trace_edge_id,
)
from codestrata.domain.security.assessment.models import (
    SecurityCategoryInventory,
    SecurityConfidenceInventory,
    SecurityCountBucket,
    SecurityDiagnosticRecord,
    SecurityDiagnosticsSummary,
    SecurityEvidenceSummary,
    SecurityEvidenceTypeInventory,
    SecurityFindingInventory,
    SecurityFindingReference,
    SecurityHotspot,
    SecurityHotspotInventory,
    SecurityRoleFindingInventory,
    SecurityRuleInventory,
    SecurityRuleInventoryEntry,
    SecuritySeverityInventory,
    SecurityTraceabilityEdge,
    SecurityTraceabilityIndex,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS
from codestrata.domain.security.taxonomy import SecurityCategory, coerce_security_category

_SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "informational": 1,
}

_ROLE_ORDER = {
    SecuritySourceRole.PRODUCTION: 0,
    SecuritySourceRole.TEST: 1,
    SecuritySourceRole.UNKNOWN: 2,
}


class SecurityRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact for inventory (not a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    diagnostic_messages: tuple[str, ...] = ()


def map_source_role(
    classification: str | SourceClassification | None,
    *,
    path: str | None = None,
    security_context: str | None = None,
) -> SecuritySourceRole:
    """Map evidence classification / path heuristics to inventory source roles.

    Unknown-role findings are never treated as production.
    Test and fixture paths share the ``test`` inventory role.
    Non-actionable security contexts (CI expressions, schema metadata, mocks)
    map to ``test`` or ``unknown`` so production-primary reports stay clean.
    """

    context = (security_context or "").strip().lower()
    if context in {
        "test",
        "test_fixture",
        "mock_credential",
    }:
        return SecuritySourceRole.TEST
    if context in {
        "documentation",
        "sample",
        "generated",
        "dependency_metadata",
        "build_artifact",
        "configuration_schema",
        "ci_expression",
        "unknown",
    }:
        return SecuritySourceRole.UNKNOWN

    if isinstance(classification, SourceClassification):
        raw = classification.value
    else:
        raw = (classification or "").strip().lower()
    if raw in {"source", "production"}:
        return SecuritySourceRole.PRODUCTION
    if raw in {"test", "fixture"}:
        return SecuritySourceRole.TEST
    if raw in {"generated", "unknown", "example", "vendor", "documentation", "docs"}:
        return SecuritySourceRole.UNKNOWN
    if path:
        classified = classify_source_path(path)
        if classified is SourceClassification.SOURCE:
            return SecuritySourceRole.PRODUCTION
        if classified in {SourceClassification.TEST, SourceClassification.FIXTURE}:
            return SecuritySourceRole.TEST
        return SecuritySourceRole.UNKNOWN
    return SecuritySourceRole.UNKNOWN


def enrich_finding_reference(finding: Finding) -> SecurityFindingReference:
    """Project a shared Finding into a bounded Security assessment reference."""

    category = coerce_security_category(
        finding.metadata.get("security_category")
        or finding.metadata.get("taxonomy_id")
        or SecurityCategory.UNKNOWN
    )
    path = finding.metadata.get("path")
    location = finding.metadata.get("location")
    if not path and finding.evidence:
        path = finding.evidence[0].path
    path = path.replace("\\", "/") if path else None
    if location:
        location = str(location).replace("\\", "/")
    classification = finding.metadata.get("classification")
    security_context = finding.metadata.get("security_context")
    source_role = map_source_role(
        classification,
        path=path,
        security_context=str(security_context) if security_context else None,
    )
    ids: list[str] = []
    meta_ids = finding.metadata.get("participating_evidence_ids", "")
    if meta_ids:
        ids.extend(part.strip() for part in str(meta_ids).split(",") if part.strip())
    if finding.metadata.get("evidence_id"):
        ids.append(str(finding.metadata["evidence_id"]))
    for item in finding.evidence:
        if item.source_id:
            ids.append(item.source_id)
    evidence_ids = tuple(sorted(set(ids)))
    subjects_raw = finding.metadata.get("subject_keys", "")
    affected_scope = tuple(
        part.strip() for part in str(subjects_raw).split(",") if part.strip()
    ) or tuple(item.path for item in finding.evidence if item.path)
    explanation = finding.description or finding.metadata.get("explanation")
    remediation = finding.metadata.get("remediation")
    if explanation:
        explanation = str(explanation)[:500]
    if remediation:
        remediation = str(remediation)[:500]
    return SecurityFindingReference(
        finding_id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        security_category=category,
        finding_category="security",
        source_role=source_role,
        affected_scope=affected_scope,
        severity=finding.severity.value,
        confidence=str(finding.metadata.get("confidence", "high")),
        status="visible",
        evidence_count=len(finding.evidence),
        taxonomy_ids=(category.value,),
        assessment_dimensions=("security",),
        path=path,
        location=location,
        explanation=explanation,
        remediation=remediation,
        evidence_ids=evidence_ids,
    )


def build_finding_references(
    findings: Sequence[Finding],
) -> tuple[SecurityFindingReference, ...]:
    refs = [enrich_finding_reference(finding) for finding in findings]
    return tuple(
        sorted(refs, key=lambda item: (item.rule_id, item.finding_id, item.title))
    )


def _role_finding_inventory(
    role: SecuritySourceRole,
    refs: Sequence[SecurityFindingReference],
) -> SecurityRoleFindingInventory:
    subset = [item for item in refs if item.source_role is role]
    return SecurityRoleFindingInventory(
        source_role=role,
        finding_ids=tuple(item.finding_id for item in subset),
        finding_count=len(subset),
        rule_counts=dict(sorted(Counter(item.rule_id for item in subset).items())),
        severity_counts=dict(
            sorted(Counter(item.severity for item in subset).items())
        ),
        category_counts=dict(
            sorted(
                Counter(item.security_category.value for item in subset).items()
            )
        ),
    )


def build_finding_inventory(
    refs: Sequence[SecurityFindingReference],
) -> SecurityFindingInventory:
    return SecurityFindingInventory(
        primary_source_role=SecuritySourceRole.PRODUCTION,
        production=_role_finding_inventory(SecuritySourceRole.PRODUCTION, refs),
        test=_role_finding_inventory(SecuritySourceRole.TEST, refs),
        unknown=_role_finding_inventory(SecuritySourceRole.UNKNOWN, refs),
        total_finding_count=len(refs),
    )


def build_evidence_summary(
    evidence: AggregatedRepositorySensitiveEvidence | None,
) -> SecurityEvidenceSummary:
    if evidence is None:
        return SecurityEvidenceSummary()
    coverage = evidence.coverage
    private_keys = sum(
        1
        for item in evidence.artifacts
        if ContentClassification.PRIVATE_KEY_MATERIAL in item.content_classifications
        or item.kind
        in {
            SensitiveArtifactKind.PRIVATE_KEY,
            SensitiveArtifactKind.SSH_PRIVATE_KEY,
        }
    )
    certificates = sum(
        1
        for item in evidence.artifacts
        if ContentClassification.PUBLIC_CERTIFICATE_MATERIAL
        in item.content_classifications
        or item.kind is SensitiveArtifactKind.PUBLIC_CERTIFICATE
    )
    metadata_only = sum(
        1
        for item in evidence.artifacts
        if item.inspection_status is InspectionStatus.METADATA_ONLY
    )
    credential_facts = sum(
        1
        for item in evidence.configuration_facts
        if item.key_family
        in {ConfigurationKeyFamily.CREDENTIAL, ConfigurationKeyFamily.SECRET}
    )
    env_refs = sum(
        1
        for item in evidence.configuration_facts
        if item.value_kind is ValueKind.ENVIRONMENT_REFERENCE
        or item.placeholder_status is PlaceholderStatus.ENVIRONMENT_INTERPOLATION
    )
    placeholders = sum(
        1
        for item in evidence.configuration_facts
        if item.value_kind is ValueKind.PLACEHOLDER
        or item.placeholder_status is PlaceholderStatus.PLACEHOLDER_LITERAL
    )
    roles = {
        map_source_role(item.classification, path=item.path).value
        for item in evidence.artifacts
    }
    roles |= {
        map_source_role(item.classification, path=item.path).value
        for item in evidence.configuration_facts
    }
    return SecurityEvidenceSummary(
        evidence_schema_name=evidence.schema_name
        or REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_NAME,
        evidence_schema_version=evidence.schema_version
        or REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION,
        evidence_fingerprint=evidence.evidence_fingerprint,
        collection_status=evidence.status.value,
        candidate_artifacts_discovered=coverage.candidate_files_discovered,
        artifacts_inspected=coverage.files_inspected,
        metadata_only_artifacts=metadata_only or coverage.metadata_only_files,
        private_key_signatures_observed=private_keys,
        public_certificate_signatures_observed=certificates,
        structured_files_parsed=coverage.structured_files_parsed,
        configuration_facts_collected=coverage.configuration_facts_collected,
        credential_sensitive_facts=credential_facts,
        environment_reference_facts=env_refs,
        placeholder_facts=placeholders or coverage.placeholder_facts,
        malformed_files=coverage.malformed_files,
        unsupported_binaries=coverage.unsupported_binaries,
        skipped_files=coverage.skipped_files,
        source_roles_represented=tuple(sorted(roles)),
        formats_represented=coverage.formats_represented,
        evidence_diagnostic_count=len(evidence.diagnostics),
        evidence_limitation_count=len(evidence.limitations),
    )


def build_evidence_type_inventory(
    evidence: AggregatedRepositorySensitiveEvidence | None,
) -> SecurityEvidenceTypeInventory:
    if evidence is None:
        return SecurityEvidenceTypeInventory()
    facts = evidence.configuration_facts
    return SecurityEvidenceTypeInventory(
        artifact_candidates=evidence.coverage.candidate_files_discovered,
        private_key_material=sum(
            1
            for item in evidence.artifacts
            if ContentClassification.PRIVATE_KEY_MATERIAL
            in item.content_classifications
        ),
        certificates=sum(
            1
            for item in evidence.artifacts
            if ContentClassification.PUBLIC_CERTIFICATE_MATERIAL
            in item.content_classifications
        ),
        metadata_only_keystores=sum(
            1
            for item in evidence.artifacts
            if item.kind
            in {
                SensitiveArtifactKind.KEYSTORE,
                SensitiveArtifactKind.TRUSTSTORE,
            }
            and item.inspection_status is InspectionStatus.METADATA_ONLY
        ),
        credential_configuration_facts=sum(
            1
            for item in facts
            if item.key_family
            in {ConfigurationKeyFamily.CREDENTIAL, ConfigurationKeyFamily.SECRET}
        ),
        transport_configuration_facts=sum(
            1
            for item in facts
            if item.key_family
            in {
                ConfigurationKeyFamily.TLS_VERIFICATION,
                ConfigurationKeyFamily.HOSTNAME_VERIFICATION,
            }
        ),
        authentication_configuration_facts=sum(
            1
            for item in facts
            if item.key_family is ConfigurationKeyFamily.AUTHENTICATION
        ),
        cors_configuration_facts=sum(
            1
            for item in facts
            if item.key_family is ConfigurationKeyFamily.CORS_ORIGIN
        ),
        debug_configuration_facts=sum(
            1
            for item in facts
            if item.key_family is ConfigurationKeyFamily.DEBUG
        ),
        placeholders=sum(
            1
            for item in facts
            if item.value_kind is ValueKind.PLACEHOLDER
            or item.placeholder_status is PlaceholderStatus.PLACEHOLDER_LITERAL
        ),
        environment_references=sum(
            1
            for item in facts
            if item.value_kind is ValueKind.ENVIRONMENT_REFERENCE
            or item.placeholder_status is PlaceholderStatus.ENVIRONMENT_INTERPOLATION
        ),
    )


def build_rule_inventory(
    *,
    refs: Sequence[SecurityFindingReference],
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
    execution_facts: Sequence[SecurityRuleExecutionFact] = (),
    pack_enabled: bool = True,
) -> SecurityRuleInventory:
    facts_by_id = {item.rule_id: item for item in execution_facts}
    by_rule: dict[str, list[SecurityFindingReference]] = defaultdict(list)
    for ref in refs:
        by_rule[ref.rule_id].append(ref)
    entries: list[SecurityRuleInventoryEntry] = []
    for rule_id in registered_rule_ids:
        fact = facts_by_id.get(rule_id)
        subset = by_rule.get(rule_id, [])
        executed = bool(fact.executed) if fact is not None else False
        status = (
            fact.evaluation_status
            if fact is not None
            else ("not_executed" if pack_enabled else "disabled")
        )
        entries.append(
            SecurityRuleInventoryEntry(
                rule_id=rule_id,
                enabled=pack_enabled if fact is None else fact.enabled,
                executed=executed,
                evaluation_status=status,
                finding_count=len(subset),
                production_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.PRODUCTION
                ),
                test_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.TEST
                ),
                unknown_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.UNKNOWN
                ),
                diagnostic_count=(
                    len(fact.diagnostic_messages) if fact is not None else 0
                ),
            )
        )
    for rule_id in sorted(by_rule):
        if rule_id in registered_rule_ids:
            continue
        subset = by_rule[rule_id]
        fact = facts_by_id.get(rule_id)
        entries.append(
            SecurityRuleInventoryEntry(
                rule_id=rule_id,
                enabled=True,
                executed=bool(fact.executed) if fact is not None else True,
                evaluation_status=(
                    fact.evaluation_status if fact is not None else "matched"
                ),
                finding_count=len(subset),
                production_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.PRODUCTION
                ),
                test_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.TEST
                ),
                unknown_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.UNKNOWN
                ),
                diagnostic_count=(
                    len(fact.diagnostic_messages) if fact is not None else 0
                ),
            )
        )
    return SecurityRuleInventory(
        entries=tuple(sorted(entries, key=lambda item: item.rule_id))
    )


def _count_buckets(counter: Counter[str]) -> tuple[SecurityCountBucket, ...]:
    return tuple(
        SecurityCountBucket(key=key, count=count)
        for key, count in sorted(counter.items())
    )


def build_category_inventory(
    refs: Sequence[SecurityFindingReference],
) -> SecurityCategoryInventory:
    return SecurityCategoryInventory(
        buckets=_count_buckets(
            Counter(item.security_category.value for item in refs)
        )
    )


def build_severity_inventory(
    refs: Sequence[SecurityFindingReference],
) -> SecuritySeverityInventory:
    return SecuritySeverityInventory(
        buckets=_count_buckets(Counter(item.severity for item in refs))
    )


def build_confidence_inventory(
    refs: Sequence[SecurityFindingReference],
) -> SecurityConfidenceInventory:
    return SecurityConfidenceInventory(
        buckets=_count_buckets(Counter(item.confidence for item in refs))
    )


def _highest_severity(severities: Sequence[str]) -> str:
    if not severities:
        return "informational"
    return max(severities, key=lambda item: _SEVERITY_RANK.get(item, 0))


def _hotspot_sort_key(hotspot: SecurityHotspot) -> tuple[object, ...]:
    return (
        -hotspot.production_finding_count,
        -hotspot.total_finding_count,
        -_SEVERITY_RANK.get(hotspot.highest_severity, 0),
        hotspot.path.lower(),
        hotspot.hotspot_id,
    )


def build_hotspot_inventory(
    refs: Sequence[SecurityFindingReference],
) -> SecurityHotspotInventory:
    by_path: dict[str, list[SecurityFindingReference]] = defaultdict(list)
    for ref in refs:
        path = (ref.path or "unknown").replace("\\", "/")
        by_path[path].append(ref)

    hotspots: list[SecurityHotspot] = []
    for path, subset in by_path.items():
        finding_ids = tuple(
            item.finding_id
            for item in sorted(
                subset, key=lambda item: (item.rule_id, item.finding_id)
            )
        )[:MAX_HOTSPOT_FINDING_REFS]
        hotspots.append(
            SecurityHotspot(
                hotspot_id=build_hotspot_id(path=path),
                path=path,
                label="Security finding hotspot",
                total_finding_count=len(subset),
                production_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.PRODUCTION
                ),
                test_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.TEST
                ),
                unknown_finding_count=sum(
                    1
                    for item in subset
                    if item.source_role is SecuritySourceRole.UNKNOWN
                ),
                rule_ids=tuple(sorted({item.rule_id for item in subset})),
                categories=tuple(
                    sorted({item.security_category.value for item in subset})
                ),
                highest_severity=_highest_severity(
                    [item.severity for item in subset]
                ),
                finding_ids=finding_ids,
            )
        )
    ordered = tuple(sorted(hotspots, key=_hotspot_sort_key)[:MAX_SECURITY_HOTSPOTS])
    return SecurityHotspotInventory(hotspots=ordered)


def build_diagnostics_summary(
    *,
    evidence: AggregatedRepositorySensitiveEvidence | None,
    execution_facts: Sequence[SecurityRuleExecutionFact] = (),
    assessment_diagnostics: Sequence[str] = (),
) -> SecurityDiagnosticsSummary:
    evidence_records: list[SecurityDiagnosticRecord] = []
    if evidence is not None:
        for item in evidence.diagnostics:
            evidence_records.append(
                SecurityDiagnosticRecord(
                    diagnostic_id=item.diagnostic_id
                    or build_diagnostic_id(
                        code=item.diagnostic_code, message=item.message
                    ),
                    diagnostic_code=item.diagnostic_code,
                    message=item.message[:400],
                    origin="evidence",
                    path=item.path,
                )
            )
    rule_records: list[SecurityDiagnosticRecord] = []
    for fact in execution_facts:
        for message in fact.diagnostic_messages:
            code = (
                "rule_evaluation_failure"
                if fact.evaluation_status == "failed"
                else "rule_diagnostic"
            )
            rule_records.append(
                SecurityDiagnosticRecord(
                    diagnostic_id=build_diagnostic_id(
                        code=f"{fact.rule_id}:{code}", message=message
                    ),
                    diagnostic_code=code,
                    message=message[:400],
                    origin="rule",
                    path=None,
                )
            )
    assessment_records = [
        SecurityDiagnosticRecord(
            diagnostic_id=build_diagnostic_id(code="assessment", message=message),
            diagnostic_code="assessment_diagnostic",
            message=str(message)[:400],
            origin="assessment",
        )
        for message in assessment_diagnostics
        if str(message).strip()
    ]
    return SecurityDiagnosticsSummary(
        evidence_diagnostics=tuple(
            sorted(
                evidence_records,
                key=lambda item: (item.diagnostic_code, item.diagnostic_id),
            )
        ),
        rule_diagnostics=tuple(
            sorted(
                rule_records,
                key=lambda item: (item.diagnostic_code, item.diagnostic_id),
            )
        ),
        assessment_diagnostics=tuple(
            sorted(
                assessment_records,
                key=lambda item: (item.diagnostic_code, item.diagnostic_id),
            )
        ),
    )


def build_inventory_traceability(
    *,
    pack_id: str,
    limitation_ids: Sequence[str],
    finding_refs: Sequence[SecurityFindingReference],
    hotspot_ids: Sequence[str],
) -> SecurityTraceabilityIndex:
    """Bounded assessment → finding → evidence / hotspot edges."""

    edges: list[SecurityTraceabilityEdge] = [
        SecurityTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=SecurityTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=SecurityTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for limitation_id in limitation_ids:
        edges.append(
            SecurityTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=SecurityTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=limitation_id,
                ),
                relation=SecurityTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=limitation_id,
            )
        )
    ordered_refs = sorted(
        finding_refs,
        key=lambda item: (
            _ROLE_ORDER.get(item.source_role, 9),
            item.rule_id,
            item.finding_id,
        ),
    )
    finding_budget = max(0, MAX_TRACEABILITY_ENTRIES)
    for ref in ordered_refs[:finding_budget]:
        edges.append(
            SecurityTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=SecurityTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=ref.finding_id,
                ),
                relation=SecurityTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=ref.finding_id,
            )
        )
        for evidence_id in ref.evidence_ids[:2]:
            edges.append(
                SecurityTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=SecurityTraceabilityRelation.FINDING_TO_EVIDENCE.value,
                        source_id=ref.finding_id,
                        target_id=evidence_id,
                    ),
                    relation=SecurityTraceabilityRelation.FINDING_TO_EVIDENCE,
                    source_id=ref.finding_id,
                    target_id=evidence_id,
                )
            )
    for hotspot_id in tuple(hotspot_ids)[:3]:
        edges.append(
            SecurityTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=SecurityTraceabilityRelation.SECTION_TO_HOTSPOT.value,
                    source_id=SECTION_ID,
                    target_id=hotspot_id,
                ),
                relation=SecurityTraceabilityRelation.SECTION_TO_HOTSPOT,
                source_id=SECTION_ID,
                target_id=hotspot_id,
            )
        )
    unique: dict[str, SecurityTraceabilityEdge] = {
        edge.edge_id: edge for edge in edges
    }
    ordered = tuple(sorted(unique.values(), key=lambda item: item.edge_id))
    return SecurityTraceabilityIndex(
        edges=ordered[: max(MAX_TRACEABILITY_ENTRIES * 3, 36)]
    )


def findings_by_rule_counts(
    refs: Sequence[SecurityFindingReference],
) -> dict[str, int]:
    return dict(sorted(Counter(item.rule_id for item in refs).items()))


def count_failed_rules(execution_facts: Sequence[SecurityRuleExecutionFact]) -> int:
    return sum(1 for item in execution_facts if item.evaluation_status == "failed")


def count_succeeded_rules(execution_facts: Sequence[SecurityRuleExecutionFact]) -> int:
    return sum(
        1
        for item in execution_facts
        if item.executed and item.evaluation_status != "failed"
    )


def execution_facts_from_status_map(
    status_by_rule: Mapping[str, str],
    *,
    diagnostics_by_rule: Mapping[str, Sequence[str]] | None = None,
    registered_rule_ids: Sequence[str] = HYGIENE_RULE_IDS,
) -> tuple[SecurityRuleExecutionFact, ...]:
    """Build execution facts from rule_id → status mapping (tests / orchestration)."""

    diagnostics_by_rule = diagnostics_by_rule or {}
    facts: list[SecurityRuleExecutionFact] = []
    for rule_id in registered_rule_ids:
        status = status_by_rule.get(rule_id, "not_executed")
        executed = status not in {"not_executed", "disabled", "skipped"}
        facts.append(
            SecurityRuleExecutionFact(
                rule_id=rule_id,
                enabled=status != "disabled",
                executed=executed,
                evaluation_status=status,
                diagnostic_messages=tuple(
                    str(item) for item in diagnostics_by_rule.get(rule_id, ())
                ),
            )
        )
    return tuple(sorted(facts, key=lambda item: item.rule_id))


__all__ = [
    "SecurityRuleExecutionFact",
    "build_category_inventory",
    "build_confidence_inventory",
    "build_diagnostics_summary",
    "build_evidence_summary",
    "build_evidence_type_inventory",
    "build_finding_inventory",
    "build_finding_references",
    "build_hotspot_inventory",
    "build_inventory_traceability",
    "build_rule_inventory",
    "build_severity_inventory",
    "count_failed_rules",
    "count_succeeded_rules",
    "enrich_finding_reference",
    "execution_facts_from_status_map",
    "findings_by_rule_counts",
    "map_source_role",
]
