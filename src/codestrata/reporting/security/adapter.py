"""Adapt SecurityAssessmentSection into presentation SecurityReportSection.

Phase 4.5.6 — presentation only. Does not recollect evidence, rerun rules,
rebuild inventories, or regenerate synthesis.
"""

from __future__ import annotations

from collections import Counter

from codestrata.domain.security.assessment.enums import (
    SecurityAssessmentStatus,
    SecuritySourceRole,
)
from codestrata.domain.security.assessment.models import (
    SecurityAssessmentSection,
    SecurityFindingReference,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS
from codestrata.domain.security.synthesis.enums import SecurityRecommendationKind
from codestrata.reporting.security.models import (
    CONCLUSION_DISPLAY_LIMIT,
    DIAGNOSTIC_DISPLAY_LIMIT,
    FINDING_DISPLAY_LIMIT,
    HOTSPOT_DISPLAY_LIMIT,
    LIMITATION_DISPLAY_LIMIT,
    RECOMMENDATION_DISPLAY_LIMIT,
    SECURITY_REPORT_SECTION_ID,
    SECURITY_REPORT_SECTION_VERSION,
    THEME_DISPLAY_LIMIT,
    TRACE_SAMPLE_LIMIT,
    SecurityReportConclusionView,
    SecurityReportCountBucket,
    SecurityReportCoverageSummary,
    SecurityReportDiagnosticView,
    SecurityReportFindingSummary,
    SecurityReportFindingView,
    SecurityReportHotspotView,
    SecurityReportLimitationView,
    SecurityReportRecommendationGroup,
    SecurityReportRecommendationView,
    SecurityReportSection,
    SecurityReportThemeView,
    SecurityReportTraceabilityView,
    SecurityReportTraceEdgeView,
)

_STATUS_LABELS = {
    SecurityAssessmentStatus.NOT_REQUESTED: "Not requested",
    SecurityAssessmentStatus.DISABLED: "Disabled",
    SecurityAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    SecurityAssessmentStatus.SUCCEEDED: "Succeeded",
    SecurityAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    SecurityAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    SecurityAssessmentStatus.DISABLED: (
        "Security analysis was disabled for this assessment."
    ),
    SecurityAssessmentStatus.NOT_APPLICABLE: (
        "No applicable Security assessment was produced for this repository."
    ),
    SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "Security reporting is limited because required repository-sensitive "
        "evidence was unavailable or insufficient."
    ),
    SecurityAssessmentStatus.SUCCEEDED: (
        "Security assessment completed using supported repository-sensitive "
        "evidence and hygiene rules."
    ),
    SecurityAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Security assessment produced usable results with partial evidence or "
        "rule evaluation limitations."
    ),
    SecurityAssessmentStatus.FAILED: (
        "Security assessment could not be assembled successfully."
    ),
    SecurityAssessmentStatus.NOT_REQUESTED: (
        "Security assessment was not requested."
    ),
}

_FORBIDDEN = (
    "secure repository",
    "security passed",
    "no vulnerabilities",
    "no security issues",
    "low risk",
    "safe to deploy",
    "compliant",
)

_REC_GROUPS = {
    SecurityRecommendationKind.REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL.value: (
        "Repository credential hygiene"
    ),
    SecurityRecommendationKind.ROTATE_AND_REPLACE_LITERAL_CREDENTIALS.value: (
        "Repository credential hygiene"
    ),
    SecurityRecommendationKind.REPLACE_LITERAL_CREDENTIALS_WITH_EXTERNAL_SECRET_REFERENCE.value: (
        "Repository credential hygiene"
    ),
    SecurityRecommendationKind.REPLACE_PLACEHOLDER_CREDENTIALS.value: (
        "Repository credential hygiene"
    ),
    SecurityRecommendationKind.ENABLE_TLS_VERIFICATION.value: (
        "Transport and authentication configuration"
    ),
    SecurityRecommendationKind.ENABLE_HOSTNAME_VERIFICATION.value: (
        "Transport and authentication configuration"
    ),
    SecurityRecommendationKind.ENABLE_AUTHENTICATION.value: (
        "Transport and authentication configuration"
    ),
    SecurityRecommendationKind.RESTRICT_CORS_ORIGINS.value: (
        "Transport and authentication configuration"
    ),
    SecurityRecommendationKind.DISABLE_DEBUG_CONFIGURATION.value: (
        "Development/test configuration"
    ),
    SecurityRecommendationKind.REVIEW_TEST_FIXTURE_SECURITY_OBSERVATIONS.value: (
        "Development/test configuration"
    ),
    SecurityRecommendationKind.CLASSIFY_UNKNOWN_ROLE_FILES.value: (
        "Development/test configuration"
    ),
    SecurityRecommendationKind.REVIEW_SECURITY_FINDING_HOTSPOTS.value: (
        "Repository credential hygiene"
    ),
    SecurityRecommendationKind.CORRECT_MALFORMED_CONFIGURATION.value: (
        "Coverage expansion"
    ),
    SecurityRecommendationKind.EXPAND_SUPPORTED_EVIDENCE_COVERAGE.value: (
        "Coverage expansion"
    ),
    SecurityRecommendationKind.ADD_RUNTIME_SECURITY_VALIDATION.value: (
        "Coverage expansion"
    ),
    SecurityRecommendationKind.ADD_GIT_HISTORY_SECRET_SCANNING.value: (
        "Coverage expansion"
    ),
    SecurityRecommendationKind.ADD_EXTERNAL_DEPENDENCY_VULNERABILITY_ANALYSIS.value: (
        "Coverage expansion"
    ),
    SecurityRecommendationKind.ACKNOWLEDGE_NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE.value: (
        "Coverage expansion"
    ),
}

