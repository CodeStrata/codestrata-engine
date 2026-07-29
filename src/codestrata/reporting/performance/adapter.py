"""Adapt PerformanceAssessmentSection into presentation PerformanceReportSection.

Phase 4.9.6 — presentation only. Does not recollect evidence, rerun rules,
rebuild inventories, or regenerate synthesis.
"""

from __future__ import annotations

from codestrata.domain.performance.assessment.enums import PerformanceAssessmentStatus
from codestrata.domain.performance.assessment.models import PerformanceAssessmentSection
from codestrata.domain.performance.synthesis.enums import PerformanceRecommendationKind
from codestrata.reporting.performance.models import (
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_ID_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    PERFORMANCE_FAMILY_DISPLAY_LIMIT,
    PERFORMANCE_REPORT_SECTION_ID,
    PERFORMANCE_REPORT_SECTION_VERSION,
    RECOMMENDATION_DISPLAY_LIMIT,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
    PerformanceReportConclusionView,
    PerformanceReportCountBucket,
    PerformanceReportCoverageAreaView,
    PerformanceReportCoverageSummary,
    PerformanceReportDiagnosticView,
    PerformanceReportExecutionSummary,
    PerformanceReportFamilyEntry,
    PerformanceReportFamilySummary,
    PerformanceReportInventorySummary,
    PerformanceReportLimitationView,
    PerformanceReportRecommendationGroup,
    PerformanceReportRecommendationView,
    PerformanceReportRuleEntryView,
    PerformanceReportSection,
    PerformanceReportThemeView,
    PerformanceReportTraceabilityView,
    PerformanceReportTraceEdgeView,
)

_STATUS_LABELS = {
    PerformanceAssessmentStatus.NOT_REQUESTED: "Not requested",
    PerformanceAssessmentStatus.DISABLED: "Disabled",
    PerformanceAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    PerformanceAssessmentStatus.SUCCEEDED: "Succeeded",
    PerformanceAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    PerformanceAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    PerformanceAssessmentStatus.DISABLED: (
        "Performance analysis was disabled for this assessment."
    ),
    PerformanceAssessmentStatus.NOT_APPLICABLE: (
        "No applicable Performance assessment was produced for this repository."
    ),
    PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "Performance reporting is limited because required "
        "repository-performance evidence was unavailable or insufficient."
    ),
    PerformanceAssessmentStatus.SUCCEEDED: (
        "Performance assessment completed using supported "
        "repository-performance evidence and hygiene rules."
    ),
    PerformanceAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Performance assessment produced usable results with partial evidence "
        "or rule evaluation limitations."
    ),
    PerformanceAssessmentStatus.FAILED: (
        "Performance assessment could not be assembled successfully."
    ),
    PerformanceAssessmentStatus.NOT_REQUESTED: ("Performance assessment was not requested."),
}

_FORBIDDEN = (
    "is performant",
    "are performant",
    "performant",
    "bottleneck",
    "latency bottleneck",
    "is slow",
    "repository is slow",
    "performance score",
    "performance grade",
    "readiness score",
    "production ready",
    "production-ready under load",
    "scalable",
    "free of latency",
    "modernize",
    "modernisation",
    "modernization path",
    "migrate to",
    "hotspot",
)

_REC_GROUPS = {
    PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS.value: (
        "Performance signals"
    ),
    PerformanceRecommendationKind.REVIEW_BLOCKING_OPERATION_SIGNALS.value: ("Performance signals"),
    PerformanceRecommendationKind.REVIEW_CACHING_FOUNDATION_SIGNALS.value: ("Performance signals"),
    PerformanceRecommendationKind.REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS.value: (
        "Performance signals"
    ),
    PerformanceRecommendationKind.REVIEW_RESOURCE_MANAGEMENT_SIGNALS.value: ("Performance signals"),
    PerformanceRecommendationKind.REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS.value: (
        "Performance signals"
    ),
    PerformanceRecommendationKind.VALIDATE_OBSERVED_PERFORMANCE_OBSERVABILITY_SIGNALS.value: (
        "Performance signals"
    ),
    PerformanceRecommendationKind.VALIDATE_OBSERVED_CONFIGURATION_CONTROLS.value: (
        "Performance signals"
    ),
    PerformanceRecommendationKind.REVIEW_BROAD_PERFORMANCE_FOUNDATIONS.value: (
        "Foundations and coverage"
    ),
    PerformanceRecommendationKind.REVIEW_LIMITED_SUPPORTING_CONTROLS.value: (
        "Foundations and coverage"
    ),
    PerformanceRecommendationKind.ACKNOWLEDGE_NO_PERFORMANCE_FINDINGS_IN_SUPPORTED_SCOPE.value: (
        "Scope acknowledgements"
    ),
    PerformanceRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE.value: (
        "Scope acknowledgements"
    ),
}

