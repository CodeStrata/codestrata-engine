"""Shared helpers for Technical Debt complexity SharedRules."""

from __future__ import annotations

from codestrata.application.rules.technical_debt.recommendations import recommendation_for
from codestrata.application.technical_debt.evidence.complexity_projection import (
    complexity_evidence_for_debt,
    complexity_taxonomy_category,
)
from codestrata.domain.evidence.language.complexity.enums import MetricAvailability
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    CallableComplexityEvidence,
    IntMetric,
    TypeComplexityEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch
from codestrata.domain.technical_debt.ids import PACK_ID, PACK_VERSION


def complexity_evidence(context: RuleExecutionContext) -> AggregatedComplexityEvidence | None:
    raw = context.complexity_evidence
    if isinstance(raw, AggregatedComplexityEvidence):
        return complexity_evidence_for_debt(raw)
    return None


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    remediation: str,
    severity: RuleSeverity = RuleSeverity.MEDIUM,
) -> RuleMetadata:
    taxonomy = complexity_taxonomy_category().value
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse("1.0.0"),
        title=title,
        description=description,
        category=RuleCategory.TECHNICAL_DEBT,
        default_severity=severity,
        supported_languages=("java", "python", "php", "csharp"),
        tags=(
            "technical_debt",
            PACK_ID,
            "complexity",
            f"taxonomy:{taxonomy}",
            "dimension:technical-debt",
        ),
        remediation_summary=remediation,
        documentation_reference=(
            "docs/analysis-intelligence/technical-debt/complexity-rules.md"
        ),
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
    confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    remediation: str | None = None,
) -> RuleMatch:
    rec = recommendation_for(rule_id)
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse("1.0.0"),
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation or rec,
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def metric_available(metric: IntMetric) -> bool:
    return metric.availability is MetricAvailability.AVAILABLE and metric.value is not None


def exceeds_threshold(metric: IntMetric, *, threshold: int) -> bool:
    """True only when the metric is available and strictly greater than threshold."""

    return metric_available(metric) and int(metric.value or 0) > threshold


SEVERITY_HIGH_MULTIPLIER = 2


def severity_for_ratio(*, value: int, threshold: int) -> RuleSeverity:
    """Deterministic severity with explicit HIGH basis.

    HIGH is emitted only when ``value > threshold * 2`` (severe exceedance).
    Basic threshold crossings (``threshold < value <= 2*threshold``) stay MEDIUM.
    """

    if value > threshold * SEVERITY_HIGH_MULTIPLIER:
        return RuleSeverity.HIGH
    return RuleSeverity.MEDIUM


def severity_basis(*, value: int, threshold: int) -> str:
    if value > threshold * SEVERITY_HIGH_MULTIPLIER:
        return f"value>{threshold}*{SEVERITY_HIGH_MULTIPLIER}"
    return f"value>{threshold}"


def evidence_callable(
    *,
    item: CallableComplexityEvidence,
    message: str,
    metric_name: str,
    metric_value: int,
    threshold: int,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.SYMBOL,
        subject_reference=item.qualified_signature,
        message=message,
        safe_location=item.path,
        line_start=item.span.line_start,
        line_end=item.span.line_end,
        attributes={
            "metric": metric_name,
            "value": str(metric_value),
            "threshold": str(threshold),
            "severity_basis": severity_basis(value=metric_value, threshold=threshold),
            "language": item.language,
            "callable_kind": item.callable_kind.value,
            "classification": item.classification.value,
            "evidence_id": item.evidence_id,
        },
        provenance="aggregated_complexity_evidence",
    )


def evidence_type(
    *,
    item: TypeComplexityEvidence,
    message: str,
    metric_name: str,
    metric_value: int,
    threshold: int,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.SYMBOL,
        subject_reference=item.qualified_name,
        message=message,
        safe_location=item.path,
        line_start=item.span.line_start,
        line_end=item.span.line_end,
        attributes={
            "metric": metric_name,
            "value": str(metric_value),
            "threshold": str(threshold),
            "severity_basis": severity_basis(value=metric_value, threshold=threshold),
            "language": item.language,
            "type_kind": item.type_kind.value,
            "classification": item.classification.value,
            "evidence_id": item.evidence_id,
        },
        provenance="aggregated_complexity_evidence",
    )


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    return {
        "taxonomy_id": complexity_taxonomy_category().value,
        "assessment_dimensions": "technical-debt",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "recommendation_effort_band": "unknown",
        "recommendation_validation": "static_evidence_only",
        "recommendation_rationale": recommendation_for(rule_id),
        "recommendation_expected_outcome": (
            "Reduce structural complexity below configured thresholds"
        ),
    }
