"""Adapt AiReadinessAssessmentSection into presentation AiReadinessReportSection.

Phase 4.8.6 — presentation only. Does not recollect evidence, rerun rules,
rebuild inventories, or regenerate synthesis.
"""

from __future__ import annotations

from codestrata.domain.ai_readiness.assessment.enums import AiReadinessAssessmentStatus
from codestrata.domain.ai_readiness.assessment.models import AiReadinessAssessmentSection
from codestrata.domain.ai_readiness.synthesis.enums import AiReadinessRecommendationKind
from codestrata.reporting.ai_readiness.models import (
    AI_READINESS_REPORT_SECTION_ID,
    AI_READINESS_REPORT_SECTION_VERSION,
    CAPABILITY_FAMILY_DISPLAY_LIMIT,
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_ID_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    RECOMMENDATION_DISPLAY_LIMIT,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
    AiReadinessReportCapabilityFamilyEntry,
    AiReadinessReportCapabilityFamilySummary,
    AiReadinessReportConclusionView,
    AiReadinessReportCountBucket,
    AiReadinessReportCoverageAreaView,
    AiReadinessReportCoverageSummary,
    AiReadinessReportDiagnosticView,
    AiReadinessReportExecutionSummary,
    AiReadinessReportInventorySummary,
    AiReadinessReportLimitationView,
    AiReadinessReportRecommendationGroup,
    AiReadinessReportRecommendationView,
    AiReadinessReportRuleEntryView,
    AiReadinessReportSection,
    AiReadinessReportThemeView,
    AiReadinessReportTraceabilityView,
    AiReadinessReportTraceEdgeView,
)

_STATUS_LABELS = {
    AiReadinessAssessmentStatus.NOT_REQUESTED: "Not requested",
    AiReadinessAssessmentStatus.DISABLED: "Disabled",
    AiReadinessAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    AiReadinessAssessmentStatus.SUCCEEDED: "Succeeded",
    AiReadinessAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    AiReadinessAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    AiReadinessAssessmentStatus.DISABLED: (
        "AI Readiness analysis was disabled for this assessment."
    ),
    AiReadinessAssessmentStatus.NOT_APPLICABLE: (
        "No applicable AI Readiness assessment was produced for this repository."
    ),
    AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "AI Readiness reporting is limited because required "
        "repository-ai-readiness evidence was unavailable or insufficient."
    ),
    AiReadinessAssessmentStatus.SUCCEEDED: (
        "AI Readiness assessment completed using supported "
        "repository-ai-readiness evidence and hygiene rules."
    ),
    AiReadinessAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "AI Readiness assessment produced usable results with partial evidence "
        "or rule evaluation limitations."
    ),
    AiReadinessAssessmentStatus.FAILED: (
        "AI Readiness assessment could not be assembled successfully."
    ),
    AiReadinessAssessmentStatus.NOT_REQUESTED: ("AI Readiness assessment was not requested."),
}

_FORBIDDEN = (
    "ai ready",
    "is ai ready",
    "are ai ready",
    "agent ready",
    "agent-ready",
    "rag ready",
    "rag-ready",
    "fully ai-enabled",
    "fully ai enabled",
    "production ready",
    "modernize",
    "modernisation",
    "modernization path",
    "readiness score",
    "readiness grade",
    "implement rag",
    "migrate to",
    "no ai issues",
)

_REC_GROUPS = {
    AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS.value: (
        "AI readiness signals"
    ),
    AiReadinessRecommendationKind.REVIEW_DOCUMENTATION_MATURITY_SIGNALS.value: (
        "AI readiness signals"
    ),
    AiReadinessRecommendationKind.REVIEW_DATA_AND_RETRIEVAL_SIGNALS.value: ("AI readiness signals"),
    AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS.value: ("AI readiness signals"),
    AiReadinessRecommendationKind.REVIEW_MCP_AND_TOOL_SIGNALS.value: ("AI readiness signals"),
    AiReadinessRecommendationKind.REVIEW_WORKFLOW_AND_AGENT_SIGNALS.value: ("AI readiness signals"),
    AiReadinessRecommendationKind.REVIEW_OBSERVABILITY_AND_GOVERNANCE_SIGNALS.value: (
        "AI readiness signals"
    ),
    AiReadinessRecommendationKind.REVIEW_BROAD_AI_ENABLEMENT.value: ("Foundations and coverage"),
    AiReadinessRecommendationKind.REVIEW_LIMITED_SUPPORTING_FOUNDATIONS.value: (
        "Foundations and coverage"
    ),
    AiReadinessRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE.value: (
        "Scope acknowledgements"
    ),
    AiReadinessRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE.value: (
        "Scope acknowledgements"
    ),
}

