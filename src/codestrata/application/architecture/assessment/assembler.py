"""Assemble ArchitectureAssessmentSection from existing findings and conclusions."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.architecture.conclusions.helpers import scope_from_findings
from codestrata.application.architecture.conclusions.result import ArchitectureConclusionResult
from codestrata.domain.architecture.assessment.enums import (
    ArchitectureAssessmentStatus,
    ArchitectureLimitationCategory,
    CoverageAreaStatus,
    CoverageMaturity,
    TraceabilityRelation,
)
from codestrata.domain.architecture.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_configuration_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.architecture.assessment.models import (
    ArchitectureAssessmentSection,
    ArchitectureCoverageArea,
    ArchitectureCoverageSummary,
    ArchitectureExecutionSummary,
    ArchitectureFindingReference,
    ArchitectureLimitation,
    ArchitectureTraceabilityEdge,
    ArchitectureTraceabilityIndex,
)
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ConsolidatedRecommendation,
)
from codestrata.domain.findings import Finding
from codestrata.domain.rules.architecture.ids import PACK_ID, PACK_VERSION


def architecture_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    return tuple(
        sorted(
            (
                finding
                for finding in findings
                if finding.rule_id.startswith("architecture.")
            ),
            key=lambda item: (item.rule_id, item.id),
        )
    )


def _coverage_area_from_ratio(
    *,
    area_id: str,
    ratio: float | None,
    provenance: str,
) -> ArchitectureCoverageArea:
    if ratio is None:
        return ArchitectureCoverageArea(
            area_id=area_id,
            status=CoverageAreaStatus.UNKNOWN,
            provenance=provenance,
        )
    maturity = CoverageMaturity.HIGH
    status = CoverageAreaStatus.MEASURED
    limitations: tuple[str, ...] = ()
    if ratio < 0.25:
        maturity = CoverageMaturity.LOW
        status = CoverageAreaStatus.PARTIAL
        limitations = ("Low coverage reduces confidence in architecture meaning.",)
    elif ratio < 0.75:
        maturity = CoverageMaturity.MEDIUM
        status = CoverageAreaStatus.PARTIAL
        limitations = ("Partial coverage; interpret conclusions as provisional where noted.",)
    return ArchitectureCoverageArea(
        area_id=area_id,
        status=status,
        ratio=round(float(ratio), 4),
        maturity=maturity,
        limitations=limitations,
        provenance=provenance,
    )


def _default_limitations(
    *,
    classification_coverage: float | None,
    enterprise_context_used: bool,
    conclusions_enabled: bool,
    conclusion_failures: int,
    provider_failures: int,
) -> tuple[ArchitectureLimitation, ...]:
    items: list[ArchitectureLimitation] = [
        ArchitectureLimitation(
            limitation_id=build_limitation_id(
                category=ArchitectureLimitationCategory.STATIC_ANALYSIS_ONLY.value,
                summary="Static dependency analysis only",
            ),
            category=ArchitectureLimitationCategory.STATIC_ANALYSIS_ONLY,
            summary=(
                "Architecture assessment is based on static analysis of source "
                "dependencies and declared structure. Runtime behavior is not observed."
            ),
            affected_capability="architecture_assessment",
            importance="material",
            remediation_guidance=(
                "Validate critical findings with targeted design review or dynamic checks."
            ),
        ),
        ArchitectureLimitation(
            limitation_id=build_limitation_id(
                category=ArchitectureLimitationCategory.RUNTIME_BEHAVIOR_NOT_OBSERVED.value,
                summary="Runtime behavior not observed",
            ),
            category=ArchitectureLimitationCategory.RUNTIME_BEHAVIOR_NOT_OBSERVED,
            summary="No runtime traces, production telemetry, or load behavior were assessed.",
            affected_capability="architecture_assessment",
            importance="contextual",
        ),
        ArchitectureLimitation(
            limitation_id=build_limitation_id(
                category=ArchitectureLimitationCategory.POSITIVE_EVIDENCE_UNAVAILABLE.value,
                summary="Positive evidence unavailable",
            ),
            category=ArchitectureLimitationCategory.POSITIVE_EVIDENCE_UNAVAILABLE,
            summary=(
                "Architecture strengths remain empty until explicit positive evidence "
                "providers and conclusions are enabled."
            ),
            affected_capability="architecture_strengths",
            importance="informational",
        ),
    ]
    if not enterprise_context_used:
        items.append(
            ArchitectureLimitation(
                limitation_id=build_limitation_id(
                    category=ArchitectureLimitationCategory.ENTERPRISE_CONTEXT_UNAVAILABLE.value,
                    summary="Enterprise context unavailable",
                ),
                category=ArchitectureLimitationCategory.ENTERPRISE_CONTEXT_UNAVAILABLE,
                summary=(
                    "Business impact remains unknown because Engineering Knowledge Graph "
                    "context was not supplied."
                ),
                affected_capability="business_impact",
                importance="contextual",
            )
        )
    if classification_coverage is not None and classification_coverage < 0.75:
        items.append(
            ArchitectureLimitation(
                limitation_id=build_limitation_id(
                    category=ArchitectureLimitationCategory.PARTIAL_CLASSIFICATION.value,
                    summary="Partial layer classification",
                ),
                category=ArchitectureLimitationCategory.PARTIAL_CLASSIFICATION,
                summary=(
                    "Layer or boundary classification coverage is incomplete for some units."
                ),
                affected_capability="layer_classification",
                importance="contextual",
            )
        )
    if not conclusions_enabled:
        items.append(
            ArchitectureLimitation(
                limitation_id=build_limitation_id(
                    category=ArchitectureLimitationCategory.CONCLUSIONS_DISABLED.value,
                    summary="Architecture conclusions disabled",
                ),
                category=ArchitectureLimitationCategory.CONCLUSIONS_DISABLED,
                summary=(
                    "Conclusion enrichment was disabled; the section includes findings "
                    "and rule-level recommendations only."
                ),
                affected_capability="architecture_conclusions",
                importance="informational",
            )
        )
    if conclusion_failures > 0:
        items.append(
            ArchitectureLimitation(
                limitation_id=build_limitation_id(
                    category=ArchitectureLimitationCategory.CONCLUSION_POLICY_FAILURE.value,
                    summary="Conclusion policy failure",
                ),
                category=ArchitectureLimitationCategory.CONCLUSION_POLICY_FAILURE,
                summary=(
                    f"{conclusion_failures} conclusion policy execution failure(s) occurred; "
                    "available findings and successful conclusions are retained."
                ),
                affected_capability="architecture_conclusions",
                importance="contextual",
            )
        )
    if provider_failures > 0:
        items.append(
            ArchitectureLimitation(
                limitation_id=build_limitation_id(
                    category=ArchitectureLimitationCategory.PROVIDER_FAILURE.value,
                    summary="Evidence provider failure",
                ),
                category=ArchitectureLimitationCategory.PROVIDER_FAILURE,
                summary=(
                    f"{provider_failures} evidence provider failure(s) occurred during "
                    "architecture evidence collection."
                ),
                affected_capability="evidence_pipeline",
                importance="contextual",
            )
        )
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _build_finding_references(
    findings: Sequence[Finding],
    conclusions: Sequence[ArchitectureConclusion],
) -> tuple[ArchitectureFindingReference, ...]:
    conclusions_by_finding: dict[str, list[str]] = {}
    for conclusion in conclusions:
        for finding_id in conclusion.source_finding_ids:
            conclusions_by_finding.setdefault(finding_id, []).append(conclusion.conclusion_id)

    refs: list[ArchitectureFindingReference] = []
    for finding in findings:
        scope = scope_from_findings([finding])
        confidence = str(finding.metadata.get("confidence", "medium")).lower()
        remediation = finding.metadata.get("remediation")
        recommendation_ids: tuple[str, ...] = ()
        if isinstance(remediation, str) and remediation.strip():
            # Rule-level recommendation text is preserved on the finding; no separate ID.
            recommendation_ids = ()
        refs.append(
            ArchitectureFindingReference(
                finding_id=finding.id,
                rule_id=finding.rule_id,
                title=finding.title,
                affected_scope=scope,
                severity=finding.severity.value,
                confidence=confidence,
                status="visible",
                conclusion_ids=tuple(sorted(conclusions_by_finding.get(finding.id, []))),
                recommendation_ids=recommendation_ids,
                evidence_count=len(finding.evidence),
                suppression_state="unsuppressed",
                taxonomy_ids=(finding.rule_id,),
            )
        )
    return tuple(refs)


def _build_traceability(
    *,
    section_id: str,
    pack_id: str | None,
    findings: Sequence[Finding],
    conclusions: Sequence[ArchitectureConclusion],
    recommendation_group_ids: Sequence[str],
    recommendation_groups_source_findings: dict[str, tuple[str, ...]],
    recommendation_groups_source_recs: dict[str, tuple[str, ...]],
    coverage_area_ids: Sequence[str],
    limitation_ids: Sequence[str],
) -> ArchitectureTraceabilityIndex:
    edges: list[ArchitectureTraceabilityEdge] = []

    def add(relation: TraceabilityRelation, source: str, target: str) -> None:
        edges.append(
            ArchitectureTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=relation.value,
                    source_id=source,
                    target_id=target,
                ),
                relation=relation,
                source_id=source,
                target_id=target,
            )
        )

    if pack_id:
        add(TraceabilityRelation.SECTION_TO_PACK, section_id, pack_id)
    for finding in findings:
        add(TraceabilityRelation.SECTION_TO_FINDING, section_id, finding.id)
        for evidence in finding.evidence[:5]:
            add(
                TraceabilityRelation.FINDING_TO_EVIDENCE,
                finding.id,
                evidence.source_id,
            )
    for conclusion in conclusions:
        add(TraceabilityRelation.SECTION_TO_CONCLUSION, section_id, conclusion.conclusion_id)
        for finding_id in conclusion.source_finding_ids:
            add(
                TraceabilityRelation.CONCLUSION_TO_FINDING,
                conclusion.conclusion_id,
                finding_id,
            )
    for group_id in recommendation_group_ids:
        add(TraceabilityRelation.SECTION_TO_RECOMMENDATION_GROUP, section_id, group_id)
        for finding_id in recommendation_groups_source_findings.get(group_id, ()):
            add(
                TraceabilityRelation.RECOMMENDATION_GROUP_TO_FINDING,
                group_id,
                finding_id,
            )
        for rec_id in recommendation_groups_source_recs.get(group_id, ()):
            add(
                TraceabilityRelation.RECOMMENDATION_GROUP_TO_RECOMMENDATION,
                group_id,
                rec_id,
            )
    for area_id in coverage_area_ids:
        add(TraceabilityRelation.SECTION_TO_COVERAGE, section_id, area_id)
    for limitation_id in limitation_ids:
        add(TraceabilityRelation.SECTION_TO_LIMITATION, section_id, limitation_id)

    ordered = tuple(sorted(edges, key=lambda item: (item.relation.value, item.edge_id)))
    return ArchitectureTraceabilityIndex(edges=ordered)


class ArchitectureAssessmentAssembler:
    """Compose an ArchitectureAssessmentSection without re-running analysis."""

    def assemble(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding],
        conclusion_result: ArchitectureConclusionResult | None = None,
        pack_enabled: bool = False,
        conclusions_enabled: bool = False,
        include_findings: bool = True,
        include_conclusions: bool = True,
        include_recommendation_groups: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_execution_summary: bool = True,
        extraction_coverage: float | None = None,
        classification_coverage: float | None = None,
        graph_fingerprint: str = "",
        evidence_fingerprint: str = "",
        evidence_pipeline: str = "legacy_view_builder",
        configuration_payload: str = "",
        architecture_rules_planned: int = 7,
        rules_executed: int | None = None,
        providers_planned: int = 0,
        providers_executed: int = 0,
        provider_failures: int = 0,
        enterprise_context_used: bool = False,
        diagnostics: Sequence[str] = (),
        force_status: ArchitectureAssessmentStatus | None = None,
    ) -> ArchitectureAssessmentSection:
        arch_findings = architecture_findings(findings)
        conclusions: tuple[ArchitectureConclusion, ...] = ()
        recommendation_groups: tuple[ConsolidatedRecommendation, ...] = ()
        conclusion_failures = 0
        conclusion_policies_executed = 0
        conclusion_diagnostics: tuple[str, ...] = ()
        if conclusion_result is not None and conclusion_result.enabled:
            if include_conclusions:
                conclusions = conclusion_result.conclusions
            if include_recommendation_groups:
                recommendation_groups = conclusion_result.recommendation_groups
            conclusion_failures = conclusion_result.telemetry.failure_count
            conclusion_policies_executed = len(conclusion_result.telemetry.policy_records)
            conclusion_diagnostics = conclusion_result.diagnostics

        if force_status is not None:
            status = force_status
        elif not pack_enabled:
            status = ArchitectureAssessmentStatus.DISABLED
        elif (
            extraction_coverage is not None
            and extraction_coverage < 0.1
            and not arch_findings
        ):
            status = ArchitectureAssessmentStatus.INSUFFICIENT_EVIDENCE
        elif conclusion_failures > 0 or provider_failures > 0:
            status = ArchitectureAssessmentStatus.PARTIALLY_SUCCEEDED
        else:
            status = ArchitectureAssessmentStatus.SUCCEEDED

        finding_summaries = (
            _build_finding_references(arch_findings, conclusions)
            if include_findings
            else ()
        )
        finding_ids = tuple(item.finding_id for item in finding_summaries)
        conclusion_ids = tuple(item.conclusion_id for item in conclusions)
        recommendation_group_ids = tuple(
            item.recommendation_group_id for item in recommendation_groups
        )

        matched_rule_ids = {item.rule_id for item in arch_findings}
        executed = (
            rules_executed
            if rules_executed is not None
            else architecture_rules_planned
        )
        execution_summary = ArchitectureExecutionSummary(
            providers_planned=providers_planned,
            providers_executed=providers_executed,
            provider_failures=provider_failures,
            architecture_rules_planned=architecture_rules_planned,
            rules_executed=executed if pack_enabled else 0,
            rules_matched=len(matched_rule_ids),
            rules_not_matched=max(0, executed - len(matched_rule_ids)) if pack_enabled else 0,
            suppressed_finding_count=0,
            visible_finding_count=len(arch_findings),
            conclusion_policies_executed=conclusion_policies_executed
            if conclusions_enabled
            else 0,
            conclusion_count=len(conclusions),
            recommendation_group_count=len(recommendation_groups),
        )
        if not include_execution_summary:
            execution_summary = ArchitectureExecutionSummary()

        coverage_areas: list[ArchitectureCoverageArea] = []
        if include_coverage:
            coverage_areas.extend(
                [
                    _coverage_area_from_ratio(
                        area_id="extraction_coverage",
                        ratio=extraction_coverage,
                        provenance="architecture_view",
                    ),
                    _coverage_area_from_ratio(
                        area_id="classification_coverage",
                        ratio=classification_coverage,
                        provenance="architecture_view",
                    ),
                    ArchitectureCoverageArea(
                        area_id="enterprise_context_coverage",
                        status=(
                            CoverageAreaStatus.MEASURED
                            if enterprise_context_used
                            else CoverageAreaStatus.NOT_APPLICABLE
                        ),
                        ratio=1.0 if enterprise_context_used else None,
                        maturity=(
                            CoverageMaturity.HIGH
                            if enterprise_context_used
                            else CoverageMaturity.UNKNOWN
                        ),
                        limitations=(
                            ()
                            if enterprise_context_used
                            else ("Enterprise context was not supplied.",)
                        ),
                        provenance="assessment_assembly",
                    ),
                    ArchitectureCoverageArea(
                        area_id="framework_coverage",
                        status=CoverageAreaStatus.UNSUPPORTED,
                        provenance="architecture_assessment",
                        limitations=("Framework coverage is not yet measured as a ratio.",),
                    ),
                    ArchitectureCoverageArea(
                        area_id="build_metadata_coverage",
                        status=CoverageAreaStatus.UNSUPPORTED,
                        provenance="architecture_assessment",
                        limitations=("Build-metadata coverage is not measured here.",),
                    ),
                ]
            )
        coverage = ArchitectureCoverageSummary(areas=tuple(coverage_areas))

        limitations = (
            _default_limitations(
                classification_coverage=classification_coverage,
                enterprise_context_used=enterprise_context_used,
                conclusions_enabled=conclusions_enabled,
                conclusion_failures=conclusion_failures,
                provider_failures=provider_failures,
            )
            if include_limitations
            else ()
        )

        group_findings: dict[str, tuple[str, ...]] = {
            group.recommendation_group_id: group.source_finding_ids
            for group in recommendation_groups
        }
        group_recs: dict[str, tuple[str, ...]] = {
            group.recommendation_group_id: group.source_recommendation_ids
            for group in recommendation_groups
        }
        traceability = (
            _build_traceability(
                section_id=SECTION_ID,
                pack_id=PACK_ID if pack_enabled else None,
                findings=arch_findings if include_findings else (),
                conclusions=conclusions,
                recommendation_group_ids=recommendation_group_ids,
                recommendation_groups_source_findings=group_findings,
                recommendation_groups_source_recs=group_recs,
                coverage_area_ids=[area.area_id for area in coverage_areas],
                limitation_ids=[item.limitation_id for item in limitations],
            )
            if include_traceability
            else ArchitectureTraceabilityIndex()
        )

        config_fp = build_configuration_fingerprint(
            configuration_payload
            or (
                f"pack={pack_enabled}|conclusions={conclusions_enabled}|"
                f"findings={include_findings}|conclusions_inc={include_conclusions}"
            )
        )
        merged_diagnostics = tuple(
            sorted({*diagnostics, *conclusion_diagnostics})
        )

        return ArchitectureAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=status,
            repository_id=repository_id,
            architecture_pack_id=PACK_ID if pack_enabled else None,
            architecture_pack_version=PACK_VERSION if pack_enabled else None,
            evidence_pipeline=evidence_pipeline,
            graph_fingerprint=graph_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            configuration_fingerprint=config_fp,
            execution_summary=execution_summary,
            coverage=coverage,
            finding_ids=finding_ids,
            finding_summaries=finding_summaries,
            conclusion_ids=conclusion_ids,
            conclusions=conclusions,
            recommendation_group_ids=recommendation_group_ids,
            recommendation_groups=recommendation_groups,
            strengths=(),  # Positive evidence not yet available.
            limitations=limitations,
            diagnostics=merged_diagnostics,
            traceability=traceability,
            enterprise_context_used=enterprise_context_used,
            business_impact="unknown",
            metadata={
                "schema": SECTION_SCHEMA_VERSION,
                "strengths_policy": "empty_until_positive_evidence",
            },
        )

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "architecture_pack_or_section_disabled",
    ) -> ArchitectureAssessmentSection:
        return self.assemble(
            repository_id=repository_id,
            findings=(),
            pack_enabled=False,
            conclusions_enabled=False,
            force_status=ArchitectureAssessmentStatus.DISABLED,
            diagnostics=(reason,),
        )
