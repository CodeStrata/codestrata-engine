"""Performance assessment assembler (Phase 4.9.5).

Projects Performance Assessment sections with deterministic inventories and
synthesis over existing Performance Hygiene Findings and rule-execution facts.
No report projection.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.performance.assessment.inventory import (
    PerformanceRuleExecutionFact,
    build_confidence_inventory,
    build_finding_inventory,
    build_performance_family_inventory,
    build_rule_inventory,
    build_severity_inventory,
    coerce_execution_facts,
    findings_by_rule_counts,
)
from codestrata.application.performance.synthesis.service import synthesize_performance
from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.enums import (
    PerformanceAssessmentStatus,
    PerformanceCoverageAreaStatus,
    PerformanceCoverageMaturity,
    PerformanceLimitationCategory,
    PerformanceTraceabilityRelation,
)
from codestrata.domain.performance.assessment.identifiers import (
    MAX_TRACEABILITY_ENTRIES,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_configuration_fingerprint,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.performance.assessment.models import (
    PerformanceAssessmentSection,
    PerformanceConfidenceInventory,
    PerformanceCoverageArea,
    PerformanceCoverageSummary,
    PerformanceExecutionSummary,
    PerformanceFamilyInventory,
    PerformanceFindingInventory,
    PerformanceLimitation,
    PerformanceRuleInventory,
    PerformanceSeverityInventory,
    PerformanceTraceabilityEdge,
    PerformanceTraceabilityIndex,
)
from codestrata.domain.performance.ids import HYGIENE_RULE_IDS, PACK_ID, PACK_VERSION
from codestrata.domain.performance.synthesis.enums import PerformanceSynthesisStatus
from codestrata.domain.performance.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.performance.synthesis.models import PerformanceSynthesisResult

_MILESTONE = "4.9.5"
_ZERO_FINDINGS_SUMMARY = (
    "Performance Hygiene pack produced zero findings. This does not establish "
    "that the repository is performant, scalable, or free of latency risk."
)


def _limitation(
    *,
    category: PerformanceLimitationCategory,
    summary: str,
    affected_capability: str,
    importance: str = "contextual",
) -> PerformanceLimitation:
    return PerformanceLimitation(
        limitation_id=build_limitation_id(category=category.value, summary=summary),
        category=category,
        summary=summary,
        affected_capability=affected_capability,
        importance=importance,
    )


def _foundation_limitations(*, pack_enabled: bool) -> tuple[PerformanceLimitation, ...]:
    items = [
        _limitation(
            category=PerformanceLimitationCategory.FOUNDATION_ONLY,
            summary=(
                "Performance Intelligence inventory and deterministic "
                "synthesis; report presentation and performance scoring remain "
                "out of scope."
            ),
            affected_capability="performance_assessment",
            importance="critical",
        ),
        _limitation(
            category=PerformanceLimitationCategory.NO_PERFORMANCE_CONCLUSION,
            summary=(
                "No conclusion about performance, scalability, latency, or throughput can be drawn."
            ),
            affected_capability="performance",
            importance="critical",
        ),
        _limitation(
            category=PerformanceLimitationCategory.RULES_NOT_IMPLEMENTED,
            summary=(
                "Performance rule pack is disabled; no performance rules ran."
                if not pack_enabled
                else (
                    "Performance Hygiene inventories summarize existing Findings "
                    "only; they do not re-run rules or collect evidence."
                )
            ),
            affected_capability="performance_rules",
            importance="critical",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _hygiene_limitations(*, pack_enabled: bool) -> tuple[PerformanceLimitation, ...]:
    items = [
        _limitation(
            category=PerformanceLimitationCategory.NO_PERFORMANCE_CONCLUSION,
            summary=(
                "Performance Hygiene findings are repository-observable "
                "signals only. Zero findings does not mean the repository is "
                "performant, scalable, or free of latency risk."
            ),
            affected_capability="performance",
            importance="critical",
        ),
        _limitation(
            category=PerformanceLimitationCategory.OTHER,
            summary=(
                "Performance Hygiene rules consume "
                "AggregatedRepositoryPerformanceEvidence only; inventory and "
                "synthesis never re-read repository files, execute AI/LLM "
                "calls, or produce performance scores. Report presentation is "
                "not implemented."
                if pack_enabled
                else "Performance rule pack is disabled; no performance rules ran."
            ),
            affected_capability="performance_rules",
            importance="critical",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _coverage(
    *,
    pack_enabled: bool,
    findings_count: int = 0,
    rules_executed: int = 0,
    inventory_complete: bool = False,
) -> PerformanceCoverageSummary:
    planned = len(HYGIENE_RULE_IDS) if pack_enabled else 0
    areas = [
        PerformanceCoverageArea(
            area_id="performance_capability_requested",
            status=PerformanceCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=(
                PerformanceCoverageMaturity.MEDIUM
                if pack_enabled
                else PerformanceCoverageMaturity.LOW
            ),
            limitations=("hygiene_rules_only",) if pack_enabled else ("foundation_only",),
        ),
        PerformanceCoverageArea(
            area_id="performance_rules_enabled",
            status=(
                PerformanceCoverageAreaStatus.MEASURED
                if pack_enabled
                else PerformanceCoverageAreaStatus.NOT_APPLICABLE
            ),
            numerator=rules_executed if pack_enabled else 0,
            denominator=planned,
            ratio=((rules_executed / planned) if pack_enabled and planned else None),
            maturity=(
                PerformanceCoverageMaturity.MEDIUM
                if pack_enabled
                else PerformanceCoverageMaturity.LOW
            ),
            limitations=() if pack_enabled else ("pack_disabled",),
        ),
        PerformanceCoverageArea(
            area_id="performance_evidence_availability",
            status=PerformanceCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=(
                PerformanceCoverageMaturity.MEDIUM
                if pack_enabled
                else PerformanceCoverageMaturity.LOW
            ),
            limitations=("findings_and_execution_facts_only",),
        ),
        PerformanceCoverageArea(
            area_id="performance_findings_evaluated",
            status=PerformanceCoverageAreaStatus.MEASURED,
            numerator=findings_count,
            denominator=findings_count,
            ratio=1.0 if findings_count else None,
            maturity=(
                PerformanceCoverageMaturity.MEDIUM
                if pack_enabled
                else PerformanceCoverageMaturity.LOW
            ),
            limitations=("hygiene_findings_only",) if pack_enabled else ("analytically_empty",),
        ),
        PerformanceCoverageArea(
            area_id="performance_inventory_complete",
            status=(
                PerformanceCoverageAreaStatus.MEASURED
                if inventory_complete
                else PerformanceCoverageAreaStatus.UNSUPPORTED
            ),
            numerator=1 if inventory_complete else 0,
            denominator=1,
            ratio=1.0 if inventory_complete else 0.0,
            maturity=(
                PerformanceCoverageMaturity.MEDIUM
                if inventory_complete
                else PerformanceCoverageMaturity.LOW
            ),
            limitations=(
                ("inventory_and_synthesis",) if inventory_complete else ("foundation_only",)
            ),
        ),
    ]
    return PerformanceCoverageSummary(areas=tuple(sorted(areas, key=lambda item: item.area_id)))


def _lifecycle_traceability(
    *,
    pack_id: str,
    limitations: tuple[PerformanceLimitation, ...],
    finding_ids: tuple[str, ...] = (),
    theme_ids: tuple[str, ...] = (),
    conclusion_ids: tuple[str, ...] = (),
    recommendation_ids: tuple[str, ...] = (),
) -> PerformanceTraceabilityIndex:
    edges: list[PerformanceTraceabilityEdge] = [
        PerformanceTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=PerformanceTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=PerformanceTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for finding_id in finding_ids:
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=finding_id,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=finding_id,
            )
        )
    for theme_id in theme_ids:
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_THEME.value,
                    source_id=SECTION_ID,
                    target_id=theme_id,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_THEME,
                source_id=SECTION_ID,
                target_id=theme_id,
            )
        )
    for conclusion_id in conclusion_ids:
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_CONCLUSION.value,
                    source_id=SECTION_ID,
                    target_id=conclusion_id,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_CONCLUSION,
                source_id=SECTION_ID,
                target_id=conclusion_id,
            )
        )
    for recommendation_id in recommendation_ids:
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_RECOMMENDATION.value,
                    source_id=SECTION_ID,
                    target_id=recommendation_id,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                source_id=SECTION_ID,
                target_id=recommendation_id,
            )
        )
    for item in limitations:
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=item.limitation_id,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=item.limitation_id,
            )
        )
    for area in (
        "performance_capability_requested",
        "performance_rules_enabled",
        "performance_evidence_availability",
        "performance_findings_evaluated",
        "performance_inventory_complete",
    ):
        edges.append(
            PerformanceTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=PerformanceTraceabilityRelation.SECTION_TO_COVERAGE.value,
                    source_id=SECTION_ID,
                    target_id=area,
                ),
                relation=PerformanceTraceabilityRelation.SECTION_TO_COVERAGE,
                source_id=SECTION_ID,
                target_id=area,
            )
        )
    ordered = tuple(sorted(edges, key=lambda item: item.edge_id))
    return PerformanceTraceabilityIndex(edges=ordered[:MAX_TRACEABILITY_ENTRIES])


def _empty_inventories(
    *,
    pack_enabled: bool,
) -> tuple[
    PerformanceFindingInventory,
    PerformanceRuleInventory,
    PerformanceSeverityInventory,
    PerformanceConfidenceInventory,
    PerformanceFamilyInventory,
]:
    rule_inventory = build_rule_inventory(
        findings=(),
        execution_facts=(),
        pack_enabled=pack_enabled,
    )
    return (
        PerformanceFindingInventory(),
        rule_inventory,
        PerformanceSeverityInventory(),
        PerformanceConfidenceInventory(),
        build_performance_family_inventory(()),
    )


def _empty_synthesis() -> PerformanceSynthesisResult:
    return PerformanceSynthesisResult(
        status=PerformanceSynthesisStatus.NOT_REQUESTED,
        synthesis_version=SYNTHESIS_VERSION,
        overall_posture_summary="",
    )


def _build_section(
    *,
    repository_id: str,
    status: PerformanceAssessmentStatus,
    pack_enabled: bool,
    section_enabled: bool,
    reason: str,
    rules_planned: int = 0,
    configuration_fingerprint: str | None = None,
) -> PerformanceAssessmentSection:
    limitations = _foundation_limitations(pack_enabled=pack_enabled)
    fingerprint = configuration_fingerprint or build_empty_section_fingerprint(
        repository_id=repository_id,
        pack_enabled=pack_enabled,
        section_enabled=section_enabled,
    )
    assessment_id = build_assessment_id(
        repository_id=repository_id,
        status=status.value,
        configuration_fingerprint=fingerprint,
    )
    (
        finding_inventory,
        rule_inventory,
        severity_inventory,
        confidence_inventory,
        performance_family_inventory,
    ) = _empty_inventories(pack_enabled=pack_enabled)
    return PerformanceAssessmentSection(
        section_id=SECTION_ID,
        section_version=SECTION_SCHEMA_VERSION,
        assessment_id=assessment_id,
        status=status,
        capability="performance",
        repository_id=repository_id,
        performance_pack_id=PACK_ID,
        performance_pack_version=PACK_VERSION,
        evidence_pipeline="not_configured",
        configuration_fingerprint=fingerprint,
        execution_summary=PerformanceExecutionSummary(
            performance_rules_planned=rules_planned,
            rules_executed=0,
            total_finding_count=0,
            visible_finding_count=0,
            pack_id=PACK_ID,
            pack_version=PACK_VERSION,
            pack_enabled=pack_enabled,
        ),
        coverage=_coverage(pack_enabled=pack_enabled, inventory_complete=False),
        finding_inventory=finding_inventory,
        rule_inventory=rule_inventory,
        severity_inventory=severity_inventory,
        confidence_inventory=confidence_inventory,
        performance_family_inventory=performance_family_inventory,
        synthesis=_empty_synthesis(),
        themes=(),
        theme_ids=(),
        conclusions=(),
        conclusion_ids=(),
        recommendations=(),
        recommendation_ids=(),
        finding_ids=(),
        all_finding_ids=(),
        findings=(),
        limitations=limitations,
        diagnostics=(reason,),
        traceability=_lifecycle_traceability(pack_id=PACK_ID, limitations=limitations),
        metadata={
            "assessment_milestone": _MILESTONE,
            "reason": reason,
            "summary": (
                "Performance Intelligence assessment section with empty "
                "inventories. Does not establish performance, scalability, "
                "latency, or throughput posture."
            ),
            "synthesis_version": SYNTHESIS_VERSION,
        },
    )


class PerformanceAssessmentAssembler:
    """Assemble Performance assessment sections (inventory + synthesis)."""

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "performance_pack_disabled",
    ) -> PerformanceAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.DISABLED,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
        )

    def assemble_not_requested(
        self,
        *,
        repository_id: str,
        reason: str = "performance_analysis_not_requested",
    ) -> PerformanceAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.NOT_REQUESTED,
            pack_enabled=False,
            section_enabled=False,
            reason=reason,
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_performance_findings",
    ) -> PerformanceAssessmentSection:
        status = (
            PerformanceAssessmentStatus.SUCCEEDED
            if pack_enabled
            else PerformanceAssessmentStatus.DISABLED
        )
        return _build_section(
            repository_id=repository_id,
            status=status,
            pack_enabled=pack_enabled,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS) if pack_enabled else 0,
        )

    def assemble_insufficient_evidence(
        self,
        *,
        repository_id: str,
        reason: str = "performance_evidence_unavailable",
        configuration_payload: str = "",
    ) -> PerformanceAssessmentSection:
        fingerprint = build_configuration_fingerprint(
            configuration_payload or f"insufficient|{repository_id}"
        )
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
            configuration_fingerprint=fingerprint,
        )

    def assemble_partially_succeeded(
        self,
        *,
        repository_id: str,
        reason: str = "performance_assessment_partial",
    ) -> PerformanceAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.PARTIALLY_SUCCEEDED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
        )

    def assemble_failed(
        self,
        *,
        repository_id: str,
        reason: str = "performance_assessment_failed",
    ) -> PerformanceAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.FAILED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
        )

    def assemble_not_applicable(
        self,
        *,
        repository_id: str,
        reason: str = "performance_assessment_not_applicable",
    ) -> PerformanceAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=PerformanceAssessmentStatus.NOT_APPLICABLE,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
        )

    def assemble(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding] = (),
        pack_enabled: bool = True,
        rules_planned: int | None = None,
        rules_executed: int = 0,
        rules_matched: int = 0,
        rules_not_matched: int = 0,
        rules_not_applicable: int = 0,
        rules_failed: int = 0,
        rule_execution_facts: Sequence[object] = (),
        evidence_pipeline: str = "not_configured",
        evidence_fingerprint: str = "",
        configuration_payload: str = "",
        diagnostics: Sequence[str] = (),
        include_findings: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_execution_summary: bool = True,
        include_synthesis: bool = True,
    ) -> PerformanceAssessmentSection:
        """Assemble a Performance Hygiene assessment section with inventories and synthesis."""

        if not pack_enabled:
            return self.assemble_disabled(repository_id=repository_id)

        ordered_findings = tuple(
            sorted(findings, key=lambda item: (item.rule_id, item.id, item.title))
        )
        inventory_findings = ordered_findings if include_findings else ()
        finding_ids = tuple(item.id for item in inventory_findings)
        planned = rules_planned if rules_planned is not None else len(HYGIENE_RULE_IDS)
        execution_facts = coerce_execution_facts(rule_execution_facts)
        if not execution_facts and rules_executed:
            execution_facts = tuple(
                PerformanceRuleExecutionFact(
                    rule_id=rule_id,
                    enabled=True,
                    executed=True,
                    evaluation_status="not_matched",
                )
                for rule_id in HYGIENE_RULE_IDS
            )

        finding_inventory = build_finding_inventory(inventory_findings)
        rule_inventory = build_rule_inventory(
            findings=inventory_findings,
            execution_facts=execution_facts,
            pack_enabled=True,
        )
        severity_inventory = build_severity_inventory(inventory_findings)
        confidence_inventory = build_confidence_inventory(inventory_findings)
        performance_family_inventory = build_performance_family_inventory(inventory_findings)

        matched = rules_matched or rule_inventory.rules_matched
        not_matched = rules_not_matched or rule_inventory.rules_not_matched
        not_applicable = rules_not_applicable or rule_inventory.rules_not_applicable
        failed = rules_failed or rule_inventory.rules_failed
        executed = rules_executed or rule_inventory.rules_executed

        limitations = _hygiene_limitations(pack_enabled=True) if include_limitations else ()
        fingerprint = build_configuration_fingerprint(
            configuration_payload
            or (
                f"repository_id={repository_id}|pack={PACK_ID}|"
                f"evidence={evidence_fingerprint}|findings={len(finding_ids)}"
            )
        )
        status = PerformanceAssessmentStatus.SUCCEEDED
        assessment_id = build_assessment_id(
            repository_id=repository_id,
            status=status.value,
            configuration_fingerprint=fingerprint,
        )
        by_rule = findings_by_rule_counts(inventory_findings)
        summary = (
            _ZERO_FINDINGS_SUMMARY
            if not finding_ids
            else (
                f"Performance Hygiene pack produced {len(finding_ids)} finding"
                f"{'' if len(finding_ids) == 1 else 's'} from repository "
                "performance evidence."
            )
        )

        synthesis = PerformanceSynthesisResult()
        synthesis_diagnostics: tuple[str, ...] = ()
        try:
            synthesis = synthesize_performance(
                repository_id=repository_id,
                pack_enabled=True,
                section_status=status,
                findings=inventory_findings,
                finding_inventory=finding_inventory,
                rule_inventory=rule_inventory,
                performance_family_inventory=performance_family_inventory,
                limitations=limitations,
                evidence_status=evidence_pipeline,
                include_synthesis=include_synthesis,
            )
            synthesis_diagnostics = synthesis.diagnostics
        except Exception as error:  # noqa: BLE001 - isolate synthesis failures
            synthesis = PerformanceSynthesisResult(
                status=PerformanceSynthesisStatus.FAILED,
                synthesis_version=SYNTHESIS_VERSION,
                diagnostics=(f"synthesis_failed:{type(error).__name__}",),
            )
            synthesis_diagnostics = synthesis.diagnostics

        execution = (
            PerformanceExecutionSummary(
                performance_rules_planned=planned,
                rules_executed=executed,
                rules_matched=matched,
                rules_not_matched=not_matched,
                rules_not_applicable=not_applicable,
                rules_failed=failed,
                visible_finding_count=len(finding_ids),
                total_finding_count=len(finding_ids),
                findings_by_rule=by_rule,
                pack_id=PACK_ID,
                pack_version=PACK_VERSION,
                pack_enabled=True,
                theme_count=len(synthesis.themes),
                conclusion_count=len(synthesis.conclusions),
                recommendation_count=len(synthesis.recommendations),
            )
            if include_execution_summary
            else PerformanceExecutionSummary()
        )
        coverage = (
            _coverage(
                pack_enabled=True,
                findings_count=len(finding_ids),
                rules_executed=executed,
                inventory_complete=True,
            )
            if include_coverage
            else PerformanceCoverageSummary()
        )
        traceability = (
            _lifecycle_traceability(
                pack_id=PACK_ID,
                limitations=limitations,
                finding_ids=finding_ids,
                theme_ids=synthesis.theme_ids,
                conclusion_ids=synthesis.conclusion_ids,
                recommendation_ids=synthesis.recommendation_ids,
            )
            if include_traceability
            else PerformanceTraceabilityIndex()
        )
        merged_diagnostics = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in (*diagnostics, *synthesis_diagnostics)
                    if str(item).strip()
                }
            )
        )
        return PerformanceAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            assessment_id=assessment_id,
            status=status,
            capability="performance",
            repository_id=repository_id,
            performance_pack_id=PACK_ID,
            performance_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline or "repository_performance",
            evidence_fingerprint=evidence_fingerprint,
            configuration_fingerprint=fingerprint,
            execution_summary=execution,
            coverage=coverage,
            finding_inventory=finding_inventory,
            rule_inventory=rule_inventory,
            severity_inventory=severity_inventory,
            confidence_inventory=confidence_inventory,
            performance_family_inventory=performance_family_inventory,
            synthesis=synthesis,
            themes=synthesis.themes,
            theme_ids=synthesis.theme_ids,
            conclusions=synthesis.conclusions,
            conclusion_ids=synthesis.conclusion_ids,
            recommendations=synthesis.recommendations,
            recommendation_ids=synthesis.recommendation_ids,
            finding_ids=finding_ids,
            all_finding_ids=finding_ids,
            findings=finding_ids,
            limitations=limitations,
            diagnostics=merged_diagnostics,
            traceability=traceability,
            metadata={
                "assessment_milestone": _MILESTONE,
                "summary": summary,
                "families_observed": str(performance_family_inventory.families_observed),
                "synthesis_version": SYNTHESIS_VERSION,
                "overall_posture_summary": synthesis.overall_posture_summary,
            },
        )
