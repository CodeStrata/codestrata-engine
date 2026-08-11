"""Shared helpers for Architecture Intelligence SharedRules."""

from __future__ import annotations

from codestrata.application.rules.confidence_catalog import confidence_for_rule
from codestrata.application.rules.architecture.metadata import (
    dimensions_for,
    executive_for,
    taxonomy_for,
)
from codestrata.application.rules.architecture.recommendations import recommendation_for
from codestrata.domain.rules.architecture.models import ArchitectureAnalysisView, ArchitectureUnit
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
from codestrata.domain.rules.results import RuleMatch


def architecture_view(context: RuleExecutionContext) -> ArchitectureAnalysisView | None:
    raw = context.architecture_view
    if isinstance(raw, ArchitectureAnalysisView):
        return raw
    return None


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    remediation: str,
    requires_enterprise: bool = False,
    severity: RuleSeverity = RuleSeverity.MEDIUM,
) -> RuleMetadata:
    taxonomy = taxonomy_for(rule_id)
    dimensions = dimensions_for(rule_id)
    tags = (
        "architecture",
        "architecture.core",
        f"taxonomy:{taxonomy}",
        *[f"dimension:{item}" for item in dimensions],
    )
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse("1.0.0"),
        title=title,
        description=description,
        category=RuleCategory.ARCHITECTURE,
        default_severity=severity,
        confidence=confidence_for_rule(rule_id),
        supported_languages=("java", "python", "javascript", "typescript", "php", "csharp"),
        tags=tags,
        remediation_summary=remediation,
        documentation_reference="docs/analysis-intelligence/architecture/rules.md",
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=requires_enterprise,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_GRAPH_CHANGES,
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
    remediation: str | None = None,
    rule_confidence: RuleConfidence | None = None,
) -> RuleMatch:
    rec = recommendation_for(rule_id)
    remediation_text = remediation or rec.get("action") or ""
    _ = executive_for(rule_id)
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse("1.0.0"),
        severity=severity,
        confidence=confidence,
        rule_confidence=rule_confidence or confidence_for_rule(rule_id),
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation_text,
        affected_entities=subject_keys,
        provenance="architecture.core",
        subject_keys=subject_keys,
    )


def evidence_graph_edge(
    *,
    source: str,
    target: str,
    path: str | None = None,
    message: str,
    attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    attrs = {"source": source, "target": target}
    if attributes:
        attrs.update(attributes)
    return RuleEvidence(
        kind=RuleEvidenceKind.GRAPH_EDGE,
        subject_reference=f"{source}->{target}",
        message=message,
        safe_location=path,
        attributes=attrs,
        provenance="architecture_analysis_view",
    )


def evidence_unit(
    *,
    unit_id: str,
    message: str,
    path: str | None = None,
    attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.GRAPH_NODE,
        subject_reference=unit_id,
        message=message,
        safe_location=path,
        attributes=dict(attributes or {}),
        provenance="architecture_analysis_view",
    )


def min_coverage_ok(view: ArchitectureAnalysisView, *, minimum: float = 0.15) -> bool:
    """Extraction coverage + primary population safeguards."""

    extraction = view.extraction_coverage or view.coverage_ratio
    return (
        view.files_parsed >= 1
        and extraction >= minimum
        and view.primary_unit_count >= 2
    )


def classification_coverage_ok(
    view: ArchitectureAnalysisView,
    *,
    minimum: float = 0.25,
    minimum_layered: int = 2,
) -> bool:
    layered = sum(
        1
        for unit in view.primary_units()
        if unit.layer not in {"unknown", "test"}
        and unit.classification_confidence in {"medium", "high"}
    )
    return view.classification_coverage >= minimum and layered >= minimum_layered


def comparable_coupling_units(view: ArchitectureAnalysisView) -> tuple[ArchitectureUnit, ...]:
    """Units eligible for coupling comparison (exclude composition/registration/test)."""

    return tuple(
        unit
        for unit in view.primary_units()
        if unit.role == "architectural_module" and unit.layer != "test"
    )


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    """Structured metadata for Finding.metadata (report-ready, no AI prose)."""

    rec = recommendation_for(rule_id)
    exec_meta = executive_for(rule_id)
    payload = {
        "taxonomy_id": taxonomy_for(rule_id),
        "assessment_dimensions": ",".join(dimensions_for(rule_id)),
        "business_impact": "unknown",
        "pack_id": "architecture.core",
        "pack_version": "1.0.0",
        "recommendation_effort_band": rec.get("effort_band", "unknown"),
        "recommendation_validation": rec.get("validation", ""),
        "recommendation_rationale": rec.get("rationale", ""),
        "recommendation_expected_outcome": rec.get("expected_outcome", ""),
    }
    for key, value in exec_meta.items():
        payload[key if key.startswith("executive_") else f"executive_{key}"] = value
    return payload