_GROUP_ORDER = (
    "Repository credential hygiene",
    "Transport and authentication configuration",
    "Development/test configuration",
    "Coverage expansion",
)


def _safe(text: str) -> str:
    lowered = text.lower()
    disclaimer = (
        "does not establish that the repository or deployed application is secure"
    )
    sanitized = (
        lowered.replace(disclaimer, "")
        .replace("does not mean the repository is secure", "")
        .replace("do not prove", "")
    )
    for phrase in _FORBIDDEN:
        if phrase in sanitized:
            raise ValueError(f"forbidden report wording: {phrase}")
    return text


class SecurityReportAdapter:
    """Single boundary from Security assessment domain to report presentation."""

    def adapt(
        self,
        section: SecurityAssessmentSection,
        *,
        include_executive_summary: bool = True,
        include_coverage: bool = True,
        include_findings: bool = True,
        include_themes: bool = True,
        include_conclusions: bool = True,
        include_recommendations: bool = True,
        include_hotspots: bool = True,
        include_diagnostics: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        theme_limit: int = THEME_DISPLAY_LIMIT,
        conclusion_limit: int = CONCLUSION_DISPLAY_LIMIT,
        recommendation_limit: int = RECOMMENDATION_DISPLAY_LIMIT,
        hotspot_limit: int = HOTSPOT_DISPLAY_LIMIT,
        finding_limit: int = FINDING_DISPLAY_LIMIT,
        diagnostic_limit: int = DIAGNOSTIC_DISPLAY_LIMIT,
        limitation_limit: int = LIMITATION_DISPLAY_LIMIT,
    ) -> SecurityReportSection:
        synthesis_status = section.synthesis.status.value
        include_synth_projection = synthesis_status not in {
            "not_requested",
            "disabled",
            "failed",
        }

        finding_summary = (
            _finding_summary(section, finding_limit=finding_limit)
            if include_findings
            else SecurityReportFindingSummary()
        )
        coverage = (
            _coverage(section) if include_coverage else SecurityReportCoverageSummary()
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
        hotspots = (
            _hotspots(section, limit=hotspot_limit) if include_hotspots else ()
        )
        diagnostics = (
            _diagnostics(section, limit=diagnostic_limit)
            if include_diagnostics
            else ()
        )
        limitations = (
            _limitations(section, limit=limitation_limit)
            if include_limitations
            else ()
        )
        traceability = (
            _traceability(section)
            if include_traceability
            else SecurityReportTraceabilityView(summary="Traceability not included.")
        )
        executive = (
            _executive_summary(section)
            if include_executive_summary
            else section.status.value
        )
        return SecurityReportSection(
            section_id=SECURITY_REPORT_SECTION_ID,
            section_version=SECURITY_REPORT_SECTION_VERSION,
            title="Security Intelligence",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(
                section.status, section.status.value
            ),
            assessment_status=section.status.value,
            synthesis_status=synthesis_status,
            assessment_scope=(
                "Repository-level Security hygiene assessment for "
                f"{section.repository_id}"
            ),
            repository_name=section.repository_id,
            security_pack_id=section.security_pack_id,
            security_pack_version=section.security_pack_version,
            executive_summary=_safe(executive),
            coverage_summary=coverage,
            finding_summary=finding_summary,
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
            hotspots=hotspots,
            hotspots_displayed=len(hotspots),
            hotspots_total=len(section.hotspot_inventory.hotspots),
            diagnostics=diagnostics,
            diagnostics_displayed=len(diagnostics),
            diagnostics_total=(
                len(section.diagnostics_summary.evidence_diagnostics)
                + len(section.diagnostics_summary.rule_diagnostics)
                + len(section.diagnostics_summary.assessment_diagnostics)
                + len(section.synthesis.diagnostics)
            ),
            limitations=limitations,
            limitations_displayed=len(limitations),
            limitations_total=len(section.limitations),
            traceability=traceability,
            generated_from_assessment_section_version=section.section_version,
            metadata={
                "assessment_section_id": section.section_id,
                "evidence_pipeline": section.evidence_pipeline,
                "production_finding_count": str(
                    finding_summary.production_finding_count
                ),
                "all_finding_count": str(finding_summary.all_finding_count),
                "theme_limit": str(theme_limit),
                "finding_display_limit": str(finding_limit),
                "hotspot_limit": str(hotspot_limit),
                "diagnostic_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(section: SecurityAssessmentSection) -> str:
    if section.status is SecurityAssessmentStatus.DISABLED:
        return (
            "Security reporting is available, but Security analysis was disabled "
            "for this assessment."
        )
    if section.status is SecurityAssessmentStatus.NOT_REQUESTED:
        return "Security assessment was not requested for this run."
    if section.status is SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Security reporting is limited because the required "
            "repository-sensitive evidence was unavailable or insufficient."
        )
    if section.status is SecurityAssessmentStatus.FAILED:
        return (
            "Security assessment output is unavailable because analysis did not "
            "complete successfully."
        )
    if section.status is SecurityAssessmentStatus.NOT_APPLICABLE:
        return (
            "No applicable Security assessment content was produced for this "
            "repository."
        )

    production = section.finding_inventory.production.finding_count
    test = section.finding_inventory.test.finding_count
    unknown = section.finding_inventory.unknown.finding_count
    extra = test + unknown
    parts: list[str] = []

    if production > 0:
        locations = len(
            {
                item.path
                for item in section.finding_summaries
                if item.path
            }
        )
        text = (
            f"The supported repository Security hygiene assessment identified "
            f"{production} production-role finding"
            f"{'s' if production != 1 else ''} across {locations} repository "
            f"location{'s' if locations != 1 else ''}."
        )
        if extra > 0:
            text += (
                f" An additional {extra} test, fixture, or unknown-role "
                "observations remain visible outside the production-primary view."
            )
        parts.append(text)
    elif test > 0 and unknown == 0:
        parts.append(
            "No production-role findings were emitted by the supported repository "
            f"Security hygiene rules. {test} test or fixture observation"
            f"{'s' if test != 1 else ''} remain available for review."
        )
    elif unknown > 0 and production == 0 and test == 0:
        parts.append(
            "No production-role findings were emitted. "
            f"{unknown} finding{'s' if unknown != 1 else ''} "
            f"{'are' if unknown != 1 else 'is'} associated with files whose "
            "source role could not be classified."
        )
    elif production == 0:
        parts.append(
            "The supported repository Security hygiene rules emitted no "
            "production-role findings within the available evidence scope. This "
            "result does not establish that the repository or deployed "
            "application is secure."
        )
        if test > 0 or unknown > 0:
            parts.append(
                f"{test} test/fixture and {unknown} unknown-role observations "
                "remain visible outside the production-primary view."
            )

    if (
        section.status is SecurityAssessmentStatus.PARTIALLY_SUCCEEDED
        or section.evidence_summary.collection_status == "partially_succeeded"
        or section.evidence_summary.malformed_files > 0
        or section.diagnostics_summary.evidence_diagnostics
    ):
        incomplete = max(
            section.evidence_summary.malformed_files,
            len(section.diagnostics_summary.evidence_diagnostics),
        )
        parts.append(
            "Evidence collection was partial because "
            f"{incomplete} supported input"
            f"{'s' if incomplete != 1 else ''} could not be fully parsed or "
            "inspected."
        )

    if section.synthesis.status.value == "failed":
        parts.append(
            "Security synthesis is unavailable for this report; inventory and "
            "finding projections remain."
        )
    elif section.synthesis.status.value in {"not_requested", "disabled"}:
        parts.append(
            "Security synthesis was not included; this report projects inventory "
            "and coverage facts only."
        )

    return " ".join(parts).strip()


def _finding_view(item: SecurityFindingReference) -> SecurityReportFindingView:
    return SecurityReportFindingView(
        finding_id=item.finding_id,
        rule_id=item.rule_id,
        title=item.title,
        severity=item.severity,
        confidence=item.confidence,
        source_role=item.source_role.value,
        category=item.security_category.value,
        path=item.path,
        explanation=item.explanation,
        remediation=item.remediation,
    )


def _finding_summary(
    section: SecurityAssessmentSection,
    *,
    finding_limit: int,
) -> SecurityReportFindingSummary:
    production = tuple(
        item
        for item in section.all_finding_summaries
        if item.source_role is SecuritySourceRole.PRODUCTION
    )
    additional = tuple(
        item
        for item in section.all_finding_summaries
        if item.source_role is not SecuritySourceRole.PRODUCTION
    )
    all_refs = section.all_finding_summaries
    by_severity = tuple(
        SecurityReportCountBucket(key=key, count=count)
        for key, count in sorted(Counter(item.severity for item in all_refs).items())
    )
    by_category = tuple(
        SecurityReportCountBucket(key=key, count=count)
        for key, count in sorted(
            Counter(item.security_category.value for item in all_refs).items()
        )
    )
    by_rule = tuple(
        SecurityReportCountBucket(key=key, count=count)
        for key, count in sorted(Counter(item.rule_id for item in all_refs).items())
    )
    locations = {item.path for item in all_refs if item.path}
    none_detected = None
    if not production:
        none_detected = (
            "No production-role findings were emitted by the supported "
            "repository Security hygiene rules within the available evidence scope."
        )
    return SecurityReportFindingSummary(
        production_finding_count=len(production),
        test_finding_count=section.finding_inventory.test.finding_count,
        unknown_finding_count=section.finding_inventory.unknown.finding_count,
        all_finding_count=len(all_refs),
        hotspot_count=len(section.hotspot_inventory.hotspots),
        locations_represented=len(locations),
        by_severity=by_severity,
        by_category=by_category,
        by_rule=by_rule,
        production_findings=tuple(
            _finding_view(item) for item in production[:finding_limit]
        ),
        production_findings_displayed=min(len(production), finding_limit),
        additional_observations=tuple(
            _finding_view(item) for item in additional[:finding_limit]
        ),
        additional_observations_displayed=min(len(additional), finding_limit),
        none_detected_statement=none_detected,
    )


def _coverage(section: SecurityAssessmentSection) -> SecurityReportCoverageSummary:
    evidence = section.evidence_summary
    return SecurityReportCoverageSummary(
        evidence_status=evidence.collection_status,
        evidence_schema_name=evidence.evidence_schema_name,
        evidence_schema_version=evidence.evidence_schema_version,
        candidate_artifacts_discovered=evidence.candidate_artifacts_discovered,
        artifacts_inspected=evidence.artifacts_inspected,
        structured_files_parsed=evidence.structured_files_parsed,
        configuration_facts_collected=evidence.configuration_facts_collected,
        rules_registered=section.execution_summary.security_rules_planned
        or len(HYGIENE_RULE_IDS),
        rules_executed=section.execution_summary.rules_executed,
        malformed_files=evidence.malformed_files,
        unsupported_binaries=evidence.unsupported_binaries,
        skipped_files=evidence.skipped_files,
        source_roles_represented=evidence.source_roles_represented,
        formats_represented=evidence.formats_represented,
    )


def _themes(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[SecurityReportThemeView, ...]:
    ordered = sorted(
        section.themes,
        key=lambda item: (item.ordering_key or item.kind.value, item.theme_id),
    )
    return tuple(
        SecurityReportThemeView(
            theme_id=item.theme_id,
            kind=item.kind.value,
            title=item.title,
            summary=item.description,
            scope=item.scope.value,
            source_role=item.source_role.value,
            finding_count=len(item.finding_ids),
            rule_ids=item.rule_ids,
        )
        for item in ordered[:limit]
    )


def _conclusions(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[SecurityReportConclusionView, ...]:
    ordered = sorted(
        section.conclusions,
        key=lambda item: (item.kind.value, item.conclusion_id),
    )
    return tuple(
        SecurityReportConclusionView(
            conclusion_id=item.conclusion_id,
            kind=item.kind.value,
            audience=item.audience.value,
            title=item.title,
            summary=item.summary,
            confidence=item.confidence,
            theme_ids=item.theme_ids,
            finding_count=len(item.finding_ids),
            recommendation_ids=item.recommendation_ids,
        )
        for item in ordered[:limit]
    )


def _recommendations(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[
    tuple[SecurityReportRecommendationView, ...],
    tuple[SecurityReportRecommendationGroup, ...],
]:
    ordered = sorted(
        section.recommendations,
        key=lambda item: (item.kind.value, item.recommendation_id),
    )[:limit]
    views = tuple(
        SecurityReportRecommendationView(
            recommendation_id=item.recommendation_id,
            kind=item.kind.value,
            title=item.title,
            action=item.action,
            rationale=item.rationale,
            audience=item.audience.value,
            presentation_group=_REC_GROUPS.get(item.kind.value, "Coverage expansion"),
            conclusion_ids=item.conclusion_ids,
            conditional=item.conditional,
        )
        for item in ordered
    )
    by_group: dict[str, list[SecurityReportRecommendationView]] = {
        name: [] for name in _GROUP_ORDER
    }
    for view in views:
        by_group.setdefault(view.presentation_group, []).append(view)
    groups = tuple(
        SecurityReportRecommendationGroup(
            group=name,
            recommendations=tuple(by_group[name]),
        )
        for name in _GROUP_ORDER
        if by_group.get(name)
    )
    return views, groups


def _hotspots(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[SecurityReportHotspotView, ...]:
    return tuple(
        SecurityReportHotspotView(
            hotspot_id=item.hotspot_id,
            path=item.path,
            label=item.label,
            total_finding_count=item.total_finding_count,
            production_finding_count=item.production_finding_count,
            test_finding_count=item.test_finding_count,
            unknown_finding_count=item.unknown_finding_count,
            highest_severity=item.highest_severity,
            rule_ids=item.rule_ids,
            categories=item.categories,
            finding_ids=item.finding_ids,
            presentation_order=index,
        )
        for index, item in enumerate(section.hotspot_inventory.hotspots[:limit], start=1)
    )


def _diagnostics(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[SecurityReportDiagnosticView, ...]:
    records: list[SecurityReportDiagnosticView] = []
    for item in section.diagnostics_summary.evidence_diagnostics:
        records.append(
            SecurityReportDiagnosticView(
                diagnostic_id=item.diagnostic_id,
                diagnostic_code=item.diagnostic_code,
                message=item.message,
                origin="evidence",
                path=item.path,
            )
        )
    for item in section.diagnostics_summary.rule_diagnostics:
        records.append(
            SecurityReportDiagnosticView(
                diagnostic_id=item.diagnostic_id,
                diagnostic_code=item.diagnostic_code,
                message=item.message,
                origin="rule",
                path=item.path,
            )
        )
    for item in section.diagnostics_summary.assessment_diagnostics:
        records.append(
            SecurityReportDiagnosticView(
                diagnostic_id=item.diagnostic_id,
                diagnostic_code=item.diagnostic_code,
                message=item.message,
                origin="assessment",
                path=item.path,
            )
        )
    for index, message in enumerate(section.synthesis.diagnostics):
        records.append(
            SecurityReportDiagnosticView(
                diagnostic_id=f"synth-diag:{index}",
                diagnostic_code="synthesis_diagnostic",
                message=str(message)[:400],
                origin="synthesis",
            )
        )
    ordered = sorted(
        records,
        key=lambda item: (item.origin, item.diagnostic_code, item.diagnostic_id),
    )
    return tuple(ordered[:limit])


def _limitations(
    section: SecurityAssessmentSection, *, limit: int
) -> tuple[SecurityReportLimitationView, ...]:
    seen: set[str] = set()
    views: list[SecurityReportLimitationView] = []
    for item in sorted(section.limitations, key=lambda lim: lim.limitation_id):
        key = item.summary.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        views.append(
            SecurityReportLimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                summary=item.summary,
                importance=item.importance,
            )
        )
    return tuple(views[:limit])


def _traceability(
    section: SecurityAssessmentSection,
) -> SecurityReportTraceabilityView:
    edges = sorted(section.traceability.edges, key=lambda item: item.edge_id)
    samples = tuple(
        SecurityReportTraceEdgeView(
            relation=item.relation.value,
            source_id=item.source_id,
            target_id=item.target_id,
        )
        for item in edges[:TRACE_SAMPLE_LIMIT]
    )
    return SecurityReportTraceabilityView(
        edge_count=len(edges),
        sample_edges=samples,
        summary=(
            f"{len(edges)} assessment traceability edges available; "
            f"showing {len(samples)} bounded samples."
        ),
    )


__all__ = ["SecurityReportAdapter"]
