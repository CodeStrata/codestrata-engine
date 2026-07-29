"""Security assessment assembler (Phase 4.5.5).

Projects shared security Findings, repository-sensitive evidence, and rule
execution facts into SecurityAssessmentSection inventories and deterministic
synthesis. No scores, report fields, or AI narrative.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.security.assessment.inventory import (
    SecurityRuleExecutionFact,
    build_category_inventory,
    build_confidence_inventory,
    build_diagnostics_summary,
    build_evidence_summary,
    build_evidence_type_inventory,
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    build_inventory_traceability,
    build_rule_inventory,
    build_severity_inventory,
    count_failed_rules,
    count_succeeded_rules,
    findings_by_rule_counts,
)
from codestrata.application.security.synthesis import synthesize_security
from codestrata.domain.evidence.repository_sensitive.enums import (
    RepositorySensitiveParseStatus,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
)
from codestrata.domain.findings.models import Finding
from codestrata.domain.security.assessment.enums import (
    SecurityAssessmentStatus,
    SecurityCoverageAreaStatus,
    SecurityCoverageMaturity,
    SecurityLimitationCategory,
    SecuritySourceRole,
    SecurityTraceabilityRelation,
)
from codestrata.domain.security.assessment.identifiers import (
    MAX_TRACEABILITY_ENTRIES,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_configuration_fingerprint,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.security.assessment.models import (
    SecurityAssessmentSection,
    SecurityCoverageArea,
    SecurityCoverageSummary,
    SecurityExecutionSummary,
    SecurityLimitation,
    SecurityTraceabilityEdge,
    SecurityTraceabilityIndex,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS, PACK_ID, PACK_VERSION
from codestrata.domain.security.synthesis.enums import SecuritySynthesisStatus
from codestrata.domain.security.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.security.synthesis.models import SecuritySynthesisResult

_MILESTONE = "4.5.5"


def _limitation(
    *,
    category: SecurityLimitationCategory,
    summary: str,
    affected_capability: str,
    importance: str = "contextual",
) -> SecurityLimitation:
    return SecurityLimitation(
        limitation_id=build_limitation_id(
            category=category.value, summary=summary
        ),
        category=category,
        summary=summary,
        affected_capability=affected_capability,
        importance=importance,
    )


def _inventory_limitations(*, pack_enabled: bool) -> tuple[SecurityLimitation, ...]:
    items = [
        _limitation(
            category=SecurityLimitationCategory.FOUNDATION_ONLY,
            summary=(
                "Security Intelligence Phase 4.5.5 organizes repository-local "
                "hygiene Findings into inventories and deterministic synthesis. "
                "Zero findings does not mean the repository is secure."
            ),
            affected_capability="security_assessment",
            importance="critical",
        ),
        _limitation(
            category=SecurityLimitationCategory.SECURITY_EVIDENCE_NOT_IMPLEMENTED,
            summary=(
                "Assessment inventory consumes platform repository-sensitive "
                "evidence snapshots only; no Git history or runtime environment."
            ),
            affected_capability="security_evidence",
            importance="critical",
        ),
        _limitation(
            category=SecurityLimitationCategory.RULES_NOT_IMPLEMENTED,
            summary=(
                "Security hygiene rules evaluate typed repository-sensitive "
                "evidence facts only; inventory does not re-run rules."
                if pack_enabled
                else "Security rule pack is disabled; no security rules ran."
            ),
            affected_capability="security_rules",
            importance="critical",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_RUNTIME_ANALYSIS,
            summary="No runtime security analysis or secret validity checks.",
            affected_capability="runtime_analysis",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_EXTERNAL_VULNERABILITY_METADATA,
            summary=(
                "No external vulnerability metadata, CVE, or package registry "
                "queries."
            ),
            affected_capability="vulnerability_metadata",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_PACKAGE_REGISTRY_QUERY,
            summary="No package registry access is performed.",
            affected_capability="package_registry",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_SAST,
            summary=(
                "No SAST, DAST, entropy analysis, keystore decryption, or "
                "certificate trust/expiry analysis."
            ),
            affected_capability="sast",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_DATA_FLOW_ANALYSIS,
            summary="No taint or data-flow analysis is performed.",
            affected_capability="data_flow",
        ),
        _limitation(
            category=SecurityLimitationCategory.NO_GIT_HISTORY_ANALYSIS,
            summary="No git-history security analysis is performed.",
            affected_capability="git_history",
        ),
        _limitation(
            category=SecurityLimitationCategory.BUSINESS_IMPACT_UNKNOWN,
            summary="Business impact remains unknown for hygiene findings.",
            affected_capability="business_impact",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _coverage(
    *,
    pack_enabled: bool,
    evidence_available: bool,
    findings_count: int,
    rules_executed: int,
) -> SecurityCoverageSummary:
    areas = [
        SecurityCoverageArea(
            area_id="security_capability_requested",
            status=SecurityCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=SecurityCoverageMaturity.MEDIUM,
            limitations=("hygiene_rules_and_inventory_only",),
        ),
        SecurityCoverageArea(
            area_id="security_rules_enabled",
            status=(
                SecurityCoverageAreaStatus.MEASURED
                if pack_enabled
                else SecurityCoverageAreaStatus.NOT_APPLICABLE
            ),
            numerator=rules_executed if pack_enabled else 0,
            denominator=len(HYGIENE_RULE_IDS) if pack_enabled else 0,
            ratio=(
                (rules_executed / len(HYGIENE_RULE_IDS))
                if pack_enabled and HYGIENE_RULE_IDS
                else None
            ),
            maturity=SecurityCoverageMaturity.MEDIUM,
            limitations=(),
        ),
        SecurityCoverageArea(
            area_id="security_evidence_availability",
            status=(
                SecurityCoverageAreaStatus.MEASURED
                if evidence_available
                else SecurityCoverageAreaStatus.UNSUPPORTED
            ),
            numerator=1 if evidence_available else 0,
            denominator=1,
            ratio=1.0 if evidence_available else 0.0,
            maturity=(
                SecurityCoverageMaturity.MEDIUM
                if evidence_available
                else SecurityCoverageMaturity.LOW
            ),
            limitations=(
                ()
                if evidence_available
                else ("repository_sensitive_evidence_unavailable",)
            ),
        ),
        SecurityCoverageArea(
            area_id="security_inventory_assembled",
            status=SecurityCoverageAreaStatus.MEASURED,
            numerator=1,
            denominator=1,
            ratio=1.0,
            maturity=SecurityCoverageMaturity.MEDIUM,
            limitations=("no_synthesis",),
        ),
        SecurityCoverageArea(
            area_id="security_findings_evaluated",
            status=SecurityCoverageAreaStatus.MEASURED,
            numerator=findings_count,
            denominator=findings_count,
            ratio=1.0 if findings_count else None,
            maturity=SecurityCoverageMaturity.MEDIUM,
            limitations=("production_primary_views",),
        ),
    ]
    return SecurityCoverageSummary(
        areas=tuple(sorted(areas, key=lambda item: item.area_id))
    )


def _lifecycle_traceability(
    *,
    pack_id: str,
    limitations: tuple[SecurityLimitation, ...],
) -> SecurityTraceabilityIndex:
    edges: list[SecurityTraceabilityEdge] = [
        SecurityTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=SecurityTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=SecurityTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for item in limitations:
        edges.append(
            SecurityTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=SecurityTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=item.limitation_id,
                ),
                relation=SecurityTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=item.limitation_id,
            )
        )
    for area in (
        "security_capability_requested",
        "security_rules_enabled",
        "security_evidence_availability",
        "security_inventory_assembled",
        "security_findings_evaluated",
    ):
        edges.append(
            SecurityTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=SecurityTraceabilityRelation.SECTION_TO_COVERAGE.value,
                    source_id=SECTION_ID,
                    target_id=area,
                ),
                relation=SecurityTraceabilityRelation.SECTION_TO_COVERAGE,
                source_id=SECTION_ID,
                target_id=area,
            )
        )
    return SecurityTraceabilityIndex(
        edges=tuple(sorted(edges, key=lambda item: item.edge_id))
    )


def _resolve_status(
    *,
    pack_enabled: bool,
    evidence_enabled: bool,
    evidence: AggregatedRepositorySensitiveEvidence | None,
    execution_facts: Sequence[SecurityRuleExecutionFact],
) -> SecurityAssessmentStatus:
    """Status reflects collection/evaluation completeness, not finding presence."""

    if not pack_enabled:
        return SecurityAssessmentStatus.DISABLED
    if not evidence_enabled or evidence is None:
        return SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE

    failed = count_failed_rules(execution_facts)
    succeeded = count_succeeded_rules(execution_facts)
    executed = sum(1 for item in execution_facts if item.executed)

    if evidence.status is RepositorySensitiveParseStatus.FAILED:
        if executed == 0 or (failed > 0 and succeeded == 0):
            return SecurityAssessmentStatus.FAILED
        return SecurityAssessmentStatus.PARTIALLY_SUCCEEDED

    if executed > 0 and failed > 0 and succeeded == 0:
        return SecurityAssessmentStatus.FAILED
    if failed > 0:
        return SecurityAssessmentStatus.PARTIALLY_SUCCEEDED
    if evidence.status is RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED:
        return SecurityAssessmentStatus.PARTIALLY_SUCCEEDED
    return SecurityAssessmentStatus.SUCCEEDED


def _build_section(
    *,
    repository_id: str,
    status: SecurityAssessmentStatus,
    pack_enabled: bool,
    section_enabled: bool,
    reason: str,
    rules_planned: int = 0,
    evidence_pipeline: str = "not_configured",
    evidence_fingerprint: str = "",
    configuration_fingerprint: str | None = None,
    evidence: AggregatedRepositorySensitiveEvidence | None = None,
) -> SecurityAssessmentSection:
    limitations = _inventory_limitations(pack_enabled=pack_enabled)
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
    evidence_summary = build_evidence_summary(evidence)
    evidence_type_inventory = build_evidence_type_inventory(evidence)
    diagnostics_summary = build_diagnostics_summary(
        evidence=evidence,
        assessment_diagnostics=(reason,),
    )
    return SecurityAssessmentSection(
        section_id=SECTION_ID,
        section_version=SECTION_SCHEMA_VERSION,
        assessment_id=assessment_id,
        status=status,
        repository_id=repository_id,
        security_pack_id=PACK_ID,
        security_pack_version=PACK_VERSION,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint
        or (evidence.evidence_fingerprint if evidence is not None else ""),
        configuration_fingerprint=fingerprint,
        execution_summary=SecurityExecutionSummary(
            security_rules_planned=rules_planned,
            rules_executed=0,
            visible_finding_count=0,
            total_finding_count=0,
            pack_id=PACK_ID,
            pack_version=PACK_VERSION,
            pack_enabled=pack_enabled,
        ),
        evidence_summary=evidence_summary,
        evidence_type_inventory=evidence_type_inventory,
        diagnostics_summary=diagnostics_summary,
        coverage=_coverage(
            pack_enabled=pack_enabled,
            evidence_available=evidence is not None,
            findings_count=0,
            rules_executed=0,
        ),
        finding_ids=(),
        finding_summaries=(),
        all_finding_ids=(),
        all_finding_summaries=(),
        rule_inventory=build_rule_inventory(
            refs=(),
            pack_enabled=pack_enabled,
            execution_facts=(),
        ),
        limitations=limitations,
        diagnostics=(reason,),
        traceability=_lifecycle_traceability(pack_id=PACK_ID, limitations=limitations),
        enterprise_context_used=False,
        business_impact="unknown",
        metadata={"assessment_milestone": _MILESTONE},
    )


class SecurityAssessmentAssembler:
    """Build security assessment inventories (Phase 4.5.4)."""

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "security_pack_disabled",
        evidence: AggregatedRepositorySensitiveEvidence | None = None,
    ) -> SecurityAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.DISABLED,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
            evidence=evidence,
            evidence_pipeline=(
                "repository_sensitive" if evidence is not None else "not_configured"
            ),
            evidence_fingerprint=(
                evidence.evidence_fingerprint if evidence is not None else ""
            ),
        )

    def assemble_not_requested(
        self,
        *,
        repository_id: str,
        reason: str = "security_section_not_requested",
    ) -> SecurityAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.NOT_REQUESTED,
            pack_enabled=False,
            section_enabled=False,
            reason=reason,
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_security_rules_registered",
    ) -> SecurityAssessmentSection:
        status = (
            SecurityAssessmentStatus.SUCCEEDED
            if pack_enabled
            else SecurityAssessmentStatus.DISABLED
        )
        return _build_section(
            repository_id=repository_id,
            status=status,
            pack_enabled=pack_enabled,
            section_enabled=True,
            reason=reason,
            rules_planned=0,
        )

    def assemble_insufficient_evidence(
        self,
        *,
        repository_id: str,
        reason: str = "security_evidence_unavailable",
        configuration_payload: str = "",
    ) -> SecurityAssessmentSection:
        fingerprint = build_configuration_fingerprint(
            configuration_payload or f"insufficient|{repository_id}"
        )
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE,
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
        reason: str = "security_assessment_partial",
        evidence: AggregatedRepositorySensitiveEvidence | None = None,
    ) -> SecurityAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.PARTIALLY_SUCCEEDED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
            evidence=evidence,
        )

    def assemble_failed(
        self,
        *,
        repository_id: str,
        reason: str = "security_assessment_failed",
    ) -> SecurityAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.FAILED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=len(HYGIENE_RULE_IDS),
        )

    def assemble_not_applicable(
        self,
        *,
        repository_id: str,
        reason: str = "security_assessment_not_applicable",
    ) -> SecurityAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=SecurityAssessmentStatus.NOT_APPLICABLE,
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
        evidence_enabled: bool = False,
        evidence_available: bool = False,
        include_findings: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_execution_summary: bool = True,
        include_synthesis: bool = True,
        evidence_pipeline: str = "not_configured",
        evidence_fingerprint: str = "",
        configuration_payload: str = "",
        security_rules_planned: int | None = None,
        rules_executed: int = 0,
        rules_matched: int = 0,
        rules_not_matched: int = 0,
        rules_not_applicable: int = 0,
        diagnostics: Sequence[str] = (),
        repository_sensitive_evidence: AggregatedRepositorySensitiveEvidence
        | None = None,
        rule_execution_facts: Sequence[SecurityRuleExecutionFact] = (),
    ) -> SecurityAssessmentSection:
        """Assemble inventory and optional synthesis from in-memory facts."""

        if not pack_enabled:
            return self.assemble_disabled(
                repository_id=repository_id,
                evidence=repository_sensitive_evidence,
            )
        evidence = repository_sensitive_evidence
        if not evidence_available or evidence is None:
            return self.assemble_insufficient_evidence(
                repository_id=repository_id,
                reason="repository_sensitive_evidence_unavailable",
                configuration_payload=configuration_payload,
            )

        all_refs = (
            build_finding_references(findings) if include_findings else ()
        )
        production_refs = tuple(
            item
            for item in all_refs
            if item.source_role is SecuritySourceRole.PRODUCTION
        )
        primary_finding_ids = tuple(item.finding_id for item in production_refs)
        all_finding_ids = tuple(item.finding_id for item in all_refs)

        execution_facts = tuple(rule_execution_facts)
        if not execution_facts and rules_executed:
            execution_facts = tuple(
                SecurityRuleExecutionFact(
                    rule_id=rule_id,
                    enabled=True,
                    executed=True,
                    evaluation_status="not_matched",
                )
                for rule_id in HYGIENE_RULE_IDS
            )

        status = _resolve_status(
            pack_enabled=True,
            evidence_enabled=evidence_enabled or evidence is not None,
            evidence=evidence,
            execution_facts=execution_facts,
        )

        finding_inventory = build_finding_inventory(all_refs)
        rule_inventory = build_rule_inventory(
            refs=all_refs,
            execution_facts=execution_facts,
            pack_enabled=True,
        )
        category_inventory = build_category_inventory(all_refs)
        severity_inventory = build_severity_inventory(all_refs)
        confidence_inventory = build_confidence_inventory(all_refs)
        evidence_summary = build_evidence_summary(evidence)
        evidence_type_inventory = build_evidence_type_inventory(evidence)
        hotspot_inventory = build_hotspot_inventory(all_refs)
        diagnostics_summary = build_diagnostics_summary(
            evidence=evidence,
            execution_facts=execution_facts,
            assessment_diagnostics=diagnostics,
        )

        planned = (
            security_rules_planned
            if security_rules_planned is not None
            else len(HYGIENE_RULE_IDS)
        )
        limitations = (
            _inventory_limitations(pack_enabled=True) if include_limitations else ()
        )
        fingerprint = build_configuration_fingerprint(
            configuration_payload
            or (
                f"repository_id={repository_id}|pack={PACK_ID}|"
                f"evidence={evidence_fingerprint}|findings={len(all_refs)}"
            )
        )
        assessment_id = build_assessment_id(
            repository_id=repository_id,
            status=status.value,
            configuration_fingerprint=fingerprint,
        )
        failed = count_failed_rules(execution_facts)
        by_rule = findings_by_rule_counts(all_refs)
        executed_count = rules_executed or sum(
            1 for item in execution_facts if item.executed
        )

        synthesis = SecuritySynthesisResult()
        synthesis_diagnostics: tuple[str, ...] = ()
        try:
            synthesis = synthesize_security(
                repository_id=repository_id,
                pack_enabled=True,
                section_status=status,
                finding_summaries=all_refs,
                finding_inventory=finding_inventory,
                hotspot_inventory=hotspot_inventory,
                evidence_summary=evidence_summary,
                diagnostics_summary=diagnostics_summary,
                rule_inventory=rule_inventory,
                limitations=limitations,
                include_synthesis=include_synthesis,
            )
            synthesis_diagnostics = synthesis.diagnostics
        except Exception as error:  # noqa: BLE001 - isolate synthesis failures
            synthesis = SecuritySynthesisResult(
                status=SecuritySynthesisStatus.FAILED,
                synthesis_version=SYNTHESIS_VERSION,
                diagnostics=(
                    f"synthesis_failed:{type(error).__name__}",
                ),
            )
            synthesis_diagnostics = synthesis.diagnostics

        execution = (
            SecurityExecutionSummary(
                security_rules_planned=planned,
                rules_executed=executed_count,
                rules_matched=rules_matched or sum(
                    1 for item in execution_facts if item.evaluation_status == "matched"
                ),
                rules_not_matched=rules_not_matched,
                rules_not_applicable=rules_not_applicable,
                rules_failed=failed,
                visible_finding_count=len(primary_finding_ids),
                total_finding_count=len(all_refs),
                findings_by_rule=by_rule,
                pack_id=PACK_ID,
                pack_version=PACK_VERSION,
                pack_enabled=True,
                theme_count=len(synthesis.theme_ids),
                conclusion_count=len(synthesis.conclusion_ids),
                recommendation_count=len(synthesis.recommendation_ids),
            )
            if include_execution_summary
            else SecurityExecutionSummary()
        )
        coverage = (
            _coverage(
                pack_enabled=True,
                evidence_available=True,
                findings_count=len(all_refs),
                rules_executed=executed_count,
            )
            if include_coverage
            else SecurityCoverageSummary()
        )
        hotspot_ids = tuple(item.hotspot_id for item in hotspot_inventory.hotspots)
        base_traceability = (
            build_inventory_traceability(
                pack_id=PACK_ID,
                limitation_ids=tuple(item.limitation_id for item in limitations),
                finding_refs=all_refs,
                hotspot_ids=hotspot_ids,
            )
            if include_traceability
            else SecurityTraceabilityIndex()
        )
        synthesis_edges: list[SecurityTraceabilityEdge] = []
        if include_traceability:
            for theme_id in synthesis.theme_ids[:MAX_TRACEABILITY_ENTRIES]:
                synthesis_edges.append(
                    SecurityTraceabilityEdge(
                        edge_id=build_trace_edge_id(
                            relation=SecurityTraceabilityRelation.SECTION_TO_THEME.value,
                            source_id=SECTION_ID,
                            target_id=theme_id,
                        ),
                        relation=SecurityTraceabilityRelation.SECTION_TO_THEME,
                        source_id=SECTION_ID,
                        target_id=theme_id,
                    )
                )
            for conclusion_id in synthesis.conclusion_ids[
                : max(0, MAX_TRACEABILITY_ENTRIES - len(synthesis_edges))
            ]:
                synthesis_edges.append(
                    SecurityTraceabilityEdge(
                        edge_id=build_trace_edge_id(
                            relation=(
                                SecurityTraceabilityRelation.SECTION_TO_CONCLUSION.value
                            ),
                            source_id=SECTION_ID,
                            target_id=conclusion_id,
                        ),
                        relation=SecurityTraceabilityRelation.SECTION_TO_CONCLUSION,
                        source_id=SECTION_ID,
                        target_id=conclusion_id,
                    )
                )
            for recommendation_id in synthesis.recommendation_ids[:3]:
                synthesis_edges.append(
                    SecurityTraceabilityEdge(
                        edge_id=build_trace_edge_id(
                            relation=(
                                SecurityTraceabilityRelation.SECTION_TO_RECOMMENDATION.value
                            ),
                            source_id=SECTION_ID,
                            target_id=recommendation_id,
                        ),
                        relation=SecurityTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                        source_id=SECTION_ID,
                        target_id=recommendation_id,
                    )
                )
        merged_edges = tuple(
            sorted(
                {
                    edge.edge_id: edge
                    for edge in (*base_traceability.edges, *synthesis_edges)
                }.values(),
                key=lambda item: item.edge_id,
            )
        )
        traceability = SecurityTraceabilityIndex(edges=merged_edges)
        merged_diagnostics = tuple(
            sorted(
                {
                    *(str(item).strip() for item in diagnostics if str(item).strip()),
                    *synthesis_diagnostics,
                    *(
                        (f"evidence_status:{evidence.status.value}",)
                        if evidence.status
                        is RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED
                        else ()
                    ),
                    *(
                        (f"rules_failed:{failed}",)
                        if failed
                        else ()
                    ),
                }
            )
        )
        return SecurityAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            assessment_id=assessment_id,
            status=status,
            repository_id=repository_id,
            security_pack_id=PACK_ID,
            security_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline,
            evidence_fingerprint=evidence_fingerprint
            or evidence.evidence_fingerprint,
            configuration_fingerprint=fingerprint,
            execution_summary=execution,
            evidence_summary=evidence_summary,
            coverage=coverage,
            finding_ids=primary_finding_ids if include_findings else (),
            finding_summaries=production_refs if include_findings else (),
            all_finding_ids=all_finding_ids if include_findings else (),
            all_finding_summaries=all_refs if include_findings else (),
            finding_inventory=finding_inventory,
            rule_inventory=rule_inventory,
            category_inventory=category_inventory,
            severity_inventory=severity_inventory,
            confidence_inventory=confidence_inventory,
            evidence_type_inventory=evidence_type_inventory,
            hotspot_inventory=hotspot_inventory,
            diagnostics_summary=diagnostics_summary,
            synthesis=synthesis,
            themes=synthesis.themes,
            theme_ids=synthesis.theme_ids,
            concentration_facts=synthesis.concentration_facts,
            conclusions=synthesis.conclusions,
            conclusion_ids=synthesis.conclusion_ids,
            recommendations=synthesis.recommendations,
            recommendation_ids=synthesis.recommendation_ids,
            limitations=limitations,
            diagnostics=merged_diagnostics,
            traceability=traceability,
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={
                "assessment_milestone": _MILESTONE,
                "synthesis_version": SYNTHESIS_VERSION,
                "production_primary": "finding_ids_and_finding_summaries",
                "all_findings": "all_finding_ids_and_all_finding_summaries",
                "hotspot_ordering": (
                    "presentation_only:production_count,total_count,"
                    "highest_severity,path"
                ),
            },
        )
