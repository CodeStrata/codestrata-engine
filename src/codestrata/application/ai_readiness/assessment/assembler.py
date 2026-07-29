"""AI Readiness assessment assembler (Phase 4.8.5).

Projects AI Readiness Assessment sections with deterministic inventories and
synthesis over existing AI Readiness Hygiene Findings and rule-execution facts.
No report projection.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.ai_readiness.assessment.inventory import (
    AiReadinessRuleExecutionFact,
    build_capability_family_inventory,
    build_confidence_inventory,
    build_finding_inventory,
    build_rule_inventory,
    build_severity_inventory,
    coerce_execution_facts,
    findings_by_rule_counts,
)
from codestrata.application.ai_readiness.synthesis.service import synthesize_ai_readiness
from codestrata.domain.ai_readiness.assessment.enums import (
    AiReadinessAssessmentStatus,
    AiReadinessCoverageAreaStatus,
    AiReadinessCoverageMaturity,
    AiReadinessLimitationCategory,
    AiReadinessTraceabilityRelation,
)
from codestrata.domain.ai_readiness.assessment.identifiers import (
    MAX_TRACEABILITY_ENTRIES,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_configuration_fingerprint,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.ai_readiness.assessment.models import (
    AiReadinessAssessmentSection,
    AiReadinessCapabilityFamilyInventory,
    AiReadinessConfidenceInventory,
    AiReadinessCoverageArea,
    AiReadinessCoverageSummary,
    AiReadinessExecutionSummary,
    AiReadinessFindingInventory,
    AiReadinessLimitation,
    AiReadinessRuleInventory,
    AiReadinessSeverityInventory,
    AiReadinessTraceabilityEdge,
    AiReadinessTraceabilityIndex,
)
from codestrata.domain.ai_readiness.ids import HYGIENE_RULE_IDS, PACK_ID, PACK_VERSION
from codestrata.domain.ai_readiness.synthesis.enums import AiReadinessSynthesisStatus
from codestrata.domain.ai_readiness.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.ai_readiness.synthesis.models import AiReadinessSynthesisResult
from codestrata.domain.findings.models import Finding

_MILESTONE = "4.8.5"
_ZERO_FINDINGS_SUMMARY = (
    "AI Readiness Hygiene pack produced zero findings. This does not establish "
    "that the repository is AI ready, agent ready, or suitable for RAG."
)


def _limitation(
    *,
    category: AiReadinessLimitationCategory,
    summary: str,
    affected_capability: str,
    importance: str = "contextual",
) -> AiReadinessLimitation:
    return AiReadinessLimitation(
        limitation_id=build_limitation_id(category=category.value, summary=summary),
        category=category,
        summary=summary,
        affected_capability=affected_capability,
        importance=importance,
    )


def _foundation_limitations(*, pack_enabled: bool) -> tuple[AiReadinessLimitation, ...]:
    items = [
        _limitation(
            category=AiReadinessLimitationCategory.FOUNDATION_ONLY,
            summary=(
                "AI Readiness Intelligence inventory and deterministic "
                "synthesis; report presentation and readiness scoring remain "
                "out of scope."
            ),
            affected_capability="ai_readiness_assessment",
            importance="critical",
        ),
        _limitation(
            category=AiReadinessLimitationCategory.NO_AI_READINESS_CONCLUSION,
            summary=(
                "No conclusion about AI readiness, agent readiness, or RAG "
                "suitability can be drawn."
            ),
            affected_capability="ai_readiness",
            importance="critical",
        ),
        _limitation(
            category=AiReadinessLimitationCategory.RULES_NOT_IMPLEMENTED,
            summary=(
                "AI Readiness rule pack is disabled; no AI Readiness rules ran."
                if not pack_enabled
                else (
                    "AI Readiness Hygiene inventories summarize existing Findings "
                    "only; they do not re-run rules or collect evidence."
                )
            ),
            affected_capability="ai_readiness_rules",
            importance="critical",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _hygiene_limitations(*, pack_enabled: bool) -> tuple[AiReadinessLimitation, ...]:
    items = [
        _limitation(
            category=AiReadinessLimitationCategory.NO_AI_READINESS_CONCLUSION,
            summary=(
                "AI Readiness Hygiene findings are repository-observable "
                "signals only. Zero findings does not mean the repository is "
                "AI ready, agent ready, or suitable for RAG."
            ),
            affected_capability="ai_readiness",
            importance="critical",
        ),
        _limitation(
            category=AiReadinessLimitationCategory.OTHER,
            summary=(
                "AI Readiness Hygiene rules consume "
                "AggregatedRepositoryAiReadinessEvidence only; inventory and "
                "synthesis never re-read repository files, execute AI/LLM "
                "calls, or produce readiness scores. Report presentation is "
                "not implemented."
                if pack_enabled
                else "AI Readiness rule pack is disabled; no AI Readiness rules ran."
            ),
            affected_capability="ai_readiness_rules",
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
) -> AiReadinessCoverageSummary:
    planned = len(HYGIENE_RULE_IDS) if pack_enabled else 0
    areas = [
        AiReadinessCoverageArea(
            area_id="ai_readiness_capability_requested",
            status=AiReadinessCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=(
                AiReadinessCoverageMaturity.MEDIUM
                if pack_enabled
                else AiReadinessCoverageMaturity.LOW
            ),
            limitations=("hygiene_rules_only",) if pack_enabled else ("foundation_only",),
        ),
        AiReadinessCoverageArea(
            area_id="ai_readiness_rules_enabled",
            status=(
                AiReadinessCoverageAreaStatus.MEASURED
                if pack_enabled
                else AiReadinessCoverageAreaStatus.NOT_APPLICABLE
            ),
            numerator=rules_executed if pack_enabled else 0,
            denominator=planned,
            ratio=((rules_executed / planned) if pack_enabled and planned else None),
            maturity=(
                AiReadinessCoverageMaturity.MEDIUM
                if pack_enabled
                else AiReadinessCoverageMaturity.LOW
            ),
            limitations=() if pack_enabled else ("pack_disabled",),
        ),
        AiReadinessCoverageArea(
            area_id="ai_readiness_evidence_availability",
            status=AiReadinessCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=(
                AiReadinessCoverageMaturity.MEDIUM
                if pack_enabled
                else AiReadinessCoverageMaturity.LOW
            ),
            limitations=("findings_and_execution_facts_only",),
        ),
        AiReadinessCoverageArea(
            area_id="ai_readiness_findings_evaluated",
            status=AiReadinessCoverageAreaStatus.MEASURED,
            numerator=findings_count,
            denominator=findings_count,
            ratio=1.0 if findings_count else None,
            maturity=(
                AiReadinessCoverageMaturity.MEDIUM
                if pack_enabled
                else AiReadinessCoverageMaturity.LOW
            ),
            limitations=("hygiene_findings_only",) if pack_enabled else ("analytically_empty",),
        ),
        AiReadinessCoverageArea(
            area_id="ai_readiness_inventory_complete",
            status=(
                AiReadinessCoverageAreaStatus.MEASURED
                if inventory_complete
                else AiReadinessCoverageAreaStatus.UNSUPPORTED
            ),
            numerator=1 if inventory_complete else 0,
            denominator=1,
            ratio=1.0 if inventory_complete else 0.0,
            maturity=(
                AiReadinessCoverageMaturity.MEDIUM
                if inventory_complete
                else AiReadinessCoverageMaturity.LOW
            ),
            limitations=(
                ("inventory_and_synthesis",) if inventory_complete else ("foundation_only",)
            ),
        ),
    ]
    return AiReadinessCoverageSummary(areas=tuple(sorted(areas, key=lambda item: item.area_id)))


def _lifecycle_traceability(
    *,
    pack_id: str,
    limitations: tuple[AiReadinessLimitation, ...],
    finding_ids: tuple[str, ...] = (),
    theme_ids: tuple[str, ...] = (),
    conclusion_ids: tuple[str, ...] = (),
    recommendation_ids: tuple[str, ...] = (),
) -> AiReadinessTraceabilityIndex:
    edges: list[AiReadinessTraceabilityEdge] = [
        AiReadinessTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=AiReadinessTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=AiReadinessTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for finding_id in finding_ids:
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=finding_id,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=finding_id,
            )
        )
    for theme_id in theme_ids:
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_THEME.value,
                    source_id=SECTION_ID,
                    target_id=theme_id,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_THEME,
                source_id=SECTION_ID,
                target_id=theme_id,
            )
        )
    for conclusion_id in conclusion_ids:
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_CONCLUSION.value,
                    source_id=SECTION_ID,
                    target_id=conclusion_id,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_CONCLUSION,
                source_id=SECTION_ID,
                target_id=conclusion_id,
            )
        )
    for recommendation_id in recommendation_ids:
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_RECOMMENDATION.value,
                    source_id=SECTION_ID,
                    target_id=recommendation_id,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                source_id=SECTION_ID,
                target_id=recommendation_id,
            )
        )
    for item in limitations:
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=item.limitation_id,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=item.limitation_id,
            )
        )
    for area in (
        "ai_readiness_capability_requested",
        "ai_readiness_rules_enabled",
        "ai_readiness_evidence_availability",
        "ai_readiness_findings_evaluated",
        "ai_readiness_inventory_complete",
    ):
        edges.append(
            AiReadinessTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=AiReadinessTraceabilityRelation.SECTION_TO_COVERAGE.value,
                    source_id=SECTION_ID,
                    target_id=area,
                ),
                relation=AiReadinessTraceabilityRelation.SECTION_TO_COVERAGE,
                source_id=SECTION_ID,
                target_id=area,
            )
        )
    ordered = tuple(sorted(edges, key=lambda item: item.edge_id))
    return AiReadinessTraceabilityIndex(edges=ordered[:MAX_TRACEABILITY_ENTRIES])


def _empty_inventories(
    *,
    pack_enabled: bool,
) -> tuple[
    AiReadinessFindingInventory,
    AiReadinessRuleInventory,
    AiReadinessSeverityInventory,
    AiReadinessConfidenceInventory,
    AiReadinessCapabilityFamilyInventory,
]:
    rule_inventory = build_rule_inventory(
        findings=(),
        execution_facts=(),
        pack_enabled=pack_enabled,
    )
    return (
        AiReadinessFindingInventory(),
        rule_inventory,
        AiReadinessSeverityInventory(),
        AiReadinessConfidenceInventory(),
        build_capability_family_inventory(()),
    )


def _build_section(
    *,
    repository_id: str,
    status: AiReadinessAssessmentStatus,
    pack_enabled: bool,
    section_enabled: bool,
    reason: str,
    rules_planned: int = 0,
    configuration_fingerprint: str | None = None,
) -> AiReadinessAssessmentSection:
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
        capability_family_inventory,
    ) = _empty_inventories(pack_enabled=pack_enabled)
    return AiReadinessAssessmentSection(
        section_id=SECTION_ID,
        section_version=SECTION_SCHEMA_VERSION,
        assessment_id=assessment_id,
        status=status,
        capability="ai_readiness",
        repository_id=repository_id,
        ai_readiness_pack_id=PACK_ID,
        ai_readiness_pack_version=PACK_VERSION,
        evidence_pipeline="not_configured",
        configuration_fingerprint=fingerprint,
        execution_summary=AiReadinessExecutionSummary(
            ai_readiness_rules_planned=rules_planned,
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
        capability_family_inventory=capability_family_inventory,
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
                "AI Readiness Intelligence assessment section with empty "
                "inventories. Does not establish that the repository is AI "
                "ready, agent ready, or suitable for RAG."
            ),
            "synthesis_version": SYNTHESIS_VERSION,
        },
    )


class AiReadinessAssessmentAssembler:
    """Assemble AI Readiness assessment sections (inventory + synthesis)."""

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "ai_readiness_pack_disabled",
    ) -> AiReadinessAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.DISABLED,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
        )

    def assemble_not_requested(
        self,
        *,
        repository_id: str,
        reason: str = "ai_readiness_analysis_not_requested",
    ) -> AiReadinessAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.NOT_REQUESTED,
            pack_enabled=False,
            section_enabled=False,
            reason=reason,
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_ai_readiness_findings",
    ) -> AiReadinessAssessmentSection:
        status = (
            AiReadinessAssessmentStatus.SUCCEEDED
            if pack_enabled
            else AiReadinessAssessmentStatus.DISABLED
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
        reason: str = "ai_readiness_evidence_unavailable",
        configuration_payload: str = "",
    ) -> AiReadinessAssessmentSection:
        fingerprint = build_configuration_fingerprint(
            configuration_payload or f"insufficient|{repository_id}"
        )
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE,
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
        reason: str = "ai_readiness_assessment_partial",
    ) -> AiReadinessAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.PARTIALLY_SUCCEEDED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
        )

    def assemble_failed(
        self,
        *,
        repository_id: str,
        reason: str = "ai_readiness_assessment_failed",
    ) -> AiReadinessAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.FAILED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
        )

    def assemble_not_applicable(
        self,
        *,
        repository_id: str,
        reason: str = "ai_readiness_assessment_not_applicable",
    ) -> AiReadinessAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=AiReadinessAssessmentStatus.NOT_APPLICABLE,
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
    ) -> AiReadinessAssessmentSection:
        """Assemble an AI Readiness Hygiene assessment section with inventories and synthesis."""

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
                AiReadinessRuleExecutionFact(
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
        capability_family_inventory = build_capability_family_inventory(inventory_findings)

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
        status = AiReadinessAssessmentStatus.SUCCEEDED
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
                f"AI Readiness Hygiene pack produced {len(finding_ids)} finding"
                f"{'' if len(finding_ids) == 1 else 's'} from repository "
                "AI-readiness evidence."
            )
        )

        synthesis = AiReadinessSynthesisResult()
        synthesis_diagnostics: tuple[str, ...] = ()
        try:
            synthesis = synthesize_ai_readiness(
                repository_id=repository_id,
                pack_enabled=True,
                section_status=status,
                findings=inventory_findings,
                finding_inventory=finding_inventory,
                rule_inventory=rule_inventory,
                capability_family_inventory=capability_family_inventory,
                limitations=limitations,
                evidence_status=evidence_pipeline,
                include_synthesis=include_synthesis,
            )
            synthesis_diagnostics = synthesis.diagnostics
        except Exception as error:  # noqa: BLE001 - isolate synthesis failures
            synthesis = AiReadinessSynthesisResult(
                status=AiReadinessSynthesisStatus.FAILED,
                synthesis_version=SYNTHESIS_VERSION,
                diagnostics=(f"synthesis_failed:{type(error).__name__}",),
            )
            synthesis_diagnostics = synthesis.diagnostics

        execution = (
            AiReadinessExecutionSummary(
                ai_readiness_rules_planned=planned,
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
            else AiReadinessExecutionSummary()
        )
        coverage = (
            _coverage(
                pack_enabled=True,
                findings_count=len(finding_ids),
                rules_executed=executed,
                inventory_complete=True,
            )
            if include_coverage
            else AiReadinessCoverageSummary()
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
            else AiReadinessTraceabilityIndex()
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
        return AiReadinessAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            assessment_id=assessment_id,
            status=status,
            capability="ai_readiness",
            repository_id=repository_id,
            ai_readiness_pack_id=PACK_ID,
            ai_readiness_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline or "repository_ai_readiness",
            evidence_fingerprint=evidence_fingerprint,
            configuration_fingerprint=fingerprint,
            execution_summary=execution,
            coverage=coverage,
            finding_inventory=finding_inventory,
            rule_inventory=rule_inventory,
            severity_inventory=severity_inventory,
            confidence_inventory=confidence_inventory,
            capability_family_inventory=capability_family_inventory,
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
                "families_observed": str(capability_family_inventory.families_observed),
                "synthesis_version": SYNTHESIS_VERSION,
                "overall_posture_summary": synthesis.overall_posture_summary,
            },
        )
