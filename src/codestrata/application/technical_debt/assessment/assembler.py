"""Assemble TechnicalDebtAssessmentSection (Phase 4.3.4 assessment vertical)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.technical_debt.assessment.inventory import (
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    material_production_parse_failures,
)
from codestrata.application.technical_debt.synthesis.service import synthesize_technical_debt
from codestrata.domain.evidence.language.complexity.models import AggregatedComplexityEvidence
from codestrata.domain.findings import Finding
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtCoverageAreaStatus,
    TechnicalDebtCoverageMaturity,
    TechnicalDebtLimitationCategory,
    TechnicalDebtSourceRole,
    TechnicalDebtTraceabilityRelation,
)
from codestrata.domain.technical_debt.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_configuration_fingerprint,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.technical_debt.assessment.models import (
    TechnicalDebtAssessmentSection,
    TechnicalDebtCoverageArea,
    TechnicalDebtCoverageSummary,
    TechnicalDebtExecutionSummary,
    TechnicalDebtFindingInventory,
    TechnicalDebtHotspotInventory,
    TechnicalDebtLimitation,
    TechnicalDebtTraceabilityEdge,
    TechnicalDebtTraceabilityIndex,
)
from codestrata.domain.technical_debt.ids import PACK_ID, PACK_VERSION, RULE_ID_PREFIX


def technical_debt_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """Filter shared findings that belong to the technical-debt rule namespace."""

    return tuple(
        sorted(
            (
                finding
                for finding in findings
                if finding.rule_id.startswith(RULE_ID_PREFIX)
            ),
            key=lambda item: (item.rule_id, item.id),
        )
    )


def _assessment_limitations(
    *,
    pack_enabled: bool,
    complexity_evidence_enabled: bool,
) -> tuple[TechnicalDebtLimitation, ...]:
    items: list[TechnicalDebtLimitation] = [
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.FINANCIAL_COST_NOT_ASSESSED.value,
                summary="Financial cost not assessed",
            ),
            category=TechnicalDebtLimitationCategory.FINANCIAL_COST_NOT_ASSESSED,
            summary=(
                "No financial cost, interest-rate, or dollar estimate is computed for "
                "technical debt."
            ),
            affected_capability="technical_debt_cost",
            importance="material",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.EFFORT_NOT_ASSESSED.value,
                summary="Engineering effort not assessed",
            ),
            category=TechnicalDebtLimitationCategory.EFFORT_NOT_ASSESSED,
            summary=(
                "No engineering-hours, staffing, or schedule estimate is produced by "
                "this assessment section."
            ),
            affected_capability="technical_debt_effort",
            importance="material",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.BUSINESS_IMPACT_UNKNOWN.value,
                summary="Business impact unknown",
            ),
            category=TechnicalDebtLimitationCategory.BUSINESS_IMPACT_UNKNOWN,
            summary=(
                "Business impact remains unknown for repository-only technical debt "
                "assessment without explicit enterprise context."
            ),
            affected_capability="business_impact",
            importance="contextual",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.STATIC_ANALYSIS_ONLY.value,
                summary="Static analysis only",
            ),
            category=TechnicalDebtLimitationCategory.STATIC_ANALYSIS_ONLY,
            summary=(
                "Technical debt findings are based on static repository evidence. "
                "Runtime behavior and productivity loss are not observed."
            ),
            affected_capability="technical_debt_assessment",
            importance="contextual",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.OTHER.value,
                summary="JavaScript TypeScript complexity unsupported",
            ),
            category=TechnicalDebtLimitationCategory.OTHER,
            summary=(
                "JavaScript and TypeScript complexity metrics are unsupported in "
                "Phase 4.3; only Python and Java collectors are available."
            ),
            affected_capability="complexity_evidence",
            importance="contextual",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.OTHER.value,
                summary="Cognitive complexity unsupported",
            ),
            category=TechnicalDebtLimitationCategory.OTHER,
            summary=(
                "Cognitive complexity is not measured. Branch-point counts are "
                "structural keyword/operator counts, not certified cyclomatic products."
            ),
            affected_capability="complexity_evidence",
            importance="informational",
        ),
        TechnicalDebtLimitation(
            limitation_id=build_limitation_id(
                category=TechnicalDebtLimitationCategory.WORKSPACE_CONTENT_EXCLUDED.value,
                summary="Workspace content excluded",
            ),
            category=TechnicalDebtLimitationCategory.WORKSPACE_CONTENT_EXCLUDED,
            summary=(
                "Paths under .codestrata/ and other shared ignore markers are excluded from "
                "complexity measurement."
            ),
            affected_capability="complexity_evidence",
            importance="informational",
        ),
    ]
    if not pack_enabled:
        items.append(
            TechnicalDebtLimitation(
                limitation_id=build_limitation_id(
                    category=TechnicalDebtLimitationCategory.OTHER.value,
                    summary="Technical debt pack disabled",
                ),
                category=TechnicalDebtLimitationCategory.OTHER,
                summary="The technical debt rule pack feature gate is disabled.",
                affected_capability="technical_debt_pack",
                importance="informational",
            )
        )
    if pack_enabled and not complexity_evidence_enabled:
        items.append(
            TechnicalDebtLimitation(
                limitation_id=build_limitation_id(
                    category=TechnicalDebtLimitationCategory.EVIDENCE_PROVIDERS_UNAVAILABLE.value,
                    summary="Complexity evidence collection disabled",
                ),
                category=TechnicalDebtLimitationCategory.EVIDENCE_PROVIDERS_UNAVAILABLE,
                summary=(
                    "Complexity evidence collection is disabled "
                    "([evidence.complexity] enabled = false)."
                ),
                affected_capability="complexity_evidence",
                importance="material",
            )
        )
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _coverage_from_evidence(
    evidence: AggregatedComplexityEvidence | None,
    *,
    pack_enabled: bool,
    complexity_evidence_enabled: bool,
    files_considered: int,
    files_analyzed: int,
    files_excluded: int,
    files_failed: int,
) -> TechnicalDebtCoverageSummary:
    if not pack_enabled:
        debt_status = TechnicalDebtCoverageAreaStatus.UNSUPPORTED
        debt_maturity = TechnicalDebtCoverageMaturity.UNKNOWN
        debt_limits: tuple[str, ...] = ("Technical debt pack is disabled.",)
    else:
        debt_status = TechnicalDebtCoverageAreaStatus.MEASURED
        debt_maturity = TechnicalDebtCoverageMaturity.MEDIUM
        debt_limits = ("Complexity SharedRules evaluated against collected evidence.",)

    if not complexity_evidence_enabled:
        complexity_status = TechnicalDebtCoverageAreaStatus.UNSUPPORTED
        complexity_maturity = TechnicalDebtCoverageMaturity.UNKNOWN
        complexity_limits: tuple[str, ...] = ("Complexity evidence collection is disabled.",)
        numerator = None
        denominator = None
        ratio = None
    elif evidence is None or files_considered == 0:
        complexity_status = TechnicalDebtCoverageAreaStatus.PARTIAL
        complexity_maturity = TechnicalDebtCoverageMaturity.LOW
        complexity_limits = ("No eligible Python/Java source units were measured.",)
        numerator = 0
        denominator = 0
        ratio = None
    else:
        complexity_status = (
            TechnicalDebtCoverageAreaStatus.MEASURED
            if files_failed == 0
            else TechnicalDebtCoverageAreaStatus.PARTIAL
        )
        complexity_maturity = TechnicalDebtCoverageMaturity.MEDIUM
        complexity_limits = (
            f"files_excluded={files_excluded}",
            f"files_failed={files_failed}",
        )
        numerator = files_analyzed
        denominator = files_considered
        ratio = (
            round(files_analyzed / files_considered, 4) if files_considered > 0 else None
        )

    areas = (
        TechnicalDebtCoverageArea(
            area_id="debt_rule_coverage",
            status=debt_status,
            maturity=debt_maturity,
            limitations=debt_limits,
            provenance="technical_debt_assessment",
        ),
        TechnicalDebtCoverageArea(
            area_id="complexity_coverage",
            status=complexity_status,
            numerator=numerator,
            denominator=denominator,
            ratio=ratio,
            maturity=complexity_maturity,
            limitations=complexity_limits,
            provenance="language.complexity",
        ),
        TechnicalDebtCoverageArea(
            area_id="duplication_coverage",
            status=TechnicalDebtCoverageAreaStatus.UNSUPPORTED,
            maturity=TechnicalDebtCoverageMaturity.UNKNOWN,
            limitations=("Duplication detection is not implemented.",),
            provenance="technical_debt_assessment",
        ),
        TechnicalDebtCoverageArea(
            area_id="dependency_support_coverage",
            status=TechnicalDebtCoverageAreaStatus.UNSUPPORTED,
            maturity=TechnicalDebtCoverageMaturity.UNKNOWN,
            limitations=("Dependency support-window analysis is not implemented.",),
            provenance="technical_debt_assessment",
        ),
        TechnicalDebtCoverageArea(
            area_id="enterprise_context_coverage",
            status=TechnicalDebtCoverageAreaStatus.NOT_APPLICABLE,
            maturity=TechnicalDebtCoverageMaturity.UNKNOWN,
            limitations=("Enterprise context was not supplied for this assessment.",),
            provenance="technical_debt_assessment",
        ),
    )
    return TechnicalDebtCoverageSummary(
        areas=tuple(sorted(areas, key=lambda item: item.area_id))
    )


    return TechnicalDebtCoverageSummary(
        areas=tuple(sorted(areas, key=lambda item: item.area_id))
    )


class TechnicalDebtAssessmentAssembler:
    """Build technical-debt assessment sections for disabled, empty, and live runs."""

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "technical_debt_pack_disabled",
    ) -> TechnicalDebtAssessmentSection:
        limitations = _assessment_limitations(
            pack_enabled=False,
            complexity_evidence_enabled=False,
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=False,
            section_enabled=True,
        )
        return TechnicalDebtAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=TechnicalDebtAssessmentStatus.DISABLED,
            repository_id=repository_id,
            technical_debt_pack_id=PACK_ID,
            technical_debt_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=TechnicalDebtExecutionSummary(),
            coverage=_coverage_from_evidence(
                None,
                pack_enabled=False,
                complexity_evidence_enabled=False,
                files_considered=0,
                files_analyzed=0,
                files_excluded=0,
                files_failed=0,
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(
                pack_id=PACK_ID,
                limitations=limitations,
                finding_ids=(),
                hotspot_ids=(),
            ),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={
                "assessment_milestone": "4.3.4A",
                "primary_inventory_role": TechnicalDebtSourceRole.PRODUCTION.value,
            },
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_debt_findings",
    ) -> TechnicalDebtAssessmentSection:
        """Succeeded empty section when pack is requested but no findings exist."""

        limitations = _assessment_limitations(
            pack_enabled=pack_enabled,
            complexity_evidence_enabled=True,
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=pack_enabled,
            section_enabled=True,
        )
        status = (
            TechnicalDebtAssessmentStatus.SUCCEEDED
            if pack_enabled
            else TechnicalDebtAssessmentStatus.DISABLED
        )
        return TechnicalDebtAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=status,
            repository_id=repository_id,
            technical_debt_pack_id=PACK_ID,
            technical_debt_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=TechnicalDebtExecutionSummary(
                debt_rules_planned=0,
                rules_executed=0,
                visible_finding_count=0,
            ),
            coverage=_coverage_from_evidence(
                None,
                pack_enabled=pack_enabled,
                complexity_evidence_enabled=True,
                files_considered=0,
                files_analyzed=0,
                files_excluded=0,
                files_failed=0,
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(
                pack_id=PACK_ID,
                limitations=limitations,
                finding_ids=(),
                hotspot_ids=(),
            ),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={
                "assessment_milestone": "4.3.4A",
                "primary_inventory_role": TechnicalDebtSourceRole.PRODUCTION.value,
            },
        )

    def assemble(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding],
        pack_enabled: bool,
        complexity_evidence_enabled: bool,
        include_findings: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_execution_summary: bool = True,
        include_synthesis: bool = True,
        complexity_evidence: AggregatedComplexityEvidence | None = None,
        evidence_pipeline: str = "language.complexity",
        evidence_fingerprint: str = "",
        configuration_payload: str = "",
        debt_rules_planned: int = 5,
        rules_executed: int = 0,
        rules_matched: int = 0,
        rules_not_matched: int = 0,
        rules_not_applicable: int = 0,
        files_considered: int = 0,
        files_analyzed: int = 0,
        files_excluded: int = 0,
        files_failed: int = 0,
        diagnostics: Sequence[str] = (),
    ) -> TechnicalDebtAssessmentSection:
        debt_findings = technical_debt_findings(findings)
        all_refs = build_finding_references(debt_findings) if include_findings else ()
        finding_inventory = (
            build_finding_inventory(all_refs)
            if include_findings
            else TechnicalDebtFindingInventory()
        )
        hotspot_inventory = (
            build_hotspot_inventory(all_refs)
            if include_findings
            else TechnicalDebtHotspotInventory()
        )
        primary_refs = tuple(
            item
            for item in all_refs
            if item.source_role is TechnicalDebtSourceRole.PRODUCTION
        )
        primary_ids = tuple(item.finding_id for item in primary_refs)
        all_ids = tuple(item.finding_id for item in all_refs)

        production_parse_failures = material_production_parse_failures(diagnostics)
        # File-level parse failures on test/fixture paths and unsupported languages
        # or unavailable optional metrics are not provider execution failures.
        provider_failures = production_parse_failures

        if not pack_enabled:
            status = TechnicalDebtAssessmentStatus.DISABLED
        elif (
            complexity_evidence_enabled
            and files_considered == 0
            and not debt_findings
        ):
            status = TechnicalDebtAssessmentStatus.INSUFFICIENT_EVIDENCE
        elif provider_failures > 0:
            status = TechnicalDebtAssessmentStatus.PARTIALLY_SUCCEEDED
        else:
            status = TechnicalDebtAssessmentStatus.SUCCEEDED

        diag = {str(item) for item in diagnostics if str(item).strip()}
        if files_failed > 0 and production_parse_failures == 0:
            diag.add(
                "non_material_parse_failures_do_not_degrade_status:"
                f"{files_failed}"
            )
        if files_failed > production_parse_failures:
            diag.add(
                "parse_failures_total_vs_production:"
                f"{files_failed}:{production_parse_failures}"
            )

        limitations = (
            _assessment_limitations(
                pack_enabled=pack_enabled,
                complexity_evidence_enabled=complexity_evidence_enabled,
            )
            if include_limitations
            else ()
        )
        coverage = (
            _coverage_from_evidence(
                complexity_evidence,
                pack_enabled=pack_enabled,
                complexity_evidence_enabled=complexity_evidence_enabled,
                files_considered=files_considered,
                files_analyzed=files_analyzed,
                files_excluded=files_excluded,
                files_failed=files_failed,
            )
            if include_coverage
            else TechnicalDebtCoverageSummary()
        )
        synthesis = synthesize_technical_debt(
            repository_id=repository_id,
            pack_enabled=pack_enabled,
            section_status=status,
            finding_summaries=all_refs,
            hotspot_inventory=hotspot_inventory,
            coverage=coverage,
            include_synthesis=include_synthesis,
        )
        execution_summary = (
            TechnicalDebtExecutionSummary(
                providers_planned=1 if complexity_evidence_enabled else 0,
                providers_executed=1 if complexity_evidence is not None else 0,
                provider_failures=provider_failures,
                files_parse_failed=files_failed,
                production_parse_failures=production_parse_failures,
                debt_rules_planned=debt_rules_planned,
                rules_executed=rules_executed,
                rules_matched=rules_matched,
                rules_not_matched=rules_not_matched,
                rules_not_applicable=rules_not_applicable,
                visible_finding_count=len(primary_ids),
                production_finding_count=finding_inventory.production.finding_count,
                test_finding_count=finding_inventory.test.finding_count,
                unknown_finding_count=finding_inventory.unknown.finding_count,
                total_finding_count=finding_inventory.total_finding_count,
                theme_count=len(synthesis.theme_ids),
                conclusion_count=len(synthesis.conclusion_ids),
                recommendation_count=len(synthesis.recommendation_ids),
            )
            if include_execution_summary
            else TechnicalDebtExecutionSummary()
        )
        fingerprint = build_configuration_fingerprint(
            configuration_payload
            or (
                f"repository_id={repository_id}|pack_enabled={pack_enabled}|"
                f"complexity_enabled={complexity_evidence_enabled}"
            )
        )
        hotspot_ids = tuple(item.hotspot_id for item in hotspot_inventory.production)
        return TechnicalDebtAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=status,
            repository_id=repository_id,
            technical_debt_pack_id=PACK_ID,
            technical_debt_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline,
            evidence_fingerprint=evidence_fingerprint,
            configuration_fingerprint=fingerprint,
            execution_summary=execution_summary,
            coverage=coverage,
            finding_ids=primary_ids,
            finding_summaries=primary_refs,
            all_finding_ids=all_ids,
            all_finding_summaries=all_refs,
            finding_inventory=finding_inventory,
            hotspot_inventory=hotspot_inventory,
            synthesis=synthesis,
            themes=synthesis.themes,
            theme_ids=synthesis.theme_ids,
            concentration_facts=synthesis.concentration_facts,
            conclusions=synthesis.conclusions,
            conclusion_ids=synthesis.conclusion_ids,
            recommendations=synthesis.recommendations,
            recommendation_ids=synthesis.recommendation_ids,
            limitations=limitations,
            diagnostics=tuple(sorted(diag | set(synthesis.diagnostics))),
            traceability=(
                _section_traceability(
                    pack_id=PACK_ID,
                    limitations=limitations,
                    finding_ids=primary_ids,
                    hotspot_ids=hotspot_ids,
                    theme_ids=synthesis.theme_ids,
                    conclusion_ids=synthesis.conclusion_ids,
                    recommendation_ids=synthesis.recommendation_ids,
                    conclusions=synthesis.conclusions,
                    recommendations=synthesis.recommendations,
                )
                if include_traceability
                else TechnicalDebtTraceabilityIndex()
            ),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={
                "assessment_milestone": "4.3.5",
                "severity_high_basis": "value_gt_two_times_threshold",
                "primary_inventory_role": TechnicalDebtSourceRole.PRODUCTION.value,
                "test_findings_exposed": "finding_inventory.test",
                "hotspot_ordering": "highest_severity_then_finding_count_then_path_unit",
                "synthesis_version": synthesis.synthesis_version,
                "package_concentration_threshold": "0.15",
                "hotspot_top10_concentration_threshold": "0.40",
            },
        )


def _section_traceability(
    *,
    pack_id: str,
    limitations: Sequence[TechnicalDebtLimitation],
    finding_ids: Sequence[str],
    hotspot_ids: Sequence[str] = (),
    theme_ids: Sequence[str] = (),
    conclusion_ids: Sequence[str] = (),
    recommendation_ids: Sequence[str] = (),
    conclusions: Sequence[object] = (),
    recommendations: Sequence[object] = (),
) -> TechnicalDebtTraceabilityIndex:
    edges: list[TechnicalDebtTraceabilityEdge] = [
        TechnicalDebtTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=TechnicalDebtTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for limitation in limitations:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=limitation.limitation_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=limitation.limitation_id,
            )
        )
    for finding_id in finding_ids:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=finding_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=finding_id,
            )
        )
    for hotspot_id in hotspot_ids:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_HOTSPOT.value,
                    source_id=SECTION_ID,
                    target_id=hotspot_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_HOTSPOT,
                source_id=SECTION_ID,
                target_id=hotspot_id,
            )
        )
    for theme_id in theme_ids:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_THEME.value,
                    source_id=SECTION_ID,
                    target_id=theme_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_THEME,
                source_id=SECTION_ID,
                target_id=theme_id,
            )
        )
    for conclusion_id in conclusion_ids:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_CONCLUSION.value,
                    source_id=SECTION_ID,
                    target_id=conclusion_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_CONCLUSION,
                source_id=SECTION_ID,
                target_id=conclusion_id,
            )
        )
    for recommendation_id in recommendation_ids:
        edges.append(
            TechnicalDebtTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TechnicalDebtTraceabilityRelation.SECTION_TO_RECOMMENDATION.value,
                    source_id=SECTION_ID,
                    target_id=recommendation_id,
                ),
                relation=TechnicalDebtTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                source_id=SECTION_ID,
                target_id=recommendation_id,
            )
        )
    for conclusion in conclusions:
        conclusion_id = getattr(conclusion, "conclusion_id", "")
        for finding_id in getattr(conclusion, "finding_ids", ())[:32]:
            edges.append(
                TechnicalDebtTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_FINDING.value,
                        source_id=conclusion_id,
                        target_id=finding_id,
                    ),
                    relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_FINDING,
                    source_id=conclusion_id,
                    target_id=finding_id,
                )
            )
        for theme_id in getattr(conclusion, "theme_ids", ()):
            edges.append(
                TechnicalDebtTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_THEME.value,
                        source_id=conclusion_id,
                        target_id=theme_id,
                    ),
                    relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_THEME,
                    source_id=conclusion_id,
                    target_id=theme_id,
                )
            )
        for hotspot_id in getattr(conclusion, "hotspot_ids", ())[:16]:
            edges.append(
                TechnicalDebtTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_HOTSPOT.value,
                        source_id=conclusion_id,
                        target_id=hotspot_id,
                    ),
                    relation=TechnicalDebtTraceabilityRelation.CONCLUSION_TO_HOTSPOT,
                    source_id=conclusion_id,
                    target_id=hotspot_id,
                )
            )
    for recommendation in recommendations:
        recommendation_id = getattr(recommendation, "recommendation_id", "")
        for conclusion_id in getattr(recommendation, "conclusion_ids", ()):
            edges.append(
                TechnicalDebtTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=TechnicalDebtTraceabilityRelation.RECOMMENDATION_TO_CONCLUSION.value,
                        source_id=recommendation_id,
                        target_id=conclusion_id,
                    ),
                    relation=TechnicalDebtTraceabilityRelation.RECOMMENDATION_TO_CONCLUSION,
                    source_id=recommendation_id,
                    target_id=conclusion_id,
                )
            )
    return TechnicalDebtTraceabilityIndex(
        edges=tuple(sorted(edges, key=lambda item: item.edge_id))
    )
