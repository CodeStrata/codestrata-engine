"""Adapt TestAssessmentSection into presentation TestingReportSection.

Phase 4.6.6 — presentation only. Does not recollect evidence, rerun rules,
rebuild inventories, or regenerate synthesis.
"""

from __future__ import annotations

from codestrata.domain.testing.assessment.enums import TestAssessmentStatus
from codestrata.domain.testing.assessment.models import TestAssessmentSection
from codestrata.domain.testing.synthesis.enums import TestRecommendationKind
from codestrata.reporting.testing.models import (
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_ID_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    RECOMMENDATION_DISPLAY_LIMIT,
    TESTING_REPORT_SECTION_ID,
    TESTING_REPORT_SECTION_VERSION,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
    TestingReportConclusionView,
    TestingReportCountBucket,
    TestingReportCoverageAreaView,
    TestingReportCoverageSummary,
    TestingReportDiagnosticView,
    TestingReportExecutionSummary,
    TestingReportInventorySummary,
    TestingReportLimitationView,
    TestingReportRecommendationGroup,
    TestingReportRecommendationView,
    TestingReportRuleEntryView,
    TestingReportSection,
    TestingReportThemeView,
    TestingReportTraceabilityView,
    TestingReportTraceEdgeView,
)

_STATUS_LABELS = {
    TestAssessmentStatus.NOT_REQUESTED: "Not requested",
    TestAssessmentStatus.DISABLED: "Disabled",
    TestAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    TestAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    TestAssessmentStatus.SUCCEEDED: "Succeeded",
    TestAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    TestAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    TestAssessmentStatus.DISABLED: ("Test analysis was disabled for this assessment."),
    TestAssessmentStatus.NOT_APPLICABLE: (
        "No applicable Test assessment was produced for this repository."
    ),
    TestAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "Test reporting is limited because required repository-testing "
        "evidence was unavailable or insufficient."
    ),
    TestAssessmentStatus.SUCCEEDED: (
        "Test assessment completed using supported repository-testing evidence and hygiene rules."
    ),
    TestAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Test assessment produced usable results with partial evidence or "
        "rule evaluation limitations."
    ),
    TestAssessmentStatus.FAILED: ("Test assessment could not be assembled successfully."),
    TestAssessmentStatus.NOT_REQUESTED: ("Test assessment was not requested."),
}

_FORBIDDEN = (
    "well tested",
    "testing passed",
    "tests passed",
    "release ready",
    "no testing issues",
    "tests are sufficient",
    "fully tested",
    "test coverage is adequate",
)

_REC_GROUPS = {
    TestRecommendationKind.REVIEW_DISABLED_OR_SKIPPED_TESTS.value: ("Test hygiene actions"),
    TestRecommendationKind.IMPROVE_TEST_DISCOVERY_SIGNALING.value: ("Test hygiene actions"),
    TestRecommendationKind.ALIGN_FRAMEWORK_DECLARATION_AND_OBSERVATION.value: (
        "Test hygiene actions"
    ),
    TestRecommendationKind.ALIGN_COVERAGE_CONFIG_WITH_CI.value: ("Coverage and CI alignment"),
    TestRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE.value: (
        "Scope acknowledgements"
    ),
    TestRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_TEST_ANALYSIS_SCOPE.value: (
        "Scope acknowledgements"
    ),
}

_GROUP_ORDER = (
    "Test hygiene actions",
    "Coverage and CI alignment",
    "Scope acknowledgements",
)


def _safe(text: str) -> str:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish that the repository is well tested", "")
        .replace("does not establish that tests are sufficient", "")
        .replace("does not establish release readiness", "")
        .replace("do not establish release readiness", "")
        .replace("or release ready", "")
        .replace("zero findings does not mean", "")
    )
    for phrase in _FORBIDDEN:
        if phrase in sanitized:
            raise ValueError(f"forbidden report wording: {phrase}")
    return text