_GROUP_ORDER = (
    "AI readiness signals",
    "Foundations and coverage",
    "Scope acknowledgements",
)


def _safe(text: str) -> str:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish that the repository is ai ready", "")
        .replace("do not establish that the repository is ai ready", "")
        .replace("does not mean the repository is ai ready", "")
        .replace("the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("do not establish ai readiness", "")
        .replace("without claiming ai readiness", "")
        .replace("from claiming ai readiness", "")
        .replace("claiming ai readiness", "")
        .replace("not readiness scores", "")
        .replace("readiness scoring", "")
        .replace("readiness scores", "")
        .replace("zero findings does not mean", "")
        .replace("does not claim ai usage is absent", "")
        .replace("suitable for rag", "")
        .replace("is ai ready", "")
        .replace("are ai ready", "")
        .replace("not ai ready", "")
        .replace("ai readiness", "")
        .replace("agent ready", "")
        .replace("agent-ready", "")
    )
    for phrase in _FORBIDDEN:
        if phrase in sanitized:
            raise ValueError(f"forbidden report wording: {phrase}")
    return text


class AiReadinessReportAdapter:
    """Single boundary from AI Readiness assessment domain to report presentation."""

    def adapt(
        self,
        section: AiReadinessAssessmentSection,
        *,
        include_executive_summary: bool = True,
        include_coverage: bool = True,
        include_inventory: bool = True,
        include_execution_summary: bool = True,
        include_themes: bool = True,
        include_conclusions: bool = True,
        include_recommendations: bool = True,
        include_diagnostics: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        theme_limit: int = THEME_DISPLAY_LIMIT,
        conclusion_limit: int = CONCLUSION_DISPLAY_LIMIT,
        recommendation_limit: int = RECOMMENDATION_DISPLAY_LIMIT,
        finding_id_limit: int = FINDING_ID_DISPLAY_LIMIT,
        diagnostic_limit: int = DIAGNOSTIC_DISPLAY_LIMIT,
        limitation_limit: int = LIMITATION_DISPLAY_LIMIT,
        capability_family_limit: int = CAPABILITY_FAMILY_DISPLAY_LIMIT,
    ) -> AiReadinessReportSection:
        synthesis_status = section.synthesis.status.value
        include_synth_projection = synthesis_status not in {
            "not_requested",
            "disabled",
            "failed",
        }

        inventory = (
            _inventory(section, finding_id_limit=finding_id_limit)
            if include_inventory
            else AiReadinessReportInventorySummary()
        )
        coverage = _coverage(section) if include_coverage else AiReadinessReportCoverageSummary()
        execution = (
            _execution(section)
            if include_execution_summary
            else AiReadinessReportExecutionSummary()
        )
        capability_families = (
            _capability_families(section, limit=capability_family_limit)
            if include_inventory
            else AiReadinessReportCapabilityFamilySummary()
        )
        themes = (
            _themes(section, limit=theme_limit)
            if include_themes and include_synth_projection
            else ()
        )
        conclusions = (
            _conclusions(section, limit=conclusion_limit)
            if include_conclusions and include_synth_projection
            else ()
        )
        recommendations, recommendation_groups = (
            _recommendations(section, limit=recommendation_limit)
            if include_recommendations and include_synth_projection
            else ((), ())
        )
        diagnostics = _diagnostics(section, limit=diagnostic_limit) if include_diagnostics else ()
        limitations = _limitations(section, limit=limitation_limit) if include_limitations else ()
        traceability = (
            _traceability(section, finding_id_limit=finding_id_limit)
            if include_traceability
            else AiReadinessReportTraceabilityView(summary="Traceability not included.")
        )
        posture = section.synthesis.overall_posture_summary or section.metadata.get(
            "overall_posture_summary", ""
        )
        executive = (
            _executive_summary(section, posture=posture)
            if include_executive_summary
            else section.status.value
        )
        return AiReadinessReportSection(
            section_id=AI_READINESS_REPORT_SECTION_ID,
            section_version=AI_READINESS_REPORT_SECTION_VERSION,
            title="AI Readiness Intelligence",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(section.status, section.status.value),
            assessment_status=section.status.value,
            synthesis_status=synthesis_status,
            assessment_scope=(
                f"Repository-level AI Readiness Hygiene assessment for {section.repository_id}"
            ),
            repository_name=section.repository_id,
            ai_readiness_pack_id=section.ai_readiness_pack_id,
            ai_readiness_pack_version=section.ai_readiness_pack_version,
            overall_posture_summary=_safe(posture) if posture else "",
            executive_summary=_safe(executive),
            coverage_summary=coverage,
            execution_summary=execution,
            inventory_summary=inventory,
            capability_family_summary=capability_families,
            themes=themes,
            themes_displayed=len(themes),
            themes_total=len(section.themes),
            conclusions=conclusions,
            conclusions_displayed=len(conclusions),
            conclusions_total=len(section.conclusions),
            recommendations=recommendations,
            recommendation_groups=recommendation_groups,
            recommendations_displayed=len(recommendations),
            recommendations_total=len(section.recommendations),
            diagnostics=diagnostics,
            diagnostics_displayed=len(diagnostics),
            diagnostics_total=len(section.diagnostics) + len(section.synthesis.diagnostics),
            limitations=limitations,
            limitations_displayed=len(limitations),
            limitations_total=len(section.limitations),
            traceability=traceability,
            generated_from_assessment_section_version=section.section_version,
            metadata={
                "assessment_section_id": section.section_id,
                "evidence_pipeline": section.evidence_pipeline,
                "finding_count": str(inventory.finding_count),
                "families_observed": str(capability_families.families_observed),
                "theme_limit": str(theme_limit),
                "finding_id_display_limit": str(finding_id_limit),
                "diagnostic_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(
    section: AiReadinessAssessmentSection,
    *,
    posture: str,
) -> str:
    if section.status is AiReadinessAssessmentStatus.DISABLED:
        return (
            "AI Readiness reporting is available, but AI Readiness analysis "
            "was disabled for this assessment."
        )
    if section.status is AiReadinessAssessmentStatus.NOT_REQUESTED:
        return "AI Readiness assessment was not requested for this run."
    if section.status is AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "AI Readiness reporting is limited because the required "
            "repository-ai-readiness evidence was unavailable or insufficient."
        )
    if section.status is AiReadinessAssessmentStatus.FAILED:
        return (
            "AI Readiness assessment output is unavailable because analysis "
            "did not complete successfully."
        )
    if section.status is AiReadinessAssessmentStatus.NOT_APPLICABLE:
        return "No applicable AI Readiness assessment content was produced for this repository."

    parts: list[str] = []
    if posture:
        parts.append(posture)
    else:
        count = section.finding_inventory.finding_count
        executed = section.execution_summary.rules_executed
        if count == 0:
            parts.append(
                f"The supported AI Readiness Hygiene rules executed ({executed}) "
                "and emitted no findings within the available evidence scope. "
                "This result does not establish that the repository is ai ready."
            )
        else:
            parts.append(
                "The supported AI Readiness Hygiene assessment identified "
                f"{count} finding{'' if count == 1 else 's'} from "
                "repository-ai-readiness evidence."
            )

    if section.synthesis.status.value == "failed":
        parts.append(
            "AI Readiness synthesis is unavailable for this report; inventory "
            "and execution projections remain."
        )
    elif section.synthesis.status.value in {"not_requested", "disabled"}:
        parts.append(
            "AI Readiness synthesis was not included; this report projects "
            "inventory and execution facts only."
        )
    elif section.synthesis.status.value == "empty":
        parts.append(
            "AI Readiness synthesis produced an empty inventory outcome within "
            "the supported evidence scope."
        )

    return " ".join(parts).strip()