_GROUP_ORDER = (
    "Performance signals",
    "Foundations and coverage",
    "Scope acknowledgements",
)


def _safe(text: str) -> str:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish that the repository is performant", "")
        .replace("do not establish that the repository is performant", "")
        .replace("does not mean the repository is performant", "")
        .replace("the repository is performant", "")
        .replace("does not establish performance", "")
        .replace("do not establish performance", "")
        .replace("without claiming the repository is performant", "")
        .replace("from claiming the repository is performant", "")
        .replace("claiming the repository is performant", "")
        .replace("prescribing enablement paths", "")
        .replace("not performance scores", "")
        .replace("performance scoring", "")
        .replace("performance scores", "")
        .replace("zero findings does not mean", "")
        .replace("does not claim bottlenecks", "")
        .replace("free of latency risk", "")
        .replace("production-ready under load", "")
        .replace("is performant", "")
        .replace("are performant", "")
        .replace("not performant", "")
        .replace("performant", "")
        .replace("bottleneck", "")
    )
    for phrase in _FORBIDDEN:
        if phrase in sanitized:
            raise ValueError(f"forbidden report wording: {phrase}")
    return text


class PerformanceReportAdapter:
    """Single boundary from Performance assessment domain to report presentation."""

    def adapt(
        self,
        section: PerformanceAssessmentSection,
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
        performance_family_limit: int = PERFORMANCE_FAMILY_DISPLAY_LIMIT,
    ) -> PerformanceReportSection:
        synthesis_status = section.synthesis.status.value
        include_synth_projection = synthesis_status not in {
            "not_requested",
            "disabled",
            "failed",
        }

        inventory = (
            _inventory(section, finding_id_limit=finding_id_limit)
            if include_inventory
            else PerformanceReportInventorySummary()
        )
        coverage = _coverage(section) if include_coverage else PerformanceReportCoverageSummary()
        execution = (
            _execution(section)
            if include_execution_summary
            else PerformanceReportExecutionSummary()
        )
        performance_families = (
            _performance_families(section, limit=performance_family_limit)
            if include_inventory
            else PerformanceReportFamilySummary()
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
            else PerformanceReportTraceabilityView(summary="Traceability not included.")
        )
        posture = section.synthesis.overall_posture_summary or section.metadata.get(
            "overall_posture_summary", ""
        )
        executive = (
            _executive_summary(section, posture=posture)
            if include_executive_summary
            else section.status.value
        )
        return PerformanceReportSection(
            section_id=PERFORMANCE_REPORT_SECTION_ID,
            section_version=PERFORMANCE_REPORT_SECTION_VERSION,
            title="Performance Intelligence",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(section.status, section.status.value),
            assessment_status=section.status.value,
            synthesis_status=synthesis_status,
            assessment_scope=(
                f"Repository-level Performance Hygiene assessment for {section.repository_id}"
            ),
            repository_name=section.repository_id,
            performance_pack_id=section.performance_pack_id,
            performance_pack_version=section.performance_pack_version,
            overall_posture_summary=_safe(posture) if posture else "",
            executive_summary=_safe(executive),
            coverage_summary=coverage,
            execution_summary=execution,
            inventory_summary=inventory,
            performance_family_summary=performance_families,
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
                "families_observed": str(performance_families.families_observed),
                "theme_limit": str(theme_limit),
                "finding_id_display_limit": str(finding_id_limit),
                "diagnostic_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(
    section: PerformanceAssessmentSection,
    *,
    posture: str,
) -> str:
    if section.status is PerformanceAssessmentStatus.DISABLED:
        return (
            "Performance reporting is available, but Performance analysis "
            "was disabled for this assessment."
        )
    if section.status is PerformanceAssessmentStatus.NOT_REQUESTED:
        return "Performance assessment was not requested for this run."
    if section.status is PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Performance reporting is limited because the required "
            "repository-performance evidence was unavailable or insufficient."
        )
    if section.status is PerformanceAssessmentStatus.FAILED:
        return (
            "Performance assessment output is unavailable because analysis "
            "did not complete successfully."
        )
    if section.status is PerformanceAssessmentStatus.NOT_APPLICABLE:
        return "No applicable Performance assessment content was produced for this repository."

    parts: list[str] = []
    if posture:
        parts.append(posture)
    else:
        count = section.finding_inventory.finding_count
        executed = section.execution_summary.rules_executed
        if count == 0:
            parts.append(
                f"The supported Performance Hygiene rules executed ({executed}) "
                "and emitted no findings within the available evidence scope. "
                "This result does not establish that the repository is performant."
            )
        else:
            parts.append(
                "The supported Performance Hygiene assessment identified "
                f"{count} finding{'' if count == 1 else 's'} from "
                "repository-performance evidence."
            )

    if section.synthesis.status.value == "failed":
        parts.append(
            "Performance synthesis is unavailable for this report; inventory "
            "and execution projections remain."
        )
    elif section.synthesis.status.value in {"not_requested", "disabled"}:
        parts.append(
            "Performance synthesis was not included; this report projects "
            "inventory and execution facts only."
        )
    elif section.synthesis.status.value == "empty":
        parts.append(
            "Performance synthesis produced an empty inventory outcome within "
            "the supported evidence scope."
        )

    return " ".join(parts).strip()