class TestingReportAdapter:
    """Single boundary from Test assessment domain to report presentation."""

    __test__ = False

    def adapt(
        self,
        section: TestAssessmentSection,
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
    ) -> TestingReportSection:
        synthesis_status = section.synthesis.status.value
        include_synth_projection = synthesis_status not in {
            "not_requested",
            "disabled",
            "failed",
        }

        inventory = (
            _inventory(section, finding_id_limit=finding_id_limit)
            if include_inventory
            else TestingReportInventorySummary()
        )
        coverage = _coverage(section) if include_coverage else TestingReportCoverageSummary()
        execution = (
            _execution(section) if include_execution_summary else TestingReportExecutionSummary()
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
            _traceability(section)
            if include_traceability
            else TestingReportTraceabilityView(summary="Traceability not included.")
        )
        posture = section.synthesis.overall_posture_summary or section.metadata.get(
            "overall_posture_summary", ""
        )
        executive = (
            _executive_summary(section, posture=posture)
            if include_executive_summary
            else section.status.value
        )
        return TestingReportSection(
            section_id=TESTING_REPORT_SECTION_ID,
            section_version=TESTING_REPORT_SECTION_VERSION,
            title="Test Intelligence",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(section.status, section.status.value),
            assessment_status=section.status.value,
            synthesis_status=synthesis_status,
            assessment_scope=(
                f"Repository-level Test Hygiene assessment for {section.repository_id}"
            ),
            repository_name=section.repository_id,
            testing_pack_id=section.testing_pack_id,
            testing_pack_version=section.testing_pack_version,
            overall_posture_summary=_safe(posture) if posture else "",
            executive_summary=_safe(executive),
            coverage_summary=coverage,
            execution_summary=execution,
            inventory_summary=inventory,
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
                "theme_limit": str(theme_limit),
                "finding_id_display_limit": str(finding_id_limit),
                "diagnostic_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(
    section: TestAssessmentSection,
    *,
    posture: str,
) -> str:
    if section.status is TestAssessmentStatus.DISABLED:
        return "Test reporting is available, but Test analysis was disabled for this assessment."
    if section.status is TestAssessmentStatus.NOT_REQUESTED:
        return "Test assessment was not requested for this run."
    if section.status is TestAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Test reporting is limited because the required "
            "repository-testing evidence was unavailable or insufficient."
        )
    if section.status is TestAssessmentStatus.FAILED:
        return (
            "Test assessment output is unavailable because analysis did not complete successfully."
        )
    if section.status is TestAssessmentStatus.NOT_APPLICABLE:
        return "No applicable Test assessment content was produced for this repository."

    parts: list[str] = []
    if posture:
        parts.append(posture)
    else:
        count = section.finding_inventory.finding_count
        executed = section.execution_summary.rules_executed
        if count == 0:
            parts.append(
                f"The supported Test Hygiene rules executed ({executed}) and "
                "emitted no findings within the available evidence scope. This "
                "result does not certify readiness for release."
            )
        else:
            parts.append(
                f"The supported Test Hygiene assessment identified {count} finding"
                f"{'' if count == 1 else 's'} from repository-testing evidence."
            )

    if section.synthesis.status.value == "failed":
        parts.append(
            "Test synthesis is unavailable for this report; inventory and "
            "execution projections remain."
        )
    elif section.synthesis.status.value in {"not_requested", "disabled"}:
        parts.append(
            "Test synthesis was not included; this report projects inventory "
            "and execution facts only."
        )

    return " ".join(parts).strip()


def _buckets(counts: dict[str, int]) -> tuple[TestingReportCountBucket, ...]:
    return tuple(
        TestingReportCountBucket(key=key, count=count) for key, count in sorted(counts.items())
    )


def _inventory(
    section: TestAssessmentSection,
    *,
    finding_id_limit: int,
) -> TestingReportInventorySummary:
    inventory = section.finding_inventory
    finding_ids = tuple(inventory.finding_ids)[:finding_id_limit]
    none_detected = None
    if inventory.finding_count == 0:
        none_detected = (
            "No Test Hygiene findings were emitted within the supported "
            "repository evidence scope. This does not certify readiness for release."
        )
        _safe(none_detected)
    return TestingReportInventorySummary(
        finding_count=inventory.finding_count,
        finding_ids=finding_ids,
        finding_ids_displayed=len(finding_ids),
        by_rule=_buckets(inventory.rule_counts),
        by_severity=_buckets(inventory.severity_counts),
        by_confidence=_buckets(inventory.confidence_counts),
        none_detected_statement=none_detected,
    )


def _coverage(section: TestAssessmentSection) -> TestingReportCoverageSummary:
    areas = tuple(
        TestingReportCoverageAreaView(
            area_id=item.area_id,
            status=item.status.value,
            numerator=item.numerator,
            denominator=item.denominator,
            maturity=item.maturity.value,
        )
        for item in sorted(section.coverage.areas, key=lambda area: area.area_id)
    )
    return TestingReportCoverageSummary(
        evidence_pipeline=section.evidence_pipeline,
        evidence_status=section.metadata.get("evidence_status", ""),
        areas=areas,
    )


