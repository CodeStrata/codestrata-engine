"""Adapt CloudAssessmentSection into presentation CloudReportSection.

Phase 4.7.6 — presentation only. Does not recollect evidence, rerun rules,
rebuild inventories, or regenerate synthesis.
"""

from __future__ import annotations

from codestrata.domain.cloud.assessment.enums import CloudAssessmentStatus
from codestrata.domain.cloud.assessment.models import CloudAssessmentSection
from codestrata.domain.cloud.synthesis.enums import CloudRecommendationKind
from codestrata.reporting.cloud.models import (
    CLOUD_REPORT_SECTION_ID,
    CLOUD_REPORT_SECTION_VERSION,
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_ID_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    RECOMMENDATION_DISPLAY_LIMIT,
    TECHNOLOGY_FAMILY_DISPLAY_LIMIT,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
    CloudReportConclusionView,
    CloudReportCountBucket,
    CloudReportCoverageAreaView,
    CloudReportCoverageSummary,
    CloudReportDiagnosticView,
    CloudReportExecutionSummary,
    CloudReportInventorySummary,
    CloudReportLimitationView,
    CloudReportRecommendationGroup,
    CloudReportRecommendationView,
    CloudReportRuleEntryView,
    CloudReportSection,
    CloudReportTechnologyFamilyEntry,
    CloudReportTechnologyFamilySummary,
    CloudReportThemeView,
    CloudReportTraceabilityView,
    CloudReportTraceEdgeView,
)

_STATUS_LABELS = {
    CloudAssessmentStatus.NOT_REQUESTED: "Not requested",
    CloudAssessmentStatus.DISABLED: "Disabled",
    CloudAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    CloudAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    CloudAssessmentStatus.SUCCEEDED: "Succeeded",
    CloudAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    CloudAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    CloudAssessmentStatus.DISABLED: ("Cloud analysis was disabled for this assessment."),
    CloudAssessmentStatus.NOT_APPLICABLE: (
        "No applicable Cloud assessment was produced for this repository."
    ),
    CloudAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "Cloud reporting is limited because required repository-cloud "
        "evidence was unavailable or insufficient."
    ),
    CloudAssessmentStatus.SUCCEEDED: (
        "Cloud assessment completed using supported repository-cloud evidence and hygiene rules."
    ),
    CloudAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Cloud assessment produced usable results with partial evidence or "
        "rule evaluation limitations."
    ),
    CloudAssessmentStatus.FAILED: ("Cloud assessment could not be assembled successfully."),
    CloudAssessmentStatus.NOT_REQUESTED: ("Cloud assessment was not requested."),
}

_FORBIDDEN = (
    "is cloud ready",
    "are cloud ready",
    "cloud-native ready",
    "fully portable",
    "migrate to",
    "modernize",
    "modernisation",
    "modernization path",
    "multi-cloud strategy",
    "production ready",
    "no cloud issues",
)

_REC_GROUPS = {
    CloudRecommendationKind.REVIEW_CLOUD_PLATFORM_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_MULTI_CLOUD_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_CONTAINERIZATION_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_ORCHESTRATION_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_IAC_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_SERVERLESS_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_MANAGED_SERVICE_SIGNALS.value: ("Cloud technology signals"),
    CloudRecommendationKind.REVIEW_DEPLOYMENT_PIPELINE_SIGNALS.value: ("Deployment and coverage"),
    CloudRecommendationKind.REVIEW_CLOUD_TECHNOLOGY_COVERAGE.value: ("Deployment and coverage"),
    CloudRecommendationKind.REVIEW_DEPLOYMENT_WITHOUT_PLATFORM.value: ("Deployment and coverage"),
    CloudRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE.value: (
        "Scope acknowledgements"
    ),
    CloudRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_CLOUD_ANALYSIS_SCOPE.value: (
        "Scope acknowledgements"
    ),
}

_GROUP_ORDER = (
    "Cloud technology signals",
    "Deployment and coverage",
    "Scope acknowledgements",
)


def _safe(text: str) -> str:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish that the repository is cloud ready", "")
        .replace("does not mean the repository is cloud ready", "")
        .replace("does not establish cloud readiness", "")
        .replace("do not establish cloud readiness", "")
        .replace("without claiming cloud readiness", "")
        .replace("does not claim cloud usage is absent", "")
        .replace("not cloud ready", "")
        .replace("cloud readiness", "")
        .replace("zero findings does not mean", "")
    )
    for phrase in _FORBIDDEN:
        if phrase in sanitized:
            raise ValueError(f"forbidden report wording: {phrase}")
    return text


