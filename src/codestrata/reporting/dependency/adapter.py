"""Adapt DependencyAssessmentSection into presentation DependencyReportSection.

Phase 4.4.6 — presentation only. Does not reparse manifests, recollect evidence,
reevaluate rules, or reconstruct synthesis.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencySourceRole,
)
from codestrata.domain.dependency.assessment.models import (
    DependencyAssessmentSection,
    DependencyFindingReference,
    DependencyHotspot,
    DependencyLimitation,
)
from codestrata.domain.dependency.synthesis.enums import (
    DependencyConclusionAudience,
    DependencyConclusionKind,
    DependencyRecommendationKind,
)
from codestrata.domain.dependency.synthesis.models import (
    DependencyConclusion,
    DependencyRecommendation,
)
from codestrata.reporting.dependency.models import (
    DEPENDENCY_REPORT_SECTION_ID,
    DEPENDENCY_REPORT_SECTION_VERSION,
    DIAGNOSTIC_SAMPLE_LIMIT,
    FINDING_DISPLAY_LIMIT,
    TOP_MANIFEST_HOTSPOTS,
    TRACE_SAMPLE_LIMIT,
    DependencyReportAudienceGroup,
    DependencyReportConclusionView,
    DependencyReportCoverageView,
    DependencyReportDiagnosticView,
    DependencyReportFindingView,
    DependencyReportHotspotView,
    DependencyReportLandscapeCount,
    DependencyReportLimitationView,
    DependencyReportProductionHealth,
    DependencyReportRecommendationView,
    DependencyReportSection,
    DependencyReportTestObservations,
    DependencyReportTraceabilityView,
    DependencyReportTraceEdgeView,
)

_STATUS_LABELS = {
    DependencyAssessmentStatus.NOT_REQUESTED: "Not requested",
    DependencyAssessmentStatus.DISABLED: "Disabled",
    DependencyAssessmentStatus.NOT_APPLICABLE: "Not applicable",
    DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    DependencyAssessmentStatus.SUCCEEDED: "Succeeded",
    DependencyAssessmentStatus.PARTIALLY_SUCCEEDED: "Partially succeeded",
    DependencyAssessmentStatus.FAILED: "Failed",
}

_STATUS_SUMMARIES = {
    DependencyAssessmentStatus.DISABLED: (
        "Dependency analysis was disabled for this assessment."
    ),
    DependencyAssessmentStatus.NOT_APPLICABLE: (
        "No supported dependency evidence was available for this repository."
    ),
    DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE: (
        "The repository was processed, but dependency conclusions could not be "
        "established safely from the available evidence."
    ),
    DependencyAssessmentStatus.SUCCEEDED: (
        "Dependency assessment completed using declared-manifest evidence."
    ),
    DependencyAssessmentStatus.PARTIALLY_SUCCEEDED: (
        "Dependency assessment produced useful results with one or more partial "
        "failures or limitations."
    ),
    DependencyAssessmentStatus.FAILED: (
        "Dependency assessment could not be assembled safely."
    ),
    DependencyAssessmentStatus.NOT_REQUESTED: (
        "Dependency assessment was not requested."
    ),
}

_TRACE_RELATIONS = {
    "recommendation_to_conclusion",
    "conclusion_to_theme",
    "section_to_theme",
    "conclusion_to_finding",
    "conclusion_to_hotspot",
    "conclusion_to_manifest",
    "conclusion_to_diagnostic",
}

_NONE_DETECTED = (
    "No production dependency hygiene findings were detected by the enabled "
    "repository-local rules."
)


class DependencyReportAdapter:
    """Single boundary from assessment domain to report presentation."""

    def adapt(
        self,
        section: DependencyAssessmentSection,
        *,
        include_executive_summary: bool = True,
        include_landscape: bool = True,
        include_production_health: bool = True,
        include_test_observations: bool = True,
        include_hotspots: bool = True,
        include_conclusions: bool = True,
        include_recommendations: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        hotspot_limit: int = TOP_MANIFEST_HOTSPOTS,
        finding_limit: int = FINDING_DISPLAY_LIMIT,
        diagnostic_limit: int = DIAGNOSTIC_SAMPLE_LIMIT,
    ) -> DependencyReportSection:
        production_refs = tuple(
            item
            for item in section.all_finding_summaries
            if item.source_role is DependencySourceRole.PRODUCTION
        )
        test_refs = tuple(
            item
            for item in section.all_finding_summaries
            if item.source_role is DependencySourceRole.TEST
        )
        production_health = (
            _production_health(section, production_refs, finding_limit=finding_limit)
            if include_production_health
            else DependencyReportProductionHealth()
        )
        test_observations = (
            _test_observations(section, test_refs, finding_limit=finding_limit)
            if include_test_observations
            else DependencyReportTestObservations()
        )
        landscape = _landscape(section) if include_landscape else ()
        hotspots = (
            _hotspots(section, limit=hotspot_limit) if include_hotspots else ()
        )
        conclusion_groups = (
            _audience_groups(
                conclusions=section.conclusions,
                recommendations=(),
                include_conclusions=True,
                include_recommendations=False,
            )
            if include_conclusions
            else ()
        )
        recommendation_groups = (
            _audience_groups(
                conclusions=(),
                recommendations=section.recommendations,
                include_conclusions=False,
                include_recommendations=True,
            )
            if include_recommendations
            else ()
        )
        conclusions = (
            tuple(_conclusion_view(item) for item in section.conclusions)
            if include_conclusions
            else ()
        )
        recommendations = (
            tuple(_recommendation_view(item) for item in section.recommendations)
            if include_recommendations
            else ()
        )
        coverage = (
            _coverage(section, diagnostic_limit=diagnostic_limit)
            if include_coverage
            else DependencyReportCoverageView()
        )
        hygiene = (
            *production_health.findings,
            *test_observations.findings,
        )
        limitations = (
            tuple(_limitation_view(item) for item in section.limitations)
            if include_limitations
            else ()
        )
        traceability = (
            _traceability(section)
            if include_traceability
            else DependencyReportTraceabilityView(
                summary="Traceability not included."
            )
        )
        executive = (
            _executive_summary(section)
            if include_executive_summary
            else section.status.value
        )
        return DependencyReportSection(
            section_id=DEPENDENCY_REPORT_SECTION_ID,
            section_version=DEPENDENCY_REPORT_SECTION_VERSION,
            title="Dependency Assessment",
            status=section.status.value,
            status_label=_STATUS_LABELS.get(section.status, section.status.value),
            status_summary=_STATUS_SUMMARIES.get(section.status, section.status.value),
            assessment_scope=(
                "Repository-level declared-dependency assessment for "
                f"{section.repository_id}"
            ),
            repository_name=section.repository_id,
            dependency_pack_id=section.dependency_pack_id,
            dependency_pack_version=section.dependency_pack_version,
            executive_summary=executive,
            landscape=landscape,
            production_health=production_health,
            test_observations=test_observations,
            hygiene_findings=hygiene,
            hygiene_findings_displayed=len(hygiene),
            hygiene_findings_total=len(production_refs) + len(test_refs),
            manifest_hotspots=hotspots,
            conclusions=conclusions,
            recommendations=recommendations,
            conclusion_groups=conclusion_groups,
            recommendation_groups=recommendation_groups,
            coverage=coverage,
            diagnostics=coverage.diagnostic_samples,
            diagnostics_total=coverage.diagnostic_total,
            limitations=limitations,
            traceability=traceability,
            generated_from_assessment_section_version=section.section_version,
            metadata={
                "assessment_section_id": section.section_id,
                "evidence_pipeline": section.evidence_pipeline,
                "evidence_fingerprint": section.evidence_fingerprint or "",
                "configuration_fingerprint": section.configuration_fingerprint or "",
                "production_finding_count": str(len(production_refs)),
                "test_finding_count": str(len(test_refs)),
                "hotspot_limit": str(hotspot_limit),
                "finding_display_limit": str(finding_limit),
                "diagnostic_sample_limit": str(diagnostic_limit),
            },
        )


def _executive_summary(section: DependencyAssessmentSection) -> str:
    if section.status is DependencyAssessmentStatus.DISABLED:
        return (
            "Dependency reporting is available, but dependency analysis was "
            "disabled for this assessment."
        )
    if section.status is DependencyAssessmentStatus.NOT_REQUESTED:
        return "Dependency assessment was not requested for this run."
    if section.status is DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE:
        return (
            "Dependency assessment could not establish safe conclusions from the "
            "available repository evidence."
        )
    if section.status is DependencyAssessmentStatus.FAILED:
        return (
            "Dependency assessment failed to assemble a usable section. Existing "
            "non-dependency report content remains available."
        )
    if section.status is DependencyAssessmentStatus.NOT_APPLICABLE:
        return (
            "No supported dependency evidence was available for this repository "
            "assessment."
        )

    production = section.execution_summary.production_finding_count
    test = section.execution_summary.test_finding_count
    kinds = {item.kind for item in section.conclusions}
    parts: list[str] = []

    if production == 0:
        parts.append(_NONE_DETECTED)
    else:
        parts.append(
            f"The dependency assessment identified {production} production "
            f"hygiene finding{'s' if production != 1 else ''} under the enabled "
            "repository-local rules."
        )

    if test > 0:
        parts.append(
            f"{test} test/fixture finding{'s' if test != 1 else ''} "
            f"{'were' if test != 1 else 'was'} recorded separately and "
            "do not contribute to the production-primary view."
        )

    if DependencyConclusionKind.UNSUPPORTED_RESOLUTION_COVERAGE in kinds:
        parts.append(
            "Some version expressions could not be evaluated because supported "
            "static collection does not inspect all Gradle resolution mechanisms."
        )

    if DependencyConclusionKind.DECLARED_DEPENDENCIES_ONLY in kinds:
        parts.append(
            "This assessment covers declared-manifest facts only and does not "
            "represent a resolved or transitive dependency graph."
        )

    parts.append(
        "No composite dependency-health score, vulnerability verdict, license "
        "assessment, or latest-version advice is included."
    )
    return " ".join(parts).strip()


def _landscape(
    section: DependencyAssessmentSection,
) -> tuple[DependencyReportLandscapeCount, ...]:
    evidence = section.evidence_summary
    decls = section.declaration_inventory
    agg = section.aggregation_inventory
    items: list[DependencyReportLandscapeCount] = [
        DependencyReportLandscapeCount(
            key="declarations_collected",
            label="Declarations collected",
            count=evidence.declarations_collected,
            group="totals",
        ),
        DependencyReportLandscapeCount(
            key="manifests_supported",
            label="Supported manifests",
            count=evidence.manifests_supported,
            group="totals",
        ),
        DependencyReportLandscapeCount(
            key="production_active",
            label="Production active dependencies",
            count=decls.production.active_declaration_count,
            group="declaration_kind",
        ),
        DependencyReportLandscapeCount(
            key="production_management",
            label="Production dependency-management declarations",
            count=decls.production.dependency_management_count,
            group="declaration_kind",
        ),
        DependencyReportLandscapeCount(
            key="production_plugins",
            label="Production build plugins",
            count=decls.production.plugin_count,
            group="declaration_kind",
        ),
        DependencyReportLandscapeCount(
            key="production_test_dev",
            label="Production test/development declarations",
            count=decls.production.test_or_development_count,
            group="declaration_kind",
        ),
        DependencyReportLandscapeCount(
            key="test_declarations",
            label="Test/fixture declarations",
            count=decls.test.declaration_count,
            group="source_role",
        ),
        DependencyReportLandscapeCount(
            key="unknown_declarations",
            label="Unknown-role declarations",
            count=decls.unknown.declaration_count,
            group="source_role",
        ),
    ]
    for bucket in agg.by_ecosystem:
        items.append(
            DependencyReportLandscapeCount(
                key=f"ecosystem:{bucket.label}",
                label=f"Ecosystem: {bucket.label}",
                count=bucket.count,
                group="ecosystem",
            )
        )
    for bucket in agg.by_manifest_type:
        items.append(
            DependencyReportLandscapeCount(
                key=f"manifest_type:{bucket.label}",
                label=f"Manifest type: {bucket.label}",
                count=bucket.count,
                group="manifest_type",
            )
        )
    for bucket in agg.by_version_resolution_status:
        items.append(
            DependencyReportLandscapeCount(
                key=f"version_resolution:{bucket.label}",
                label=f"Version resolution: {bucket.label}",
                count=bucket.count,
                group="version_resolution",
            )
        )
    return tuple(items)


def _finding_view(item: DependencyFindingReference) -> DependencyReportFindingView:
    from codestrata.application.rules.dependency.recommendations import recommendation_for

    explanation = item.title
    if item.normalized_identity:
        explanation = f"{item.title} ({item.normalized_identity})"
    context_parts = [item.source_role.value]
    if item.ecosystem:
        context_parts.append(item.ecosystem)
    return DependencyReportFindingView(
        finding_id=item.finding_id,
        rule_id=item.rule_id,
        title=item.title,
        severity=item.severity,
        confidence=item.confidence,
        source_role=item.source_role.value,
        path=item.path,
        ecosystem=item.ecosystem,
        normalized_identity=item.normalized_identity,
        explanation=explanation,
        remediation=recommendation_for(item.rule_id),
        original_declaration=item.normalized_identity,
        declaration_context=" · ".join(context_parts),
        evidence_ids=item.evidence_ids[:8],
        evidence_count=item.evidence_count or len(item.evidence_ids),
    )


def _production_health(
    section: DependencyAssessmentSection,
    refs: Sequence[DependencyFindingReference],
    *,
    finding_limit: int,
) -> DependencyReportProductionHealth:
    displayed = tuple(_finding_view(item) for item in refs[:finding_limit])
    prod_conclusions = tuple(
        _conclusion_view(item)
        for item in section.conclusions
        if item.audience is DependencyConclusionAudience.PRODUCTION_HEALTH
    )
    prod_recs = tuple(
        _recommendation_view(item)
        for item in section.recommendations
        if item.audience is DependencyConclusionAudience.PRODUCTION_HEALTH
        and item.kind
        is not DependencyRecommendationKind.ACKNOWLEDGE_NO_PRODUCTION_FINDINGS
    )
    # When zero findings, omit remediation cards (only keep none-detected statement).
    if not refs:
        prod_recs = ()
    manifests = tuple(
        sorted({item.path for item in refs if item.path})
    )
    return DependencyReportProductionHealth(
        finding_count=len(refs),
        findings_displayed=len(displayed),
        findings_total=len(refs),
        none_detected_statement=_NONE_DETECTED if not refs else None,
        findings=displayed,
        affected_manifests=manifests,
        conclusions=prod_conclusions,
        recommendations=prod_recs,
    )


def _test_observations(
    section: DependencyAssessmentSection,
    refs: Sequence[DependencyFindingReference],
    *,
    finding_limit: int,
) -> DependencyReportTestObservations:
    if not refs:
        return DependencyReportTestObservations()
    displayed = tuple(_finding_view(item) for item in refs[:finding_limit])
    conclusions = tuple(
        _conclusion_view(item)
        for item in section.conclusions
        if item.audience is DependencyConclusionAudience.TEST_OBSERVATION
    )
    recommendations = tuple(
        _recommendation_view(item)
        for item in section.recommendations
        if item.audience is DependencyConclusionAudience.TEST_OBSERVATION
    )
    return DependencyReportTestObservations(
        present=True,
        finding_count=len(refs),
        findings_displayed=len(displayed),
        findings_total=len(refs),
        title="Test and fixture observations",
        summary=(
            f"{len(refs)} test/fixture dependency hygiene finding"
            f"{'s' if len(refs) != 1 else ''} "
            f"{'are' if len(refs) != 1 else 'is'} shown separately and "
            "do not contribute to the production-primary view."
        ),
        findings=displayed,
        affected_manifests=tuple(sorted({item.path for item in refs if item.path})),
        conclusions=conclusions,
        recommendations=recommendations,
    )


def _hotspot_view(item: DependencyHotspot, *, order: int) -> DependencyReportHotspotView:
    return DependencyReportHotspotView(
        hotspot_id=item.hotspot_id,
        path=item.path,
        source_role=item.source_role.value,
        ecosystem=item.ecosystem,
        manifest_type=item.manifest_type,
        active_declaration_count=item.active_declaration_count,
        dependency_management_count=item.dependency_management_count,
        plugin_count=item.plugin_count,
        hygiene_finding_count=item.hygiene_finding_count,
        distinct_rule_count=len(item.distinct_rule_ids),
        highest_severity=item.highest_severity,
        diagnostics_count=item.diagnostics_count,
        presentation_order=order,
    )


def _hotspots(
    section: DependencyAssessmentSection,
    *,
    limit: int,
) -> tuple[DependencyReportHotspotView, ...]:
    # Preserve assessment presentation order: production, then test, then unknown.
    ordered = (
        *section.hotspot_inventory.production,
        *section.hotspot_inventory.test,
        *section.hotspot_inventory.unknown,
    )
    # Prefer hotspots with findings/diagnostics first within the already-ordered list
    # without inventing a priority score — assessment already ordered within role.
    sliced = ordered[: max(0, limit)]
    return tuple(
        _hotspot_view(item, order=index) for index, item in enumerate(sliced, start=1)
    )


def _conclusion_view(item: DependencyConclusion) -> DependencyReportConclusionView:
    return DependencyReportConclusionView(
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


def _recommendation_view(
    item: DependencyRecommendation,
) -> DependencyReportRecommendationView:
    return DependencyReportRecommendationView(
        recommendation_id=item.recommendation_id,
        kind=item.kind.value,
        title=item.title,
        action=item.action,
        rationale=item.rationale,
        conditional=item.conditional,
        audience=item.audience.value,
        conclusion_ids=item.conclusion_ids,
    )


def _audience_groups(
    *,
    conclusions: Sequence[DependencyConclusion],
    recommendations: Sequence[DependencyRecommendation],
    include_conclusions: bool,
    include_recommendations: bool,
) -> tuple[DependencyReportAudienceGroup, ...]:
    by_audience: dict[str, dict[str, list[object]]] = defaultdict(
        lambda: {"conclusions": [], "recommendations": []}
    )
    if include_conclusions:
        for conclusion in conclusions:
            by_audience[conclusion.audience.value]["conclusions"].append(
                _conclusion_view(conclusion)
            )
    if include_recommendations:
        for recommendation in recommendations:
            by_audience[recommendation.audience.value]["recommendations"].append(
                _recommendation_view(recommendation)
            )
    groups: list[DependencyReportAudienceGroup] = []
    order = (
        DependencyConclusionAudience.PRODUCTION_HEALTH.value,
        DependencyConclusionAudience.TEST_OBSERVATION.value,
        DependencyConclusionAudience.COVERAGE.value,
        DependencyConclusionAudience.REPOSITORY.value,
        DependencyConclusionAudience.STATUS.value,
    )
    for audience in order:
        bucket = by_audience.get(audience)
        if not bucket:
            continue
        if not bucket["conclusions"] and not bucket["recommendations"]:
            continue
        groups.append(
            DependencyReportAudienceGroup(
                audience=audience,
                conclusions=tuple(bucket["conclusions"]),  # type: ignore[arg-type]
                recommendations=tuple(bucket["recommendations"]),  # type: ignore[arg-type]
            )
        )
    for audience, bucket in sorted(by_audience.items()):
        if audience in order:
            continue
        if not bucket["conclusions"] and not bucket["recommendations"]:
            continue
        groups.append(
            DependencyReportAudienceGroup(
                audience=audience,
                conclusions=tuple(bucket["conclusions"]),  # type: ignore[arg-type]
                recommendations=tuple(bucket["recommendations"]),  # type: ignore[arg-type]
            )
        )
    return tuple(groups)


def _coverage(
    section: DependencyAssessmentSection,
    *,
    diagnostic_limit: int,
) -> DependencyReportCoverageView:
    evidence = section.evidence_summary
    diagnostics = section.diagnostics_summary.records
    samples = tuple(
        DependencyReportDiagnosticView(
            diagnostic_id=item.diagnostic_id,
            diagnostic_code=item.diagnostic_code,
            message=item.message,
            path=item.path,
            source_role=item.source_role.value,
            ecosystem=item.ecosystem,
        )
        for item in diagnostics[: max(0, diagnostic_limit)]
    )
    return DependencyReportCoverageView(
        evidence_schema_version=evidence.schema_version,
        evidence_fingerprint=evidence.evidence_fingerprint,
        evidence_status=evidence.evidence_status,
        manifests_discovered=evidence.manifests_discovered,
        manifests_supported=evidence.manifests_supported,
        manifests_parsed=evidence.manifests_parsed,
        manifests_partially_parsed=evidence.manifests_partially_parsed,
        manifests_failed=evidence.manifests_failed,
        production_parse_failures=section.execution_summary.production_parse_failures,
        test_fixture_parse_failures=(
            section.execution_summary.test_fixture_parse_failures
        ),
        unsupported_construct_count=evidence.unsupported_construct_count,
        proven_unresolved_count=evidence.proven_unresolved_count,
        unsupported_resolution_count=evidence.unsupported_resolution_count,
        diagnostic_total=len(diagnostics),
        diagnostic_samples=samples,
    )


def _limitation_view(item: DependencyLimitation) -> DependencyReportLimitationView:
    return DependencyReportLimitationView(
        limitation_id=item.limitation_id,
        category=item.category.value,
        summary=item.summary,
        importance=item.importance,
    )


def _traceability(
    section: DependencyAssessmentSection,
) -> DependencyReportTraceabilityView:
    edges = [
        edge
        for edge in section.traceability.edges
        if edge.relation.value in _TRACE_RELATIONS
    ]
    # Prefer recommendation→conclusion and conclusion→theme first.
    priority = {
        "recommendation_to_conclusion": 0,
        "conclusion_to_theme": 1,
        "conclusion_to_finding": 2,
        "conclusion_to_hotspot": 3,
        "conclusion_to_manifest": 4,
        "conclusion_to_diagnostic": 5,
        "section_to_theme": 6,
    }
    edges = sorted(
        edges,
        key=lambda item: (
            priority.get(item.relation.value, 9),
            item.edge_id,
        ),
    )
    sample = tuple(
        DependencyReportTraceEdgeView(
            relation=edge.relation.value,
            source_id=edge.source_id,
            target_id=edge.target_id,
        )
        for edge in edges[:TRACE_SAMPLE_LIMIT]
    )
    relation_types = tuple(sorted({edge.relation for edge in sample}))
    return DependencyReportTraceabilityView(
        edge_count=len(section.traceability.edges),
        relation_types=relation_types,
        sample_edges=sample,
        summary=(
            f"Showing {len(sample)} of {len(section.traceability.edges)} "
            "traceability edges (recommendation→conclusion, conclusion→theme/"
            "finding/hotspot/manifest/diagnostic)."
        ),
    )