def _buckets(counts: dict[str, int]) -> tuple[AiReadinessReportCountBucket, ...]:
    return tuple(
        AiReadinessReportCountBucket(key=key, count=count) for key, count in sorted(counts.items())
    )


def _inventory(
    section: AiReadinessAssessmentSection,
    *,
    finding_id_limit: int,
) -> AiReadinessReportInventorySummary:
    inventory = section.finding_inventory
    finding_ids = tuple(inventory.finding_ids)[:finding_id_limit]
    none_detected = None
    if inventory.finding_count == 0:
        none_detected = (
            "No AI Readiness Hygiene findings were emitted within the supported "
            "repository evidence scope. This does not establish that the "
            "repository is ai ready."
        )
        _safe(none_detected)
    return AiReadinessReportInventorySummary(
        finding_count=inventory.finding_count,
        finding_ids=finding_ids,
        finding_ids_displayed=len(finding_ids),
        by_rule=_buckets(inventory.rule_counts),
        by_severity=_buckets(inventory.severity_counts),
        by_confidence=_buckets(inventory.confidence_counts),
        none_detected_statement=none_detected,
    )


def _capability_families(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> AiReadinessReportCapabilityFamilySummary:
    inventory = section.capability_family_inventory
    entries = tuple(
        AiReadinessReportCapabilityFamilyEntry(
            family_id=item.family_id,
            observed=item.observed,
            finding_count=item.finding_count,
            finding_ids=item.finding_ids[:FINDING_ID_DISPLAY_LIMIT],
            signals=item.signals,
        )
        for item in sorted(inventory.entries, key=lambda entry: entry.family_id)[:limit]
    )
    return AiReadinessReportCapabilityFamilySummary(
        families_observed=inventory.families_observed,
        families_total=inventory.families_total,
        entries=entries,
    )


def _coverage(section: AiReadinessAssessmentSection) -> AiReadinessReportCoverageSummary:
    areas = tuple(
        AiReadinessReportCoverageAreaView(
            area_id=item.area_id,
            status=item.status.value,
            numerator=item.numerator,
            denominator=item.denominator,
            maturity=item.maturity.value,
        )
        for item in sorted(section.coverage.areas, key=lambda area: area.area_id)
    )
    return AiReadinessReportCoverageSummary(
        evidence_pipeline=section.evidence_pipeline,
        evidence_status=section.metadata.get("evidence_status", ""),
        areas=areas,
    )


def _execution(
    section: AiReadinessAssessmentSection,
) -> AiReadinessReportExecutionSummary:
    summary = section.execution_summary
    entries = tuple(
        AiReadinessReportRuleEntryView(
            rule_id=item.rule_id,
            enabled=item.enabled,
            executed=item.executed,
            evaluation_status=item.evaluation_status,
            finding_count=item.finding_count,
        )
        for item in sorted(section.rule_inventory.entries, key=lambda entry: entry.rule_id)
    )
    return AiReadinessReportExecutionSummary(
        rules_planned=summary.ai_readiness_rules_planned,
        rules_executed=summary.rules_executed,
        rules_matched=summary.rules_matched,
        rules_not_matched=summary.rules_not_matched,
        rules_not_applicable=summary.rules_not_applicable,
        rules_failed=summary.rules_failed,
        total_finding_count=summary.total_finding_count,
        theme_count=summary.theme_count,
        conclusion_count=summary.conclusion_count,
        recommendation_count=summary.recommendation_count,
        entries=entries,
    )


def _themes(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> tuple[AiReadinessReportThemeView, ...]:
    ordered = sorted(
        section.themes,
        key=lambda item: (item.ordering_key or item.kind.value, item.theme_id),
    )[:limit]
    return tuple(
        AiReadinessReportThemeView(
            theme_id=item.theme_id,
            kind=item.kind.value,
            title=item.title,
            summary=item.description,
            scope=item.scope.value,
            finding_count=len(item.finding_ids),
            finding_ids=item.finding_ids,
            rule_ids=item.rule_ids,
        )
        for item in ordered
    )


def _conclusions(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> tuple[AiReadinessReportConclusionView, ...]:
    ordered = sorted(
        section.conclusions,
        key=lambda item: (item.kind.value, item.conclusion_id),
    )[:limit]
    return tuple(
        AiReadinessReportConclusionView(
            conclusion_id=item.conclusion_id,
            kind=item.kind.value,
            audience=item.audience.value,
            title=item.title,
            summary=item.summary,
            confidence=item.confidence,
            theme_ids=item.theme_ids,
            finding_ids=item.finding_ids,
            finding_count=len(item.finding_ids),
            recommendation_ids=item.recommendation_ids,
        )
        for item in ordered
    )


def _recommendations(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> tuple[
    tuple[AiReadinessReportRecommendationView, ...],
    tuple[AiReadinessReportRecommendationGroup, ...],
]:
    ordered = sorted(
        section.recommendations,
        key=lambda item: (item.kind.value, item.recommendation_id),
    )[:limit]
    views = tuple(
        AiReadinessReportRecommendationView(
            recommendation_id=item.recommendation_id,
            kind=item.kind.value,
            title=item.title,
            action=item.action,
            rationale=item.rationale,
            audience=item.audience.value,
            presentation_group=_REC_GROUPS.get(item.kind.value, "AI readiness signals"),
            conclusion_ids=item.conclusion_ids,
            finding_ids=item.finding_ids,
            rule_ids=item.rule_ids,
            conditional=item.conditional,
        )
        for item in ordered
    )
    by_group: dict[str, list[AiReadinessReportRecommendationView]] = {
        name: [] for name in _GROUP_ORDER
    }
    for view in views:
        by_group.setdefault(view.presentation_group, []).append(view)
    groups = tuple(
        AiReadinessReportRecommendationGroup(
            group=name,
            recommendations=tuple(by_group[name]),
        )
        for name in _GROUP_ORDER
        if by_group.get(name)
    )
    extras = tuple(
        AiReadinessReportRecommendationGroup(group=name, recommendations=tuple(items))
        for name, items in sorted(by_group.items())
        if name not in _GROUP_ORDER and items
    )
    return views, groups + extras


def _diagnostics(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> tuple[AiReadinessReportDiagnosticView, ...]:
    records: list[AiReadinessReportDiagnosticView] = []
    for index, message in enumerate(section.diagnostics):
        records.append(
            AiReadinessReportDiagnosticView(
                diagnostic_id=f"assessment:{index}",
                origin="assessment",
                diagnostic_code="assessment_diagnostic",
                message=str(message)[:400],
            )
        )
    for index, message in enumerate(section.synthesis.diagnostics):
        records.append(
            AiReadinessReportDiagnosticView(
                diagnostic_id=f"synthesis:{index}",
                origin="synthesis",
                diagnostic_code="synthesis_diagnostic",
                message=str(message)[:400],
            )
        )
    ordered = sorted(
        records,
        key=lambda item: (item.origin, item.diagnostic_code, item.diagnostic_id),
    )
    return tuple(ordered[:limit])


def _limitations(
    section: AiReadinessAssessmentSection,
    *,
    limit: int,
) -> tuple[AiReadinessReportLimitationView, ...]:
    seen: set[str] = set()
    views: list[AiReadinessReportLimitationView] = []
    for item in sorted(section.limitations, key=lambda lim: lim.limitation_id):
        if item.summary in seen:
            continue
        seen.add(item.summary)
        views.append(
            AiReadinessReportLimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                summary=item.summary,
            )
        )
    return tuple(views[:limit])


def _traceability(
    section: AiReadinessAssessmentSection,
    *,
    finding_id_limit: int,
) -> AiReadinessReportTraceabilityView:
    edges = tuple(
        AiReadinessReportTraceEdgeView(
            edge_id=item.edge_id,
            relation=item.relation.value,
            source_id=item.source_id,
            target_id=item.target_id,
        )
        for item in sorted(section.traceability.edges, key=lambda edge: edge.edge_id)
    )
    finding_ids = tuple(section.finding_ids)[:finding_id_limit]
    return AiReadinessReportTraceabilityView(
        summary=(
            f"{len(edges)} traceability edge"
            f"{'' if len(edges) == 1 else 's'} link the AI Readiness assessment "
            "section to packs, findings, themes, conclusions, and limitations. "
            "Finding references use Finding IDs only."
        ),
        finding_ids=finding_ids,
        sample_edges=edges[:TRACE_SAMPLE_LIMIT],
        edge_count=len(edges),
    )


__all__ = ["AiReadinessReportAdapter"]