def _execution(section: TestAssessmentSection) -> TestingReportExecutionSummary:
    summary = section.execution_summary
    entries = tuple(
        TestingReportRuleEntryView(
            rule_id=item.rule_id,
            enabled=item.enabled,
            executed=item.executed,
            evaluation_status=item.evaluation_status,
            finding_count=item.finding_count,
        )
        for item in sorted(section.rule_inventory.entries, key=lambda entry: entry.rule_id)
    )
    return TestingReportExecutionSummary(
        rules_planned=summary.testing_rules_planned,
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
    section: TestAssessmentSection,
    *,
    limit: int,
) -> tuple[TestingReportThemeView, ...]:
    ordered = sorted(
        section.themes,
        key=lambda item: (item.ordering_key or item.kind.value, item.theme_id),
    )[:limit]
    return tuple(
        TestingReportThemeView(
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
    section: TestAssessmentSection,
    *,
    limit: int,
) -> tuple[TestingReportConclusionView, ...]:
    ordered = sorted(
        section.conclusions,
        key=lambda item: (item.kind.value, item.conclusion_id),
    )[:limit]
    return tuple(
        TestingReportConclusionView(
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
    section: TestAssessmentSection,
    *,
    limit: int,
) -> tuple[
    tuple[TestingReportRecommendationView, ...],
    tuple[TestingReportRecommendationGroup, ...],
]:
    ordered = sorted(
        section.recommendations,
        key=lambda item: (item.kind.value, item.recommendation_id),
    )[:limit]
    views = tuple(
        TestingReportRecommendationView(
            recommendation_id=item.recommendation_id,
            kind=item.kind.value,
            title=item.title,
            action=item.action,
            rationale=item.rationale,
            audience=item.audience.value,
            presentation_group=_REC_GROUPS.get(item.kind.value, "Test hygiene actions"),
            conclusion_ids=item.conclusion_ids,
            finding_ids=item.finding_ids,
            rule_ids=item.rule_ids,
            conditional=item.conditional,
        )
        for item in ordered
    )
    by_group: dict[str, list[TestingReportRecommendationView]] = {name: [] for name in _GROUP_ORDER}
    for view in views:
        by_group.setdefault(view.presentation_group, []).append(view)
    groups = tuple(
        TestingReportRecommendationGroup(
            group=name,
            recommendations=tuple(by_group[name]),
        )
        for name in _GROUP_ORDER
        if by_group.get(name)
    )
    extras = tuple(
        TestingReportRecommendationGroup(group=name, recommendations=tuple(items))
        for name, items in sorted(by_group.items())
        if name not in _GROUP_ORDER and items
    )
    return views, groups + extras


def _diagnostics(
    section: TestAssessmentSection,
    *,
    limit: int,
) -> tuple[TestingReportDiagnosticView, ...]:
    records: list[TestingReportDiagnosticView] = []
    for index, message in enumerate(section.diagnostics):
        records.append(
            TestingReportDiagnosticView(
                diagnostic_id=f"assessment:{index}",
                origin="assessment",
                diagnostic_code="assessment_diagnostic",
                message=str(message)[:400],
            )
        )
    for index, message in enumerate(section.synthesis.diagnostics):
        records.append(
            TestingReportDiagnosticView(
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
    section: TestAssessmentSection,
    *,
    limit: int,
) -> tuple[TestingReportLimitationView, ...]:
    seen: set[str] = set()
    views: list[TestingReportLimitationView] = []
    for item in sorted(section.limitations, key=lambda lim: lim.limitation_id):
        if item.summary in seen:
            continue
        seen.add(item.summary)
        views.append(
            TestingReportLimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                summary=item.summary,
            )
        )
    return tuple(views[:limit])


def _traceability(section: TestAssessmentSection) -> TestingReportTraceabilityView:
    edges = tuple(
        TestingReportTraceEdgeView(
            edge_id=item.edge_id,
            relation=item.relation.value,
            source_id=item.source_id,
            target_id=item.target_id,
        )
        for item in sorted(section.traceability.edges, key=lambda edge: edge.edge_id)
    )
    return TestingReportTraceabilityView(
        summary=(
            f"{len(edges)} traceability edge"
            f"{'' if len(edges) == 1 else 's'} link the Test assessment "
            "section to packs, findings, themes, conclusions, and limitations."
        ),
        sample_edges=edges[:TRACE_SAMPLE_LIMIT],
        edge_count=len(edges),
    )


__all__ = ["TestingReportAdapter"]