class CloudReportAdapter:
    """Single boundary from Cloud assessment domain to report presentation."""

    def adapt(
        self,
        section: CloudAssessmentSection,
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
        technology_family_limit: int = TECHNOLOGY_FAMILY_DISPLAY_LIMIT,
    ) -> CloudReportSection:
        synthesis_status = section.synthesis.status.value
        include_synth_projection = synthesis_status not in {
            "not_requested",
            "disabled",
            "failed",
        }

        inventory = (
            _inventory(section, finding_id_limit=finding_id_limit)
            if include_inventory
            else CloudReportInventorySummary()
        )
        coverage = _coverage(section) if include_coverage else CloudReportCoverageSummary()
        execution = (
            _execution(section) if include_execution_summary else CloudReportExecutionSummary()
        )
        technology_families = (
            _technology_families(section, limit=technology_family_limit)
            if include_inventory
            else CloudReportTechnologyFamilySummary()
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
            else CloudReportTraceabilityView(summary="Traceability not included.")
        )
        posture = section.synthesis.overall_posture_summary or section.metadata.get(
            "overall_posture_summary", ""
        )
        executive = (
            _executive_summary(section, posture=posture)
            if include_executive_summary
            else section.status.value
        )
        return CloudReportSection(
            section_id=CLOUD_REPORT_SECTION_ID,
            section_version=CLOUD_REPORT_SECTION_VERSION,
            title="Cloud Intelligence",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(section.status, section.status.value),
            assessment_status=section.status.value,
            synthesis_status=synthesis_status,
            assessment_scope=(
                f"Repository-level Cloud Hygiene assessment for {section.repository_id}"
            ),
            repository_name=section.repository_id,
            cloud_pack_id=section.cloud_pack_id,
            cloud_pack_version=section.cloud_pack_version,
            overall_posture_summary=_safe(posture) if posture else "",
            executive_summary=_safe(executive),
            coverage_summary=coverage,
            execution_summary=execution,
            inventory_summary=inventory,
            technology_family_summary=technology_families,
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
                "families_observed": str(technology_families.families_observed),
                "theme_limit": str(theme_limit),
                "finding_id_display_limit": str(finding_id_limit),
                "diagnostic_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(
    section: CloudAssessmentSection,
    *,
    posture: str,
) -> str:
    if section.status is CloudAssessmentStatus.DISABLED:
        return "Cloud reporting is available, but Cloud analysis was disabled for this assessment."
    if section.status is CloudAssessmentStatus.NOT_REQUESTED:
        return "Cloud assessment was not requested for this run."
    if section.status is CloudAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Cloud reporting is limited because the required "
            "repository-cloud evidence was unavailable or insufficient."
        )
    if section.status is CloudAssessmentStatus.FAILED:
        return (
            "Cloud assessment output is unavailable because analysis did not complete successfully."
        )
    if section.status is CloudAssessmentStatus.NOT_APPLICABLE:
        return "No applicable Cloud assessment content was produced for this repository."

    parts: list[str] = []
    if posture:
        parts.append(posture)
    else:
        count = section.finding_inventory.finding_count
        executed = section.execution_summary.rules_executed
        if count == 0:
            parts.append(
                f"The supported Cloud Hygiene rules executed ({executed}) and "
                "emitted no findings within the available evidence scope. This "
                "result does not establish cloud readiness."
            )
        else:
            parts.append(
                f"The supported Cloud Hygiene assessment identified {count} finding"
                f"{'' if count == 1 else 's'} from repository-cloud evidence."
            )

    if section.synthesis.status.value == "failed":
        parts.append(
            "Cloud synthesis is unavailable for this report; inventory and "
            "execution projections remain."
        )
    elif section.synthesis.status.value in {"not_requested", "disabled"}:
        parts.append(
            "Cloud synthesis was not included; this report projects inventory "
            "and execution facts only."
        )

    return " ".join(parts).strip()


def _buckets(counts: dict[str, int]) -> tuple[CloudReportCountBucket, ...]:
    return tuple(
        CloudReportCountBucket(key=key, count=count) for key, count in sorted(counts.items())
    )


def _inventory(
    section: CloudAssessmentSection,
    *,
    finding_id_limit: int,
) -> CloudReportInventorySummary:
    inventory = section.finding_inventory
    finding_ids = tuple(inventory.finding_ids)[:finding_id_limit]
    none_detected = None
    if inventory.finding_count == 0:
        none_detected = (
            "No Cloud Hygiene findings were emitted within the supported "
            "repository evidence scope. This does not establish cloud readiness."
        )
        _safe(none_detected)
    return CloudReportInventorySummary(
        finding_count=inventory.finding_count,
        finding_ids=finding_ids,
        finding_ids_displayed=len(finding_ids),
        by_rule=_buckets(inventory.rule_counts),
        by_severity=_buckets(inventory.severity_counts),
        by_confidence=_buckets(inventory.confidence_counts),
        none_detected_statement=none_detected,
    )