def _buckets(counts: dict[str, int]) -> tuple[PerformanceReportCountBucket, ...]:
    return tuple(
        PerformanceReportCountBucket(key=key, count=count) for key, count in sorted(counts.items())
    )


def _inventory(
    section: PerformanceAssessmentSection,
    *,
    finding_id_limit: int,
) -> PerformanceReportInventorySummary:
    inventory = section.finding_inventory
    finding_ids = tuple(inventory.finding_ids)[:finding_id_limit]
    none_detected = None
    if inventory.finding_count == 0:
        none_detected = (
            "No Performance Hygiene findings were emitted within the supported "
            "repository evidence scope. This does not establish that the "
            "repository is performant."
        )
        _safe(none_detected)
    return PerformanceReportInventorySummary(
        finding_count=inventory.finding_count,
        finding_ids=finding_ids,
        finding_ids_displayed=len(finding_ids),
        by_rule=_buckets(inventory.rule_counts),
        by_severity=_buckets(inventory.severity_counts),
        by_confidence=_buckets(inventory.confidence_counts),
        none_detected_statement=none_detected,
    )


def _performance_families(
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> PerformanceReportFamilySummary:
    inventory = section.performance_family_inventory
    entries = tuple(
        PerformanceReportFamilyEntry(
            family_id=item.family_id,
            observed=item.observed,
            finding_count=item.finding_count,
            finding_ids=item.finding_ids[:FINDING_ID_DISPLAY_LIMIT],
            signals=item.signals,
        )
        for item in sorted(inventory.entries, key=lambda entry: entry.family_id)[:limit]
    )
    return PerformanceReportFamilySummary(
        families_observed=inventory.families_observed,
        families_total=inventory.families_total,
        entries=entries,
    )


def _coverage(section: PerformanceAssessmentSection) -> PerformanceReportCoverageSummary:
    areas = tuple(
        PerformanceReportCoverageAreaView(
            area_id=item.area_id,
            status=item.status.value,
            numerator=item.numerator,
            denominator=item.denominator,
            maturity=item.maturity.value,
        )
        for item in sorted(section.coverage.areas, key=lambda area: area.area_id)
    )
    return PerformanceReportCoverageSummary(
        evidence_pipeline=section.evidence_pipeline,
        evidence_status=section.metadata.get("evidence_status", ""),
        areas=areas,
    )


def _execution(
    section: PerformanceAssessmentSection,
) -> PerformanceReportExecutionSummary:
    summary = section.execution_summary
    entries = tuple(
        PerformanceReportRuleEntryView(
            rule_id=item.rule_id,
            enabled=item.enabled,
            executed=item.executed,
            evaluation_status=item.evaluation_status,
            finding_count=item.finding_count,
        )
        for item in sorted(section.rule_inventory.entries, key=lambda entry: entry.rule_id)
    )
    return PerformanceReportExecutionSummary(
        rules_planned=summary.performance_rules_planned,
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
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> tuple[PerformanceReportThemeView, ...]:
    ordered = sorted(
        section.themes,
        key=lambda item: (item.ordering_key or item.kind.value, item.theme_id),
    )[:limit]
    return tuple(
        PerformanceReportThemeView(
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
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> tuple[PerformanceReportConclusionView, ...]:
    ordered = sorted(
        section.conclusions,
        key=lambda item: (item.kind.value, item.conclusion_id),
    )[:limit]
    return tuple(
        PerformanceReportConclusionView(
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
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> tuple[
    tuple[PerformanceReportRecommendationView, ...],
    tuple[PerformanceReportRecommendationGroup, ...],
]:
    ordered = sorted(
        section.recommendations,
        key=lambda item: (item.kind.value, item.recommendation_id),
    )[:limit]
    views = tuple(
        PerformanceReportRecommendationView(
            recommendation_id=item.recommendation_id,
            kind=item.kind.value,
            title=item.title,
            action=item.action,
            rationale=item.rationale,
            audience=item.audience.value,
            presentation_group=_REC_GROUPS.get(item.kind.value, "Performance signals"),
            conclusion_ids=item.conclusion_ids,
            finding_ids=item.finding_ids,
            rule_ids=item.rule_ids,
            conditional=item.conditional,
        )
        for item in ordered
    )
    by_group: dict[str, list[PerformanceReportRecommendationView]] = {
        name: [] for name in _GROUP_ORDER
    }
    for view in views:
        by_group.setdefault(view.presentation_group, []).append(view)
    groups = tuple(
        PerformanceReportRecommendationGroup(
            group=name,
            recommendations=tuple(by_group[name]),
        )
        for name in _GROUP_ORDER
        if by_group.get(name)
    )
    extras = tuple(
        PerformanceReportRecommendationGroup(group=name, recommendations=tuple(items))
        for name, items in sorted(by_group.items())
        if name not in _GROUP_ORDER and items
    )
    return views, groups + extras


def _diagnostics(
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> tuple[PerformanceReportDiagnosticView, ...]:
    records: list[PerformanceReportDiagnosticView] = []
    for index, message in enumerate(section.diagnostics):
        records.append(
            PerformanceReportDiagnosticView(
                diagnostic_id=f"assessment:{index}",
                origin="assessment",
                diagnostic_code="assessment_diagnostic",
                message=str(message)[:400],
            )
        )
    for index, message in enumerate(section.synthesis.diagnostics):
        records.append(
            PerformanceReportDiagnosticView(
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
    section: PerformanceAssessmentSection,
    *,
    limit: int,
) -> tuple[PerformanceReportLimitationView, ...]:
    seen: set[str] = set()
    views: list[PerformanceReportLimitationView] = []
    for item in sorted(section.limitations, key=lambda lim: lim.limitation_id):
        if item.summary in seen:
            continue
        seen.add(item.summary)
        views.append(
            PerformanceReportLimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                summary=item.summary,
            )
        )
    return tuple(views[:limit])


def _traceability(
    section: PerformanceAssessmentSection,
    *,
    finding_id_limit: int,
) -> PerformanceReportTraceabilityView:
    edges = tuple(
        PerformanceReportTraceEdgeView(
            edge_id=item.edge_id,
            relation=item.relation.value,
            source_id=item.source_id,
            target_id=item.target_id,
        )
        for item in sorted(section.traceability.edges, key=lambda edge: edge.edge_id)
    )
    finding_ids = tuple(section.finding_ids)[:finding_id_limit]
    return PerformanceReportTraceabilityView(
        summary=(
            f"{len(edges)} traceability edge"
            f"{'' if len(edges) == 1 else 's'} link the Performance assessment "
            "section to packs, findings, themes, conclusions, and limitations. "
            "Finding references use Finding IDs only."
        ),
        finding_ids=finding_ids,
        sample_edges=edges[:TRACE_SAMPLE_LIMIT],
        edge_count=len(edges),
    )


__all__ = ["PerformanceReportAdapter"]
