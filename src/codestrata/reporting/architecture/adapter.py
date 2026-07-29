"""Adapt ArchitectureAssessmentSection into presentation ArchitectureReportSection."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.architecture.assessment.enums import (
    ArchitectureAssessmentStatus,
    CoverageAreaStatus,
)
from codestrata.domain.architecture.assessment.models import (
    ArchitectureAssessmentSection,
    ArchitectureCoverageArea,
    ArchitectureFindingReference,
    ArchitectureLimitation,
)
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ConsolidatedRecommendation,
)
from codestrata.reporting.architecture.models import (
    ARCHITECTURE_REPORT_SECTION_ID,
    ARCHITECTURE_REPORT_SECTION_VERSION,
    ArchitectureReportConclusionView,
    ArchitectureReportCoverageItem,
    ArchitectureReportFindingView,
    ArchitectureReportLimitationView,
    ArchitectureReportMetric,
    ArchitectureReportRecommendationView,
    ArchitectureReportSection,
    ArchitectureReportTraceabilityView,
    ArchitectureReportTraceEdgeView,
)

_STATUS_LABELS = {
    ArchitectureAssessmentStatus.NOT_REQUESTED: "Not requested",
    ArchitectureAssessmentStatus.DISABLED: "Disabled",
    ArchitectureAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    ArchitectureAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    ArchitectureAssessmentStatus.SUCCEEDED: "Succeeded",
    ArchitectureAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    ArchitectureAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    ArchitectureAssessmentStatus.DISABLED: (
        "Architecture analysis was disabled for this assessment."
    ),
    ArchitectureAssessmentStatus.NOT_APPLICABLE: (
        "No supported architecture evidence was available for this repository."
    ),
    ArchitectureAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "The repository was processed, but architecture conclusions could not be "
        "established safely from the available evidence."
    ),
    ArchitectureAssessmentStatus.SUCCEEDED: (
        "Architecture assessment completed using static repository evidence."
    ),
    ArchitectureAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Architecture assessment produced useful results with one or more partial "
        "failures or limitations."
    ),
    ArchitectureAssessmentStatus.FAILED: (
        "Architecture assessment could not be assembled safely."
    ),
    ArchitectureAssessmentStatus.NOT_REQUESTED: (
        "Architecture assessment was not requested."
    ),
}

_COVERAGE_LABELS = {
    "extraction_coverage": "Extraction coverage",
    "classification_coverage": "Classification coverage",
    "architectural_unit_coverage": "Architectural-unit coverage",
    "dependency_coverage": "Dependency coverage",
    "framework_coverage": "Framework coverage",
    "build_metadata_coverage": "Build-metadata coverage",
    "enterprise_context_coverage": "Enterprise-context coverage",
}


class ArchitectureReportAdapter:
    """Single boundary from assessment domain to report presentation."""

    def adapt(
        self,
        section: ArchitectureAssessmentSection,
        *,
        include_executive_summary: bool = True,
        include_metrics: bool = True,
        include_conclusions: bool = True,
        include_recommendation_groups: bool = True,
        include_findings: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_strengths: bool = True,
    ) -> ArchitectureReportSection:
        status = section.status
        conclusions = section.conclusions if include_conclusions else ()
        findings = section.finding_summaries if include_findings else ()
        groups = section.recommendation_groups if include_recommendation_groups else ()
        coverage = section.coverage.areas if include_coverage else ()
        limitations = section.limitations if include_limitations else ()

        conclusion_views = tuple(
            _conclusion_view(item) for item in conclusions
        )
        finding_views = tuple(
            _finding_view(item) for item in findings
        )
        recommendation_views = tuple(
            _recommendation_view(item, conclusions) for item in groups
        )
        coverage_views = tuple(_coverage_view(item) for item in coverage)
        limitation_views = tuple(_limitation_view(item) for item in limitations)
        metrics = (
            _metrics(section, conclusions=conclusions, groups=groups, limitations=limitations)
            if include_metrics
            else ()
        )
        strengths = (
            tuple(item.title for item in section.strengths)
            if include_strengths
            else ()
        )
        traceability = (
            _traceability(section)
            if include_traceability
            else ArchitectureReportTraceabilityView(summary="Traceability not included.")
        )
        executive = (
            _executive_summary(section, conclusions=conclusions)
            if include_executive_summary
            else section.status.value
        )
        return ArchitectureReportSection(
            section_id=ARCHITECTURE_REPORT_SECTION_ID,
            section_version=ARCHITECTURE_REPORT_SECTION_VERSION,
            title="Architecture Assessment",
            status=status.value,
            status_label=_STATUS_LABELS.get(status, status.value),
            status_summary=_STATUS_SUMMARIES.get(status, status.value),
            assessment_scope=(
                f"Repository-level static architecture assessment for {section.repository_id}"
            ),
            repository_name=section.repository_id,
            architecture_pack_id=section.architecture_pack_id,
            architecture_pack_version=section.architecture_pack_version,
            executive_summary=executive,
            key_metrics=metrics,
            coverage_summary=coverage_views,
            conclusions=conclusion_views,
            findings=finding_views,
            recommendation_groups=recommendation_views,
            strengths=strengths,
            limitations=limitation_views,
            traceability_summary=traceability,
            enterprise_context_used=section.enterprise_context_used,
            generated_from_assessment_section_version=section.section_version,
            include_strengths_heading=bool(strengths),
            metadata={
                "assessment_section_id": section.section_id,
                "evidence_pipeline": section.evidence_pipeline,
                "graph_fingerprint": section.graph_fingerprint or "",
                "configuration_fingerprint": section.configuration_fingerprint or "",
            },
        )


def _executive_summary(
    section: ArchitectureAssessmentSection,
    *,
    conclusions: Sequence[ArchitectureConclusion],
) -> str:
    if section.status is ArchitectureAssessmentStatus.DISABLED:
        return (
            "Architecture reporting is available, but architecture analysis was disabled "
            "for this assessment."
        )
    if section.status is ArchitectureAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Architecture assessment could not establish safe conclusions from the "
            "available repository evidence. Findings and conclusions are not presented "
            "as confirmed architecture concerns."
        )
    if section.status is ArchitectureAssessmentStatus.FAILED:
        return (
            "Architecture assessment failed to assemble a usable section. Existing "
            "non-architecture report content remains available."
        )
    if section.status is ArchitectureAssessmentStatus.NOT_APPLICABLE:
        return (
            "No supported architecture evidence was available for this repository "
            "assessment."
        )

    finding_count = len(section.finding_ids)
    conclusion_count = len(conclusions)
    themes = _theme_text(conclusions)
    coverage_note = _coverage_note(section)
    conclusions_note = (
        f" These were consolidated into {conclusion_count} architecture conclusion"
        f"{'s' if conclusion_count != 1 else ''}"
        + (f": {themes}." if themes else ".")
        if conclusion_count
        else (
            " Architecture conclusions were not generated for this assessment; "
            "findings are presented without consolidated interpretation."
            if finding_count
            else " No architecture findings were identified under the current rules and coverage."
        )
    )
    impact = (
        "Business impact was not assessed."
        if not section.enterprise_context_used
        else "Enterprise context was supplied for organizational relevance where cited."
    )
    return (
        f"The architecture assessment identified {finding_count} visible finding"
        f"{'s' if finding_count != 1 else ''} across the analyzed repository."
        f"{conclusions_note} The assessment is based on static repository evidence. "
        f"{coverage_note} {impact}"
    ).strip()


def _theme_text(conclusions: Sequence[ArchitectureConclusion]) -> str:
    titles: list[str] = []
    seen: set[str] = set()
    for item in conclusions:
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


def _coverage_note(section: ArchitectureAssessmentSection) -> str:
    extraction = next(
        (area for area in section.coverage.areas if area.area_id == "extraction_coverage"),
        None,
    )
    classification = next(
        (
            area
            for area in section.coverage.areas
            if area.area_id == "classification_coverage"
        ),
        None,
    )
    parts: list[str] = []
    if extraction is not None and extraction.ratio is not None:
        if extraction.ratio >= 0.999:
            parts.append(
                "Extraction coverage was complete for the analyzed source set"
            )
        else:
            parts.append(
                f"Extraction coverage was {extraction.ratio:.0%} for the analyzed source set"
            )
    if classification is not None and classification.ratio is not None:
        if classification.status is CoverageAreaStatus.PARTIAL or classification.ratio < 0.75:
            parts.append(
                f"architectural classification coverage was partial ({classification.ratio:.1%})"
            )
        else:
            parts.append(
                f"architectural classification coverage was {classification.ratio:.0%}"
            )
    if not parts:
        return "Coverage details are included in the architecture section."
    if len(parts) == 1:
        return parts[0] + "."
    return parts[0] + ", while " + parts[1] + "."


def _metrics(
    section: ArchitectureAssessmentSection,
    *,
    conclusions: Sequence[object],
    groups: Sequence[object],
    limitations: Sequence[object],
) -> tuple[ArchitectureReportMetric, ...]:
    extraction = next(
        (area for area in section.coverage.areas if area.area_id == "extraction_coverage"),
        None,
    )
    classification = next(
        (
            area
            for area in section.coverage.areas
            if area.area_id == "classification_coverage"
        ),
        None,
    )
    return (
        ArchitectureReportMetric(
            key="visible_findings",
            label="Visible findings",
            value=str(len(section.finding_ids)),
        ),
        ArchitectureReportMetric(
            key="conclusions",
            label="Conclusions",
            value=str(len(conclusions)),
        ),
        ArchitectureReportMetric(
            key="recommendation_groups",
            label="Recommendation groups",
            value=str(len(groups)),
        ),
        ArchitectureReportMetric(
            key="extraction_coverage",
            label="Extraction coverage",
            value=_ratio_or_unavailable(extraction.ratio if extraction else None),
        ),
        ArchitectureReportMetric(
            key="classification_coverage",
            label="Classification coverage",
            value=_ratio_or_unavailable(classification.ratio if classification else None),
            note="Partial classification reduces certainty of layer-direction claims.",
        ),
        ArchitectureReportMetric(
            key="limitations",
            label="Limitations",
            value=str(len(limitations)),
        ),
    )


def _ratio_or_unavailable(ratio: float | None) -> str:
    if ratio is None:
        return "Unavailable"
    return f"{ratio:.1%}"


def _conclusion_view(item: ArchitectureConclusion) -> ArchitectureReportConclusionView:
    severity = item.severity_summary
    severity_text = (
        f"Highest {severity.highest_severity}; "
        f"{severity.source_finding_count} source finding"
        f"{'s' if severity.source_finding_count != 1 else ''}"
    )
    return ArchitectureReportConclusionView(
        conclusion_id=item.conclusion_id,
        title=item.title,
        category=item.category,
        summary=item.summary,
        materiality=item.materiality.value,
        confidence=item.confidence.value,
        affected_scope=item.affected_scope,
        severity_summary=severity_text,
        primary_finding_id=item.primary_finding_id,
        supporting_finding_count=max(0, len(item.source_finding_ids) - 1),
        modernization_relevance=item.modernization_relevance.value,
        business_impact=_business_impact_label(item.business_impact),
        recommendation_group_ids=item.consolidated_recommendation_ids,
        limitations=item.limitations,
    )


def _finding_view(item: ArchitectureFindingReference) -> ArchitectureReportFindingView:
    conclusion_ids = item.conclusion_ids
    scope = item.affected_scope
    title = item.title
    return ArchitectureReportFindingView(
        finding_id=item.finding_id,
        title=title,
        rule_id=item.rule_id,
        severity=item.severity,
        confidence=item.confidence,
        affected_scope=scope,
        summary=title,
        conclusion_ids=conclusion_ids,
        recommendation_ids=item.recommendation_ids,
        evidence_count=item.evidence_count,
        status=item.status,
        linked_to_conclusion=bool(conclusion_ids),
    )


def _recommendation_view(
    item: ConsolidatedRecommendation,
    conclusions: Sequence[ArchitectureConclusion],
) -> ArchitectureReportRecommendationView:
    source_findings = item.source_finding_ids
    source_conclusion_ids = tuple(
        sorted(
            {
                conclusion.conclusion_id
                for conclusion in conclusions
                if set(conclusion.source_finding_ids).intersection(source_findings)
            }
        )
    )
    primary = item.primary_action.strip()
    actions = (primary,) if primary else ()
    rationale = item.rationale.strip() or "Coordinated response to related findings."
    wave = item.modernization_wave
    wave_value = getattr(wave, "value", str(wave))
    return ArchitectureReportRecommendationView(
        recommendation_group_id=item.recommendation_group_id,
        title=item.title,
        objective=primary or item.title,
        rationale=rationale,
        source_conclusion_ids=source_conclusion_ids,
        source_finding_ids=source_findings,
        recommended_actions=actions,
        validation_steps=item.validation_steps,
        modernization_wave=str(wave_value),
        prerequisites=item.prerequisites,
        limitations=item.limitations,
    )


def _coverage_view(item: ArchitectureCoverageArea) -> ArchitectureReportCoverageItem:
    area_id = item.area_id
    status_value = item.status.value
    ratio = item.ratio
    label = _COVERAGE_LABELS.get(area_id, area_id.replace("_", " ").title())
    display = _coverage_display(status_value, ratio, area_id)
    note = item.limitations[0] if item.limitations else None
    return ArchitectureReportCoverageItem(
        area_id=area_id,
        label=label,
        status=status_value,
        display=display,
        ratio=ratio,
        note=note,
    )


def _coverage_display(status: str, ratio: float | None, area_id: str) -> str:
    if status == CoverageAreaStatus.UNSUPPORTED.value:
        return "Not measured by the current provider set."
    if status == CoverageAreaStatus.NOT_APPLICABLE.value:
        if "enterprise" in area_id:
            return "Enterprise context was not supplied for this repository assessment."
        return "Not applicable for this assessment."
    if status == CoverageAreaStatus.UNKNOWN.value or ratio is None:
        return "Unavailable"
    if status == CoverageAreaStatus.PARTIAL.value:
        return f"Partial ({ratio:.1%})."
    if ratio >= 0.999:
        return "Complete for the analyzed source set."
    return f"Measured ({ratio:.1%})."


def _limitation_view(item: ArchitectureLimitation) -> ArchitectureReportLimitationView:
    return ArchitectureReportLimitationView(
        limitation_id=item.limitation_id,
        category=item.category.value,
        summary=item.summary,
        importance=item.importance,
    )


def _traceability(section: ArchitectureAssessmentSection) -> ArchitectureReportTraceabilityView:
    edges = section.traceability.edges
    relation_types = tuple(sorted({edge.relation.value for edge in edges}))
    sample = tuple(
        ArchitectureReportTraceEdgeView(
            relation=edge.relation.value,
            source_id=edge.source_id,
            target_id=edge.target_id,
        )
        for edge in edges[:12]
    )
    return ArchitectureReportTraceabilityView(
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


def _business_impact_label(raw: str) -> str:
    value = (raw or "unknown").strip().lower()
    if value in {"unknown", "not_assessed", "not assessed"}:
        return "Unknown"
    if value in {"provided", "enterprise", "declared"}:
        return "Provided enterprise context"
    return "Not assessed"
