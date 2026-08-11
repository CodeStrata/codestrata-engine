"""Shared helpers for Performance Hygiene SharedRules (Phase 4.9.3)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.confidence_catalog import confidence_for_rule
from codestrata.domain.evidence.repository_performance.enums import (
    EvidenceConfirmationLevel,
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.models import (
    AggregatedRepositoryPerformanceEvidence,
    PerformanceBlockingFactEvidence,
    PerformanceCachingFactEvidence,
    PerformanceConcurrencyFactEvidence,
    PerformanceConfigurationFactEvidence,
    PerformanceDataAccessFactEvidence,
    PerformanceFrontendFactEvidence,
    PerformanceObservabilityFactEvidence,
    PerformanceResourceFactEvidence,
)
from codestrata.domain.performance.ids import (
    PACK_ID,
    PACK_VERSION,
    RULE_BLOCKING_SLEEP,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_CONFIG_CONTROLS,
    RULE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_EXECUTOR_CONFIG,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_LIMITED_CONTROLS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_OBSERVABILITY,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_SYNC_IO,
    RULE_VERSION,
    RULE_WITHOUT_OBSERVABILITY,
)
from codestrata.domain.performance.taxonomy import PerformanceCategory
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    MatchEvidenceConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.rule_confidence import RuleConfidence
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult

_PROVENANCE = "aggregated_repository_performance_evidence"
_MAX_PATH_EVIDENCE = 12

_SYNC_IO_KINDS = frozenset(
    {
        PerformanceBlockingKind.SYNC_HTTP_CLIENT,
        PerformanceBlockingKind.BLOCKING_DB_CALL,
        PerformanceBlockingKind.BLOCKING_FILE_IO,
    }
)

_EXECUTOR_CONCURRENCY_KINDS = frozenset(
    {
        PerformanceConcurrencyKind.EXECUTOR_SERVICE,
        PerformanceConcurrencyKind.VIRTUAL_THREADS,
    }
)

_EXECUTOR_CONFIG_KINDS = frozenset(
    {
        PerformanceConfigurationKind.THREAD_POOL,
        PerformanceConfigurationKind.EXECUTOR_CONFIG,
    }
)

_DATA_ACCESS_CONTROL_KINDS = frozenset(
    {
        PerformanceConfigurationKind.DATASOURCE_CONFIG,
        PerformanceConfigurationKind.TIMEOUT_CONFIG,
    }
)

_FRONTEND_BUNDLE_KINDS = frozenset(
    {
        PerformanceFrontendKind.WEBPACK,
        PerformanceFrontendKind.VITE,
        PerformanceFrontendKind.BUNDLE_CONFIG,
    }
)

_FRONTEND_LAZY_KINDS = frozenset(
    {
        PerformanceFrontendKind.LAZY_LOADING,
        PerformanceFrontendKind.CODE_SPLITTING,
    }
)

PerformanceFact = (
    PerformanceDataAccessFactEvidence
    | PerformanceBlockingFactEvidence
    | PerformanceCachingFactEvidence
    | PerformanceConcurrencyFactEvidence
    | PerformanceResourceFactEvidence
    | PerformanceFrontendFactEvidence
    | PerformanceObservabilityFactEvidence
    | PerformanceConfigurationFactEvidence
)


def repository_performance_evidence(
    context: RuleExecutionContext,
) -> AggregatedRepositoryPerformanceEvidence | None:
    raw = context.repository_performance_evidence
    if isinstance(raw, AggregatedRepositoryPerformanceEvidence):
        return raw
    return None


def evidence_is_usable(
    evidence: AggregatedRepositoryPerformanceEvidence | None,
) -> bool:
    if evidence is None:
        return False
    if evidence.status in {
        RepositoryPerformanceParseStatus.NOT_APPLICABLE,
        RepositoryPerformanceParseStatus.SKIPPED,
        RepositoryPerformanceParseStatus.FAILED,
        RepositoryPerformanceParseStatus.INSUFFICIENT_EVIDENCE,
    }:
        return False
    if evidence.status not in {
        RepositoryPerformanceParseStatus.SUCCEEDED,
        RepositoryPerformanceParseStatus.PARTIALLY_SUCCEEDED,
    }:
        return False
    return bool(
        evidence.file_candidates
        or evidence.data_access_facts
        or evidence.blocking_operations_facts
        or evidence.caching_facts
        or evidence.concurrency_async_facts
        or evidence.resource_management_facts
        or evidence.frontend_performance_facts
        or evidence.observability_profiling_facts
        or evidence.configuration_controls_facts
    )


def known_data_access_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceDataAccessKind, ...]:
    values = {
        item.kind
        for item in evidence.data_access_facts
        if item.kind is not PerformanceDataAccessKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_blocking_sleep_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceBlockingKind, ...]:
    values = {
        item.kind
        for item in evidence.blocking_operations_facts
        if item.kind is PerformanceBlockingKind.THREAD_SLEEP
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_sync_io_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceBlockingKind, ...]:
    values = {
        item.kind for item in evidence.blocking_operations_facts if item.kind in _SYNC_IO_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_caching_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceCachingKind, ...]:
    values = {
        item.kind
        for item in evidence.caching_facts
        if item.kind is not PerformanceCachingKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_concurrency_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceConcurrencyKind, ...]:
    values = {
        item.kind
        for item in evidence.concurrency_async_facts
        if item.kind is not PerformanceConcurrencyKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_executor_concurrency_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceConcurrencyKind, ...]:
    values = {
        item.kind
        for item in evidence.concurrency_async_facts
        if item.kind in _EXECUTOR_CONCURRENCY_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_executor_config_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceConfigurationKind, ...]:
    values = {
        item.kind
        for item in evidence.configuration_controls_facts
        if item.kind in _EXECUTOR_CONFIG_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_resource_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceResourceKind, ...]:
    values = {
        item.kind
        for item in evidence.resource_management_facts
        if item.kind is not PerformanceResourceKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_frontend_bundle_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceFrontendKind, ...]:
    values = {
        item.kind
        for item in evidence.frontend_performance_facts
        if item.kind in _FRONTEND_BUNDLE_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_frontend_lazy_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceFrontendKind, ...]:
    values = {
        item.kind
        for item in evidence.frontend_performance_facts
        if item.kind in _FRONTEND_LAZY_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_frontend_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceFrontendKind, ...]:
    values = {
        item.kind
        for item in evidence.frontend_performance_facts
        if item.kind is not PerformanceFrontendKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_observability_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceObservabilityKind, ...]:
    values = {
        item.kind
        for item in evidence.observability_profiling_facts
        if item.kind is not PerformanceObservabilityKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_configuration_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceConfigurationKind, ...]:
    values = {
        item.kind
        for item in evidence.configuration_controls_facts
        if item.kind is not PerformanceConfigurationKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_data_access_control_kinds(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[PerformanceConfigurationKind, ...]:
    values = {
        item.kind
        for item in evidence.configuration_controls_facts
        if item.kind in _DATA_ACCESS_CONTROL_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def active_families(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> tuple[str, ...]:
    families: list[str] = []
    if known_data_access_kinds(evidence):
        families.append("data_access")
    if known_blocking_sleep_kinds(evidence) or known_sync_io_kinds(evidence):
        families.append("blocking_operations")
    if known_caching_kinds(evidence):
        families.append("caching")
    if known_concurrency_kinds(evidence):
        families.append("concurrency_async")
    if known_resource_kinds(evidence):
        families.append("resource_management")
    if known_frontend_kinds(evidence):
        families.append("frontend_performance")
    if known_observability_kinds(evidence):
        families.append("observability_profiling")
    if known_configuration_kinds(evidence):
        families.append("configuration_controls")
    return tuple(sorted(families))


def performance_assets_present(
    evidence: AggregatedRepositoryPerformanceEvidence,
) -> bool:
    """True when non-config performance signal families are present."""

    return bool(
        known_data_access_kinds(evidence)
        or known_blocking_sleep_kinds(evidence)
        or known_sync_io_kinds(evidence)
        or known_caching_kinds(evidence)
        or known_concurrency_kinds(evidence)
        or known_resource_kinds(evidence)
        or known_frontend_kinds(evidence)
        or known_observability_kinds(evidence)
    )


def confidence_from_levels(
    levels: Sequence[EvidenceConfirmationLevel],
) -> MatchEvidenceConfidence:
    if any(level is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED for level in levels):
        return MatchEvidenceConfidence.HIGH
    if any(
        level
        in {
            EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            EvidenceConfirmationLevel.DECLARED,
            EvidenceConfirmationLevel.CONFIGURED,
        }
        for level in levels
    ):
        return MatchEvidenceConfidence.MEDIUM
    return MatchEvidenceConfidence.LOW


def observation_note(rule_id: str) -> str:
    return (
        "Observation only: review the repository performance evidence facts for "
        f"{rule_id}. This finding does not prescribe a remediation."
    )


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    severity: RuleSeverity = RuleSeverity.INFORMATIONAL,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.PERFORMANCE,
        default_severity=severity,
        confidence=confidence_for_rule(rule_id),
        supported_languages=(),
        tags=("performance", PACK_ID, "hygiene", "dimension:performance"),
        remediation_summary=observation_note(rule_id),
        documentation_reference=("docs/analysis-intelligence/shared-rule-platform.md"),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: MatchEvidenceConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    rule_confidence: RuleConfidence | None = None,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        rule_confidence=rule_confidence or confidence_for_rule(rule_id),
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=observation_note(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_summary(
    *,
    rule_id: str,
    message: str,
    performance_category: PerformanceCategory,
    attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    attrs = {
        "performance_category": performance_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.REPOSITORY_FACT,
        subject_reference=f"{rule_id}:summary",
        message=message,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def evidence_path(
    *,
    evidence_id: str,
    path: str,
    message: str,
    performance_category: PerformanceCategory,
    attributes: dict[str, str] | None = None,
    line_start: int | None = None,
) -> RuleEvidence:
    attrs = {
        "evidence_id": evidence_id,
        "path": path,
        "performance_category": performance_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=evidence_id,
        message=message,
        safe_location=path,
        line_start=line_start,
        line_end=line_start,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def path_evidence_from_facts(
    *,
    facts: Sequence[PerformanceFact],
    performance_category: PerformanceCategory,
    label: str,
) -> tuple[RuleEvidence, ...]:
    ordered = sorted(facts, key=lambda item: (item.path, item.evidence_id))
    items: list[RuleEvidence] = []
    for fact in ordered[:_MAX_PATH_EVIDENCE]:
        line = fact.line_hints[0] if fact.line_hints else None
        items.append(
            evidence_path(
                evidence_id=fact.evidence_id,
                path=fact.path,
                message=f"{label}; confirmation={fact.confirmation_level.value}",
                performance_category=performance_category,
                attributes={
                    "confirmation_level": fact.confirmation_level.value,
                    "detail": (fact.detail or "")[:200],
                },
                line_start=line,
            )
        )
    return tuple(items)


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    category = category_for_rule(rule_id)
    return {
        "taxonomy_id": category.value,
        "performance_category": category.value,
        "assessment_dimensions": "performance",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "observation_only": "true",
    }


def category_for_rule(rule_id: str) -> PerformanceCategory:
    mapping = {
        RULE_DATA_ACCESS: PerformanceCategory.INEFFICIENT_DATA_ACCESS,
        RULE_MULTIPLE_DATA_ACCESS: PerformanceCategory.INEFFICIENT_DATA_ACCESS,
        RULE_DATA_ACCESS_WITHOUT_BATCHING: PerformanceCategory.BATCHING_PAGINATION,
        RULE_BLOCKING_SLEEP: PerformanceCategory.BLOCKING_OPERATIONS,
        RULE_SYNC_IO: PerformanceCategory.BLOCKING_OPERATIONS,
        RULE_CACHING: PerformanceCategory.CACHING,
        RULE_DATA_WITHOUT_CACHING: PerformanceCategory.CACHING,
        RULE_CONCURRENCY: PerformanceCategory.CONCURRENCY,
        RULE_EXECUTOR_CONFIG: PerformanceCategory.CONCURRENCY,
        RULE_CONCURRENCY_WITHOUT_CONFIG: PerformanceCategory.CONCURRENCY,
        RULE_RESOURCE_MGMT: PerformanceCategory.RESOURCE_MANAGEMENT,
        RULE_RESOURCES_WITHOUT_MGMT: PerformanceCategory.RESOURCE_MANAGEMENT,
        RULE_FRONTEND_BUNDLE: PerformanceCategory.FRONTEND_RENDERING_BUNDLE,
        RULE_FRONTEND_LAZY: PerformanceCategory.FRONTEND_RENDERING_BUNDLE,
        RULE_FRONTEND_LIMITED: PerformanceCategory.FRONTEND_RENDERING_BUNDLE,
        RULE_OBSERVABILITY: PerformanceCategory.OBSERVABILITY_PROFILING,
        RULE_WITHOUT_OBSERVABILITY: PerformanceCategory.OBSERVABILITY_PROFILING,
        RULE_CONFIG_CONTROLS: PerformanceCategory.CONFIGURATION_CONTROLS,
        RULE_BROAD_FOUNDATIONS: PerformanceCategory.MISCELLANEOUS,
        RULE_LIMITED_CONTROLS: PerformanceCategory.MISCELLANEOUS,
    }
    return mapping.get(rule_id, PerformanceCategory.UNKNOWN)


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    str(item.rule_id),
                    tuple(item.subject_keys),
                    item.title,
                    item.summary,
                ),
            )
        )
    )