def _technology_families(
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> CloudReportTechnologyFamilySummary:
    inventory = section.technology_family_inventory
    entries = tuple(
        CloudReportTechnologyFamilyEntry(
            family_id=item.family_id,
            observed=item.observed,
            finding_count=item.finding_count,
            finding_ids=item.finding_ids[:FINDING_ID_DISPLAY_LIMIT],
            technologies=item.technologies,
        )
        for item in sorted(inventory.entries, key=lambda entry: entry.family_id)[:limit]
    )
    return CloudReportTechnologyFamilySummary(
        families_observed=inventory.families_observed,
        families_total=inventory.families_total,
        entries=entries,
    )


def _coverage(section: CloudAssessmentSection) -> CloudReportCoverageSummary:
    areas = tuple(
        CloudReportCoverageAreaView(
            area_id=item.area_id,
            status=item.status.value,
            numerator=item.numerator,
            denominator=item.denominator,
            maturity=item.maturity.value,
        )
        for item in sorted(section.coverage.areas, key=lambda area: area.area_id)
    )
    return CloudReportCoverageSummary(
        evidence_pipeline=section.evidence_pipeline,
        evidence_status=section.metadata.get("evidence_status", ""),
        areas=areas,
    )


def _execution(section: CloudAssessmentSection) -> CloudReportExecutionSummary:
    summary = section.execution_summary
    entries = tuple(
        CloudReportRuleEntryView(
            rule_id=item.rule_id,
            enabled=item.enabled,
            executed=item.executed,
            evaluation_status=item.evaluation_status,
            finding_count=item.finding_count,
        )
        for item in sorted(section.rule_inventory.entries, key=lambda entry: entry.rule_id)
    )
    return CloudReportExecutionSummary(
        rules_planned=summary.cloud_rules_planned,
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
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> tuple[CloudReportThemeView, ...]:
    ordered = sorted(
        section.themes,
        key=lambda item: (item.ordering_key or item.kind.value, item.theme_id),
    )[:limit]
    return tuple(
        CloudReportThemeView(
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
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> tuple[CloudReportConclusionView, ...]:
    ordered = sorted(
        section.conclusions,
        key=lambda item: (item.kind.value, item.conclusion_id),
    )[:limit]
    return tuple(
        CloudReportConclusionView(
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
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> tuple[
    tuple[CloudReportRecommendationView, ...],
    tuple[CloudReportRecommendationGroup, ...],
]:
    ordered = sorted(
        section.recommendations,
        key=lambda item: (item.kind.value, item.recommendation_id),
    )[:limit]
    views = tuple(
        CloudReportRecommendationView(
            recommendation_id=item.recommendation_id,
            kind=item.kind.value,
            title=item.title,
            action=item.action,
            rationale=item.rationale,
            audience=item.audience.value,
            presentation_group=_REC_GROUPS.get(item.kind.value, "Cloud technology signals"),
            conclusion_ids=item.conclusion_ids,
            finding_ids=item.finding_ids,
            rule_ids=item.rule_ids,
            conditional=item.conditional,
        )
        for item in ordered
    )
    by_group: dict[str, list[CloudReportRecommendationView]] = {name: [] for name in _GROUP_ORDER}
    for view in views:
        by_group.setdefault(view.presentation_group, []).append(view)
    groups = tuple(
        CloudReportRecommendationGroup(
            group=name,
            recommendations=tuple(by_group[name]),
        )
        for name in _GROUP_ORDER
        if by_group.get(name)
    )
    extras = tuple(
        CloudReportRecommendationGroup(group=name, recommendations=tuple(items))
        for name, items in sorted(by_group.items())
        if name not in _GROUP_ORDER and items
    )
    return views, groups + extras


def _diagnostics(
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> tuple[CloudReportDiagnosticView, ...]:
    records: list[CloudReportDiagnosticView] = []
    for index, message in enumerate(section.diagnostics):
        records.append(
            CloudReportDiagnosticView(
                diagnostic_id=f"assessment:{index}",
                origin="assessment",
                diagnostic_code="assessment_diagnostic",
                message=str(message)[:400],
            )
        )
    for index, message in enumerate(section.synthesis.diagnostics):
        records.append(
            CloudReportDiagnosticView(
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
    section: CloudAssessmentSection,
    *,
    limit: int,
) -> tuple[CloudReportLimitationView, ...]:
    seen: set[str] = set()
    views: list[CloudReportLimitationView] = []
    for item in sorted(section.limitations, key=lambda lim: lim.limitation_id):
        if item.summary in seen:
            continue
        seen.add(item.summary)
        views.append(
            CloudReportLimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                summary=item.summary,
            )
        )
    return tuple(views[:limit])


def _traceability(
    section: CloudAssessmentSection,
    *,
    finding_id_limit: int,
) -> CloudReportTraceabilityView:
    edges = tuple(
        CloudReportTraceEdgeView(
            edge_id=item.edge_id,
            relation=item.relation.value,
            source_id=item.source_id,
            target_id=item.target_id,
        )
        for item in sorted(section.traceability.edges, key=lambda edge: edge.edge_id)
    )
    finding_ids = tuple(section.finding_ids)[:finding_id_limit]
    return CloudReportTraceabilityView(
        summary=(
            f"{len(edges)} traceability edge"
            f"{'' if len(edges) == 1 else 's'} link the Cloud assessment "
            "section to packs, findings, themes, conclusions, and limitations. "
            "Finding references use Finding IDs only."
        ),
        finding_ids=finding_ids,
        sample_edges=edges[:TRACE_SAMPLE_LIMIT],
        edge_count=len(edges),
    )


__all__ = ["CloudReportAdapter"]
