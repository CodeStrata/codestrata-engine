"""Adapt TechnicalDebtAssessmentSection into presentation TechnicalDebtReportSection."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtCoverageAreaStatus,
    TechnicalDebtSourceRole,
)
from codestrata.domain.technical_debt.assessment.models import (
    TechnicalDebtAssessmentSection,
    TechnicalDebtCoverageArea,
    TechnicalDebtHotspot,
    TechnicalDebtLimitation,
)
from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
)
from codestrata.domain.technical_debt.synthesis.models import (
    TechnicalDebtConclusion,
    TechnicalDebtRecommendation,
    TechnicalDebtTheme,
)
from codestrata.reporting.technical_debt.models import (
    TECHNICAL_DEBT_REPORT_SECTION_ID,
    TECHNICAL_DEBT_REPORT_SECTION_VERSION,
    TOP_PRODUCTION_HOTSPOTS,
    TRACE_SAMPLE_LIMIT,
    TechnicalDebtReportConclusionView,
    TechnicalDebtReportCoverageItem,
    TechnicalDebtReportHotspotView,
    TechnicalDebtReportLimitationView,
    TechnicalDebtReportMetric,
    TechnicalDebtReportRecommendationView,
    TechnicalDebtReportSection,
    TechnicalDebtReportTestObservation,
    TechnicalDebtReportThemeView,
    TechnicalDebtReportTraceabilityView,
    TechnicalDebtReportTraceEdgeView,
)

_STATUS_LABELS = {
    TechnicalDebtAssessmentStatus.NOT_REQUESTED: "Not requested",
    TechnicalDebtAssessmentStatus.DISABLED: "Disabled",
    TechnicalDebtAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    TechnicalDebtAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    TechnicalDebtAssessmentStatus.SUCCEEDED: "Succeeded",
    TechnicalDebtAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    TechnicalDebtAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    TechnicalDebtAssessmentStatus.DISABLED: (
        "Technical debt analysis was disabled for this assessment."
    ),
    TechnicalDebtAssessmentStatus.NOT_APPLICABLE: (
        "No supported technical debt evidence was available for this repository."
    ),
    TechnicalDebtAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "The repository was processed, but technical debt conclusions could not be "
        "established safely from the available evidence."
    ),
    TechnicalDebtAssessmentStatus.SUCCEEDED: (
        "Technical debt assessment completed using static complexity evidence."
    ),
    TechnicalDebtAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Technical debt assessment produced useful results with one or more partial "
        "failures or limitations."
    ),
    TechnicalDebtAssessmentStatus.FAILED: (
        "Technical debt assessment could not be assembled safely."
    ),
    TechnicalDebtAssessmentStatus.NOT_REQUESTED: (
        "Technical debt assessment was not requested."
    ),
}

_COVERAGE_LABELS = {
    "complexity_coverage": "Complexity coverage",
    "debt_rule_coverage": "Debt rule coverage",
    "duplication_coverage": "Duplication coverage",
    "dependency_support_coverage": "Dependency-support coverage",
    "enterprise_context_coverage": "Enterprise-context coverage",
}


class TechnicalDebtReportAdapter:
    """Single boundary from assessment domain to report presentation.

    Consumes an in-memory TechnicalDebtAssessmentSection only. Does not collect
    evidence, evaluate rules, re-read artifacts, or generate AI inference.
    """

    def adapt(
        self,
        section: TechnicalDebtAssessmentSection,
        *,
        include_executive_summary: bool = True,
        include_metrics: bool = True,
        include_themes: bool = True,
        include_hotspots: bool = True,
        include_conclusions: bool = True,
        include_recommendations: bool = True,
        include_test_observation: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        top_hotspot_limit: int = TOP_PRODUCTION_HOTSPOTS,
    ) -> TechnicalDebtReportSection:
        status = section.status
        production_conclusions = tuple(
            item
            for item in section.conclusions
            if item.audience is not TechnicalDebtConclusionAudience.TEST_OBSERVATION
        )
        conclusions = production_conclusions if include_conclusions else ()
        recommendations = (
            tuple(
                item
                for item in section.recommendations
                if item.audience is not TechnicalDebtConclusionAudience.TEST_OBSERVATION
            )
            if include_recommendations
            else ()
        )
        themes = (
            tuple(
                item
                for item in section.themes
                if item.source_role is TechnicalDebtSourceRole.PRODUCTION
                and item.finding_count > 0
            )
            if include_themes
            else ()
        )
        hotspots = (
            section.hotspot_inventory.production[: max(0, top_hotspot_limit)]
            if include_hotspots
            else ()
        )
        coverage = section.coverage.areas if include_coverage else ()
        limitations = section.limitations if include_limitations else ()

        conclusion_views = tuple(_conclusion_view(item) for item in conclusions)
        recommendation_views = tuple(
            _recommendation_view(item) for item in recommendations
        )
        theme_views = tuple(_theme_view(item) for item in themes)
        hotspot_views = tuple(
            _hotspot_view(item, order=index)
            for index, item in enumerate(hotspots, start=1)
        )
        coverage_views = tuple(_coverage_view(item) for item in coverage)
        limitation_views = tuple(_limitation_view(item) for item in limitations)
        metrics = (
            _metrics(section, themes=themes, hotspots=hotspots, conclusions=conclusions)
            if include_metrics
            else ()
        )
        test_observation = (
            _test_observation(section)
            if include_test_observation
            else TechnicalDebtReportTestObservation()
        )
        traceability = (
            _traceability(section)
            if include_traceability
            else TechnicalDebtReportTraceabilityView(summary="Traceability not included.")
        )
        executive = (
            _executive_summary(section, themes=themes, conclusions=conclusions)
            if include_executive_summary
            else status.value
        )
        production_count = section.execution_summary.production_finding_count
        test_count = section.execution_summary.test_finding_count
        return TechnicalDebtReportSection(
            section_id=TECHNICAL_DEBT_REPORT_SECTION_ID,
            section_version=TECHNICAL_DEBT_REPORT_SECTION_VERSION,
            title="Technical Debt Assessment",
            status=status.value,
            status_label=_STATUS_LABELS.get(status, status.value),
            status_summary=_STATUS_SUMMARIES.get(status, status.value),
            assessment_scope=(
                "Repository-level static technical debt assessment for "
                f"{section.repository_id}"
            ),
            repository_name=section.repository_id,
            technical_debt_pack_id=section.technical_debt_pack_id,
            technical_debt_pack_version=section.technical_debt_pack_version,
            executive_summary=executive,
            key_metrics=metrics,
            significant_themes=theme_views,
            top_production_hotspots=hotspot_views,
            conclusions=conclusion_views,
            recommendations=recommendation_views,
            test_observation=test_observation,
            coverage_summary=coverage_views,
            limitations=limitation_views,
            traceability_summary=traceability,
            enterprise_context_used=section.enterprise_context_used,
            generated_from_assessment_section_version=section.section_version,
            metadata={
                "assessment_section_id": section.section_id,
                "evidence_pipeline": section.evidence_pipeline,
                "evidence_fingerprint": section.evidence_fingerprint or "",
                "configuration_fingerprint": section.configuration_fingerprint or "",
                "production_finding_count": str(production_count),
                "test_finding_count": str(test_count),
                "hotspot_limit": str(top_hotspot_limit),
            },
        )


def _executive_summary(
    section: TechnicalDebtAssessmentSection,
    *,
    themes: Sequence[TechnicalDebtTheme],
    conclusions: Sequence[TechnicalDebtConclusion],
) -> str:
    if section.status is TechnicalDebtAssessmentStatus.DISABLED:
        return (
            "Technical debt reporting is available, but technical debt analysis was "
            "disabled for this assessment."
        )
    if section.status is TechnicalDebtAssessmentStatus.NOT_REQUESTED:
        return "Technical debt assessment was not requested for this run."
    if section.status is TechnicalDebtAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Technical debt assessment could not establish safe conclusions from the "
            "available repository evidence. Findings are not presented as confirmed "
            "debt concerns."
        )
    if section.status is TechnicalDebtAssessmentStatus.FAILED:
        return (
            "Technical debt assessment failed to assemble a usable section. Existing "
            "non-debt report content remains available."
        )
    if section.status is TechnicalDebtAssessmentStatus.NOT_APPLICABLE:
        return (
            "No supported technical debt evidence was available for this repository "
            "assessment."
        )

    production = section.execution_summary.production_finding_count
    test = section.execution_summary.test_finding_count
    theme_count = len(themes)
    conclusion_count = len(conclusions)
    hotspot_count = len(section.hotspot_inventory.production)
    themes_note = _theme_text(themes)
    partial_note = (
        " Partial production parse or coverage limitations were recorded."
        if section.status is TechnicalDebtAssessmentStatus.PARTIALLY_SUCCEEDED
        else ""
    )
    if production == 0:
        base = (
            "No production-source complexity findings were identified under the "
            "current technical debt rules and coverage."
        )
        if test > 0:
            base += (
                f" {test} test-source complexity finding"
                f"{'s' if test != 1 else ''} "
                f"{'were' if test != 1 else 'was'} recorded separately as a "
                "test-maintainability observation."
            )
        if conclusion_count:
            base += (
                f" {conclusion_count} production-facing conclusion"
                f"{'s' if conclusion_count != 1 else ''} "
                f"{'were' if conclusion_count != 1 else 'was'} generated."
            )
        return (base + partial_note).strip()

    themes_clause = (
        f" Significant production themes: {themes_note}."
        if themes_note
        else (
            f" Findings spanned {theme_count} production theme"
            f"{'s' if theme_count != 1 else ''}."
            if theme_count
            else ""
        )
    )
    conclusions_clause = (
        f" These map to {conclusion_count} production-facing conclusion"
        f"{'s' if conclusion_count != 1 else ''}."
        if conclusion_count > 1
        else (
            " These map to 1 production-facing conclusion."
            if conclusion_count == 1
            else " Production conclusions were not generated for this assessment."
        )
    )
    hotspot_clause = (
        f" Inventory presentation includes {min(hotspot_count, TOP_PRODUCTION_HOTSPOTS)}"
        f" of {hotspot_count} production hotspot"
        f"{'s' if hotspot_count != 1 else ''} "
        "(ordered by severity, finding count, then path — not a priority score)."
        if hotspot_count
        else ""
    )
    test_clause = (
        f" Separately, {test} test-source finding"
        f"{'s' if test != 1 else ''} "
        "are presented as a test-maintainability observation, not production health."
        if test
        else ""
    )
    return (
        f"The technical debt assessment identified {production} production-source "
        f"complexity finding{'s' if production != 1 else ''} across the analyzed "
        f"repository.{themes_clause}{conclusions_clause}{hotspot_clause}{test_clause}"
        f" The assessment is based on static complexity evidence and does not include "
        f"composite debt scores, financial estimates, or remediation-hour claims."
        f"{partial_note}"
    ).strip()


def _theme_text(themes: Sequence[TechnicalDebtTheme]) -> str:
    titles: list[str] = []
    seen: set[str] = set()
    for item in themes:
        title = item.title.rstrip(".")
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    if not titles:
        return ""
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return ", ".join(titles[:-1]) + f", and {titles[-1]}"


def _metrics(
    section: TechnicalDebtAssessmentSection,
    *,
    themes: Sequence[TechnicalDebtTheme],
    hotspots: Sequence[TechnicalDebtHotspot],
    conclusions: Sequence[TechnicalDebtConclusion],
) -> tuple[TechnicalDebtReportMetric, ...]:
    summary = section.execution_summary
    complexity = next(
        (
            area
            for area in section.coverage.areas
            if area.area_id == "complexity_coverage"
        ),
        None,
    )
    return (
        TechnicalDebtReportMetric(
            key="production_findings",
            label="Production findings",
            value=str(summary.production_finding_count),
        ),
        TechnicalDebtReportMetric(
            key="production_hotspots",
            label="Production hotspots shown",
            value=str(len(hotspots)),
            note=(
                f"{len(section.hotspot_inventory.production)} production hotspots "
                "in inventory (presentation order, not priority)."
            ),
        ),
        TechnicalDebtReportMetric(
            key="significant_themes",
            label="Significant themes",
            value=str(len(themes)),
        ),
        TechnicalDebtReportMetric(
            key="conclusions",
            label="Conclusions",
            value=str(len(conclusions)),
        ),
        TechnicalDebtReportMetric(
            key="complexity_coverage",
            label="Complexity coverage",
            value=_ratio_or_unavailable(complexity.ratio if complexity else None),
        ),
        TechnicalDebtReportMetric(
            key="test_findings",
            label="Test findings (separate)",
            value=str(summary.test_finding_count),
            note="Presented as test-maintainability observation only.",
        ),
    )


def _ratio_or_unavailable(ratio: float | None) -> str:
    if ratio is None:
        return "Unavailable"
    return f"{ratio:.1%}"


def _theme_view(item: TechnicalDebtTheme) -> TechnicalDebtReportThemeView:
    return TechnicalDebtReportThemeView(
        theme_id=item.theme_id,
        title=item.title,
        rule_id=item.rule_id,
        source_role=item.source_role.value,
        finding_count=item.finding_count,
        high_severity_count=item.high_severity_count,
        medium_severity_count=item.medium_severity_count,
    )


def _hotspot_view(
    item: TechnicalDebtHotspot, *, order: int
) -> TechnicalDebtReportHotspotView:
    metric_parts = [
        f"{metric.metric}={metric.value}"
        + (f" (threshold {metric.threshold})" if metric.threshold else "")
        for metric in item.observed_metrics[:5]
    ]
    return TechnicalDebtReportHotspotView(
        hotspot_id=item.hotspot_id,
        path=item.path,
        package=item.package,
        source_unit=item.source_unit,
        source_role=item.source_role.value,
        language=item.language,
        finding_count=item.finding_count,
        highest_severity=item.highest_severity,
        rule_ids=item.rule_ids,
        metric_summary="; ".join(metric_parts) if metric_parts else "—",
        presentation_order=order,
    )


def _conclusion_view(
    item: TechnicalDebtConclusion,
) -> TechnicalDebtReportConclusionView:
    kind = getattr(item.kind, "value", str(item.kind))
    audience = getattr(item.audience, "value", str(item.audience))
    return TechnicalDebtReportConclusionView(
        conclusion_id=item.conclusion_id,
        policy_id=item.policy_id,
        kind=str(kind),
        audience=str(audience),
        title=item.title,
        summary=item.summary,
        confidence=item.confidence,
        source_role=item.source_role.value,
        theme_ids=item.theme_ids,
        finding_count=len(item.finding_ids),
        hotspot_count=len(item.hotspot_ids),
        recommendation_ids=item.recommendation_ids,
    )


def _recommendation_view(
    item: TechnicalDebtRecommendation,
) -> TechnicalDebtReportRecommendationView:
    audience = getattr(item.audience, "value", str(item.audience))
    return TechnicalDebtReportRecommendationView(
        recommendation_id=item.recommendation_id,
        title=item.title,
        action=item.action,
        rationale=item.rationale,
        conditional=item.conditional,
        audience=str(audience),
        conclusion_ids=item.conclusion_ids,
    )


def _test_observation(
    section: TechnicalDebtAssessmentSection,
) -> TechnicalDebtReportTestObservation:
    test_conclusions = tuple(
        item
        for item in section.conclusions
        if item.audience is TechnicalDebtConclusionAudience.TEST_OBSERVATION
    )
    test_count = section.execution_summary.test_finding_count
    if not test_conclusions and test_count == 0:
        return TechnicalDebtReportTestObservation()
    if test_conclusions:
        primary = test_conclusions[0]
        return TechnicalDebtReportTestObservation(
            present=True,
            finding_count=test_count,
            title=primary.title,
            summary=primary.summary,
            conclusion_ids=tuple(item.conclusion_id for item in test_conclusions),
        )
    return TechnicalDebtReportTestObservation(
        present=True,
        finding_count=test_count,
        title="Test-source complexity findings observed",
        summary=(
            f"{test_count} test-source complexity finding"
            f"{'s' if test_count != 1 else ''} "
            "were recorded. These are a test-maintainability observation and are not "
            "treated as production health signals."
        ),
        conclusion_ids=(),
    )


def _coverage_view(item: TechnicalDebtCoverageArea) -> TechnicalDebtReportCoverageItem:
    area_id = item.area_id
    status_value = item.status.value
    ratio = item.ratio
    label = _COVERAGE_LABELS.get(area_id, area_id.replace("_", " ").title())
    display = _coverage_display(status_value, ratio, area_id)
    note = item.limitations[0] if item.limitations else None
    return TechnicalDebtReportCoverageItem(
        area_id=area_id,
        label=label,
        status=status_value,
        display=display,
        ratio=ratio,
        note=note,
    )


def _coverage_display(status: str, ratio: float | None, area_id: str) -> str:
    if status == TechnicalDebtCoverageAreaStatus.UNSUPPORTED.value:
        return "Not measured by the current provider set."
    if status == TechnicalDebtCoverageAreaStatus.NOT_APPLICABLE.value:
        if "enterprise" in area_id:
            return "Enterprise context was not supplied for this repository assessment."
        return "Not applicable for this assessment."
    if status == TechnicalDebtCoverageAreaStatus.UNKNOWN.value or ratio is None:
        return "Unavailable"
    if status == TechnicalDebtCoverageAreaStatus.PARTIAL.value:
        return f"Partial ({ratio:.1%})."
    if ratio >= 0.999:
        return "Complete for the analyzed source set."
    return f"Measured ({ratio:.1%})."


def _limitation_view(
    item: TechnicalDebtLimitation,
) -> TechnicalDebtReportLimitationView:
    category = getattr(item.category, "value", str(item.category))
    return TechnicalDebtReportLimitationView(
        limitation_id=item.limitation_id,
        category=str(category),
        summary=item.summary,
        importance=item.importance,
    )


def _traceability(
    section: TechnicalDebtAssessmentSection,
) -> TechnicalDebtReportTraceabilityView:
    edges = section.traceability.edges
    relation_types = tuple(sorted({edge.relation.value for edge in edges}))
    sample = tuple(
        TechnicalDebtReportTraceEdgeView(
            relation=edge.relation.value,
            source_id=edge.source_id,
            target_id=edge.target_id,
        )
        for edge in edges[:TRACE_SAMPLE_LIMIT]
    )
    return TechnicalDebtReportTraceabilityView(
        edge_count=len(edges),
        relation_types=relation_types,
        sample_edges=sample,
        summary=(
            f"{len(edges)} traceability relationship"
            f"{'s' if len(edges) != 1 else ''} across "
            f"{len(relation_types)} relation type"
            f"{'s' if len(relation_types) != 1 else ''}."
        ),
    )
