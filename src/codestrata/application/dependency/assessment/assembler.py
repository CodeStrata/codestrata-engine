"""Assemble DependencyAssessmentSection (Phase 4.4.1 / 4.4.4 / 4.4.5).

Produces disabled, not-requested, empty, insufficient-evidence, inventory-, and
synthesis-backed sections. Does not parse manifests; consumes shared Findings and
AggregatedDependencyEvidence only. Synthesis consumes inventory projections only.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.dependency.assessment.inventory import (
    build_aggregation_inventory,
    build_declaration_inventory,
    build_diagnostics_summary,
    build_evidence_summary,
    build_finding_inventory,
    build_finding_references,
    build_hotspot_inventory,
    build_manifest_inventory,
    parse_failure_counts,
    production_manifests_usable,
)
from codestrata.application.dependency.synthesis.service import synthesize_dependency
from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencyCoverageAreaStatus,
    DependencyCoverageMaturity,
    DependencyLimitationCategory,
    DependencySourceRole,
    DependencyTraceabilityRelation,
)
from codestrata.domain.dependency.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.dependency.assessment.models import (
    DependencyAssessmentSection,
    DependencyCoverageArea,
    DependencyCoverageSummary,
    DependencyExecutionSummary,
    DependencyLimitation,
    DependencyTraceabilityEdge,
    DependencyTraceabilityIndex,
)
from codestrata.domain.dependency.ids import (
    HYGIENE_RULE_IDS,
    PACK_ID,
    PACK_VERSION,
    RULE_ID_PREFIX,
)
from codestrata.domain.evidence.dependency.enums import DependencyParseStatus
from codestrata.domain.evidence.dependency.models import AggregatedDependencyEvidence
from codestrata.domain.findings import Finding


def dependency_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """Filter shared findings that belong to the dependency rule namespace."""

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
    evidence_enabled: bool,
) -> tuple[DependencyLimitation, ...]:
    items: list[DependencyLimitation] = [
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.MANIFEST_PARSING_NOT_OWNED.value,
                summary="Manifest parsing owned by Dependency Evidence",
            ),
            category=DependencyLimitationCategory.MANIFEST_PARSING_NOT_OWNED,
            summary=(
                "Dependency Intelligence does not reparse Maven, Gradle, or "
                "Python manifests. Rules consume Dependency Evidence only."
            ),
            affected_capability="dependency_evidence",
            importance="material",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.STATIC_ANALYSIS_ONLY.value,
                summary="Declared dependencies only; no transitive resolution",
            ),
            category=DependencyLimitationCategory.STATIC_ANALYSIS_ONLY,
            summary=(
                "Inventory and hygiene cover declared-manifest facts only. "
                "Transitive dependencies are not resolved. Build tools are not "
                "executed. Gradle support is static-parse only."
            ),
            affected_capability="dependency_rules",
            importance="material",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.EXTERNAL_REGISTRY_NOT_QUERIED.value,
                summary="External registries not queried",
            ),
            category=DependencyLimitationCategory.EXTERNAL_REGISTRY_NOT_QUERIED,
            summary=(
                "No package-registry or internet calls are made. Version "
                "freshness and remote metadata are not assessed."
            ),
            affected_capability="dependency_external_data",
            importance="material",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.CVE_DATA_NOT_ASSESSED.value,
                summary="CVE and vulnerability data not assessed",
            ),
            category=DependencyLimitationCategory.CVE_DATA_NOT_ASSESSED,
            summary=(
                "No CVE, advisory, or vulnerability database is consulted."
            ),
            affected_capability="dependency_security",
            importance="material",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.LICENSE_NOT_ASSESSED.value,
                summary="License analysis not assessed",
            ),
            category=DependencyLimitationCategory.LICENSE_NOT_ASSESSED,
            summary="License compliance analysis is not performed.",
            affected_capability="dependency_license",
            importance="contextual",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.VERSION_FRESHNESS_NOT_ASSESSED.value,
                summary="Version freshness not assessed",
            ),
            category=DependencyLimitationCategory.VERSION_FRESHNESS_NOT_ASSESSED,
            summary=(
                "Declared vs latest version comparison is not performed."
            ),
            affected_capability="dependency_versions",
            importance="contextual",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.OTHER.value,
                summary="npm and package.json not supported",
            ),
            category=DependencyLimitationCategory.OTHER,
            summary=(
                "npm / package.json ecosystems are out of scope for this "
                "milestone. No framework or DependencyRole classification is "
                "inferred."
            ),
            affected_capability="dependency_ecosystems",
            importance="material",
        ),
        DependencyLimitation(
            limitation_id=build_limitation_id(
                category=DependencyLimitationCategory.BUSINESS_IMPACT_UNKNOWN.value,
                summary="Business impact unknown",
            ),
            category=DependencyLimitationCategory.BUSINESS_IMPACT_UNKNOWN,
            summary=(
                "Business impact remains unknown without explicit enterprise "
                "context for dependency assessment."
            ),
            affected_capability="business_impact",
            importance="contextual",
        ),
    ]
    if not evidence_enabled:
        items.append(
            DependencyLimitation(
                limitation_id=build_limitation_id(
                    category=DependencyLimitationCategory.EVIDENCE_PROVIDERS_UNAVAILABLE.value,
                    summary="Dependency evidence disabled",
                ),
                category=DependencyLimitationCategory.EVIDENCE_PROVIDERS_UNAVAILABLE,
                summary=(
                    "Dependency Evidence collection is disabled. Hygiene rules "
                    "cannot evaluate without normalized declaration facts."
                ),
                affected_capability="dependency_evidence",
                importance="material",
            )
        )
    if not pack_enabled:
        items.append(
            DependencyLimitation(
                limitation_id=build_limitation_id(
                    category=DependencyLimitationCategory.OTHER.value,
                    summary="Dependency pack disabled",
                ),
                category=DependencyLimitationCategory.OTHER,
                summary="The dependency rule pack feature gate is disabled.",
                affected_capability="dependency_pack",
                importance="informational",
            )
        )
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _coverage(
    *,
    pack_enabled: bool,
    evidence_enabled: bool,
    evidence: AggregatedDependencyEvidence | None,
) -> DependencyCoverageSummary:
    if pack_enabled:
        rule_status = DependencyCoverageAreaStatus.MEASURED
        rule_maturity = DependencyCoverageMaturity.MEDIUM
        rule_limits = (
            f"{len(HYGIENE_RULE_IDS)} declaration hygiene rules are registered.",
        )
    else:
        rule_status = DependencyCoverageAreaStatus.UNSUPPORTED
        rule_maturity = DependencyCoverageMaturity.UNKNOWN
        rule_limits = ("Dependency pack is disabled.",)

    if evidence_enabled and evidence is not None:
        denom = max(evidence.coverage.manifests_discovered, 1)
        numer = evidence.coverage.manifests_parsed + (
            evidence.coverage.manifests_partially_parsed
        )
        ratio = min(numer / denom, 1.0)
        evidence_status = (
            DependencyCoverageAreaStatus.MEASURED
            if evidence.status is DependencyParseStatus.SUCCEEDED
            else DependencyCoverageAreaStatus.PARTIAL
        )
        evidence_limits: tuple[str, ...] = (
            f"declarations={evidence.coverage.declarations_collected}",
            f"unsupported={evidence.coverage.unsupported_construct_count}",
            f"unresolved={evidence.coverage.unresolved_expression_count}",
        )
    elif evidence_enabled:
        evidence_status = DependencyCoverageAreaStatus.PARTIAL
        ratio = None
        numer = None
        denom = None
        evidence_limits = ("Evidence enabled but no aggregated facts were supplied.",)
    else:
        evidence_status = DependencyCoverageAreaStatus.UNSUPPORTED
        ratio = None
        numer = None
        denom = None
        evidence_limits = ("Dependency Evidence collection is disabled.",)

    areas = (
        DependencyCoverageArea(
            area_id="dependency_rule_coverage",
            status=rule_status,
            maturity=rule_maturity,
            limitations=rule_limits,
        ),
        DependencyCoverageArea(
            area_id="dependency_evidence_coverage",
            status=evidence_status,
            numerator=numer,
            denominator=denom,
            ratio=ratio,
            maturity=(
                DependencyCoverageMaturity.MEDIUM
                if evidence_enabled
                else DependencyCoverageMaturity.UNKNOWN
            ),
            limitations=evidence_limits,
        ),
        DependencyCoverageArea(
            area_id="enterprise_context_coverage",
            status=DependencyCoverageAreaStatus.NOT_APPLICABLE,
            maturity=DependencyCoverageMaturity.UNKNOWN,
            limitations=("Enterprise context was not supplied.",),
        ),
    )
    return DependencyCoverageSummary(
        areas=tuple(sorted(areas, key=lambda item: item.area_id))
    )


def _section_traceability(
    *,
    pack_id: str,
    limitations: Sequence[DependencyLimitation],
    finding_ids: Sequence[str] = (),
    manifest_ids: Sequence[str] = (),
    hotspot_ids: Sequence[str] = (),
    theme_ids: Sequence[str] = (),
    conclusions: Sequence[object] = (),
    recommendation_ids: Sequence[str] = (),
) -> DependencyTraceabilityIndex:
    edges: list[DependencyTraceabilityEdge] = [
        DependencyTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=DependencyTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=DependencyTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for limitation in limitations:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=limitation.limitation_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=limitation.limitation_id,
            )
        )
    for area_id in (
        "dependency_evidence_coverage",
        "dependency_rule_coverage",
        "enterprise_context_coverage",
    ):
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_COVERAGE.value,
                    source_id=SECTION_ID,
                    target_id=area_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_COVERAGE,
                source_id=SECTION_ID,
                target_id=area_id,
            )
        )
    for finding_id in finding_ids:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=finding_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=finding_id,
            )
        )
    for manifest_id in manifest_ids:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_MANIFEST.value,
                    source_id=SECTION_ID,
                    target_id=manifest_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_MANIFEST,
                source_id=SECTION_ID,
                target_id=manifest_id,
            )
        )
    for hotspot_id in hotspot_ids:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_HOTSPOT.value,
                    source_id=SECTION_ID,
                    target_id=hotspot_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_HOTSPOT,
                source_id=SECTION_ID,
                target_id=hotspot_id,
            )
        )
    for theme_id in theme_ids:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_THEME.value,
                    source_id=SECTION_ID,
                    target_id=theme_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_THEME,
                source_id=SECTION_ID,
                target_id=theme_id,
            )
        )
    for conclusion in conclusions:
        conclusion_id = getattr(conclusion, "conclusion_id", "")
        if not conclusion_id:
            continue
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=DependencyTraceabilityRelation.SECTION_TO_CONCLUSION.value,
                    source_id=SECTION_ID,
                    target_id=conclusion_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_CONCLUSION,
                source_id=SECTION_ID,
                target_id=conclusion_id,
            )
        )
        for theme_id in getattr(conclusion, "theme_ids", ())[:16]:
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=DependencyTraceabilityRelation.CONCLUSION_TO_THEME.value,
                        source_id=conclusion_id,
                        target_id=theme_id,
                    ),
                    relation=DependencyTraceabilityRelation.CONCLUSION_TO_THEME,
                    source_id=conclusion_id,
                    target_id=theme_id,
                )
            )
        for finding_id in getattr(conclusion, "finding_ids", ())[:32]:
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=(
                            DependencyTraceabilityRelation.CONCLUSION_TO_FINDING.value
                        ),
                        source_id=conclusion_id,
                        target_id=finding_id,
                    ),
                    relation=DependencyTraceabilityRelation.CONCLUSION_TO_FINDING,
                    source_id=conclusion_id,
                    target_id=finding_id,
                )
            )
        for hotspot_id in getattr(conclusion, "hotspot_ids", ())[:16]:
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=(
                            DependencyTraceabilityRelation.CONCLUSION_TO_HOTSPOT.value
                        ),
                        source_id=conclusion_id,
                        target_id=hotspot_id,
                    ),
                    relation=DependencyTraceabilityRelation.CONCLUSION_TO_HOTSPOT,
                    source_id=conclusion_id,
                    target_id=hotspot_id,
                )
            )
        for manifest_id in getattr(conclusion, "manifest_inventory_ids", ())[:16]:
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=(
                            DependencyTraceabilityRelation.CONCLUSION_TO_MANIFEST.value
                        ),
                        source_id=conclusion_id,
                        target_id=manifest_id,
                    ),
                    relation=DependencyTraceabilityRelation.CONCLUSION_TO_MANIFEST,
                    source_id=conclusion_id,
                    target_id=manifest_id,
                )
            )
        for diagnostic_id in getattr(conclusion, "diagnostic_ids", ())[:16]:
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=(
                            DependencyTraceabilityRelation.CONCLUSION_TO_DIAGNOSTIC.value
                        ),
                        source_id=conclusion_id,
                        target_id=diagnostic_id,
                    ),
                    relation=DependencyTraceabilityRelation.CONCLUSION_TO_DIAGNOSTIC,
                    source_id=conclusion_id,
                    target_id=diagnostic_id,
                )
            )
    for recommendation_id in recommendation_ids:
        edges.append(
            DependencyTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=(
                        DependencyTraceabilityRelation.SECTION_TO_RECOMMENDATION.value
                    ),
                    source_id=SECTION_ID,
                    target_id=recommendation_id,
                ),
                relation=DependencyTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                source_id=SECTION_ID,
                target_id=recommendation_id,
            )
        )
    # recommendation → conclusion edges from conclusions' recommendation_ids inverted
    for conclusion in conclusions:
        conclusion_id = getattr(conclusion, "conclusion_id", "")
        for recommendation_id in getattr(conclusion, "recommendation_ids", ()):
            edges.append(
                DependencyTraceabilityEdge(
                    edge_id=build_trace_edge_id(
                        relation=(
                            DependencyTraceabilityRelation.RECOMMENDATION_TO_CONCLUSION.value
                        ),
                        source_id=recommendation_id,
                        target_id=conclusion_id,
                    ),
                    relation=DependencyTraceabilityRelation.RECOMMENDATION_TO_CONCLUSION,
                    source_id=recommendation_id,
                    target_id=conclusion_id,
                )
            )
    return DependencyTraceabilityIndex(
        edges=tuple(sorted(edges, key=lambda item: item.edge_id))
    )


class DependencyAssessmentAssembler:
    """Build dependency assessment sections for foundation and hygiene findings."""

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "dependency_pack_disabled",
    ) -> DependencyAssessmentSection:
        limitations = _assessment_limitations(
            pack_enabled=False, evidence_enabled=False
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=False,
            section_enabled=True,
        )
        return DependencyAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=DependencyAssessmentStatus.DISABLED,
            repository_id=repository_id,
            dependency_pack_id=PACK_ID,
            dependency_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=DependencyExecutionSummary(),
            coverage=_coverage(
                pack_enabled=False, evidence_enabled=False, evidence=None
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(pack_id=PACK_ID, limitations=limitations),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={"assessment_milestone": "4.4.5"},
        )

    def assemble_not_requested(
        self,
        *,
        repository_id: str,
        reason: str = "dependency_section_not_requested",
    ) -> DependencyAssessmentSection:
        limitations = _assessment_limitations(
            pack_enabled=False, evidence_enabled=False
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=False,
            section_enabled=False,
        )
        return DependencyAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=DependencyAssessmentStatus.NOT_REQUESTED,
            repository_id=repository_id,
            dependency_pack_id=PACK_ID,
            dependency_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=DependencyExecutionSummary(),
            coverage=_coverage(
                pack_enabled=False, evidence_enabled=False, evidence=None
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(pack_id=PACK_ID, limitations=limitations),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={"assessment_milestone": "4.4.5"},
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_dependency_findings",
    ) -> DependencyAssessmentSection:
        """Succeeded empty section when pack is requested but no findings exist."""

        limitations = _assessment_limitations(
            pack_enabled=pack_enabled, evidence_enabled=False
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=pack_enabled,
            section_enabled=True,
        )
        status = (
            DependencyAssessmentStatus.SUCCEEDED
            if pack_enabled
            else DependencyAssessmentStatus.DISABLED
        )
        return DependencyAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=status,
            repository_id=repository_id,
            dependency_pack_id=PACK_ID,
            dependency_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=DependencyExecutionSummary(
                dependency_rules_planned=len(HYGIENE_RULE_IDS) if pack_enabled else 0,
                rules_executed=0,
                visible_finding_count=0,
            ),
            coverage=_coverage(
                pack_enabled=pack_enabled, evidence_enabled=False, evidence=None
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(pack_id=PACK_ID, limitations=limitations),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={"assessment_milestone": "4.4.5"},
        )

    def assemble_insufficient_evidence(
        self,
        *,
        repository_id: str,
        reason: str = "dependency_evidence_unavailable",
        evidence_enabled: bool = False,
    ) -> DependencyAssessmentSection:
        limitations = _assessment_limitations(
            pack_enabled=True, evidence_enabled=evidence_enabled
        )
        fingerprint = build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=True,
            section_enabled=True,
        )
        return DependencyAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE,
            repository_id=repository_id,
            dependency_pack_id=PACK_ID,
            dependency_pack_version=PACK_VERSION,
            evidence_pipeline="not_configured",
            configuration_fingerprint=fingerprint,
            execution_summary=DependencyExecutionSummary(
                dependency_rules_planned=len(HYGIENE_RULE_IDS),
            ),
            coverage=_coverage(
                pack_enabled=True,
                evidence_enabled=evidence_enabled,
                evidence=None,
            ),
            limitations=limitations,
            diagnostics=(reason,),
            traceability=_section_traceability(pack_id=PACK_ID, limitations=limitations),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={"assessment_milestone": "4.4.5"},
        )

    def assemble(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding],
        pack_enabled: bool,
        evidence_enabled: bool,
        include_findings: bool = True,
        include_coverage: bool = True,
        include_limitations: bool = True,
        include_traceability: bool = True,
        include_execution_summary: bool = True,
        include_synthesis: bool = True,
        dependency_evidence: AggregatedDependencyEvidence | None = None,
        evidence_pipeline: str = "dependency.manifest",
        evidence_fingerprint: str = "",
        configuration_payload: str = "",
        dependency_rules_planned: int = 5,
        rules_executed: int = 0,
        rules_matched: int = 0,
        rules_not_matched: int = 0,
        rules_not_applicable: int = 0,
        diagnostics: Sequence[str] = (),
    ) -> DependencyAssessmentSection:
        dep_findings = dependency_findings(findings)
        all_refs = build_finding_references(dep_findings) if include_findings else ()
        production_refs = tuple(
            item
            for item in all_refs
            if item.source_role is DependencySourceRole.PRODUCTION
        )
        primary_finding_ids = tuple(item.finding_id for item in production_refs)
        all_finding_ids = tuple(item.finding_id for item in all_refs)

        evidence_summary = build_evidence_summary(dependency_evidence)
        declaration_inventory = build_declaration_inventory(dependency_evidence)
        finding_inventory = build_finding_inventory(all_refs)
        manifest_inventory = build_manifest_inventory(
            evidence=dependency_evidence,
            finding_refs=all_refs,
        )
        aggregation_inventory = build_aggregation_inventory(dependency_evidence)
        hotspot_inventory = build_hotspot_inventory(
            manifest_inventory=manifest_inventory,
            finding_refs=all_refs,
        )
        diagnostics_summary = build_diagnostics_summary(
            dependency_evidence,
            extra_diagnostics=diagnostics,
        )
        prod_parse_failures, test_parse_failures, unknown_parse_failures = (
            parse_failure_counts(dependency_evidence)
        )

        status = _resolve_status(
            pack_enabled=pack_enabled,
            evidence_enabled=evidence_enabled,
            evidence=dependency_evidence,
            production_parse_failures=prod_parse_failures,
        )

        limitations = (
            _assessment_limitations(
                pack_enabled=pack_enabled, evidence_enabled=evidence_enabled
            )
            if include_limitations
            else ()
        )
        coverage = (
            _coverage(
                pack_enabled=pack_enabled,
                evidence_enabled=evidence_enabled,
                evidence=dependency_evidence,
            )
            if include_coverage
            else DependencyCoverageSummary()
        )
        execution_summary = (
            DependencyExecutionSummary(
                providers_planned=1 if evidence_enabled else 0,
                providers_executed=1 if dependency_evidence is not None else 0,
                provider_failures=(
                    1
                    if dependency_evidence is not None
                    and dependency_evidence.status is DependencyParseStatus.FAILED
                    else 0
                ),
                dependency_rules_planned=dependency_rules_planned,
                rules_executed=rules_executed,
                rules_matched=rules_matched,
                rules_not_matched=rules_not_matched,
                rules_not_applicable=rules_not_applicable,
                visible_finding_count=len(primary_finding_ids),
                production_finding_count=finding_inventory.production.finding_count,
                test_finding_count=finding_inventory.test.finding_count,
                unknown_finding_count=finding_inventory.unknown.finding_count,
                total_finding_count=finding_inventory.total_finding_count,
                production_parse_failures=prod_parse_failures,
                test_fixture_parse_failures=test_parse_failures,
                unknown_parse_failures=unknown_parse_failures,
            )
            if include_execution_summary
            else DependencyExecutionSummary()
        )
        fingerprint = configuration_payload or build_empty_section_fingerprint(
            repository_id=repository_id,
            pack_enabled=pack_enabled,
            section_enabled=True,
        )
        diagnostic_codes = tuple(
            sorted({item.diagnostic_code for item in diagnostics_summary.records})
        )
        synthesis = synthesize_dependency(
            repository_id=repository_id,
            pack_enabled=pack_enabled,
            section_status=status,
            finding_summaries=all_refs,
            hotspot_inventory=hotspot_inventory,
            manifest_inventory=manifest_inventory,
            declaration_inventory=declaration_inventory,
            aggregation_inventory=aggregation_inventory,
            evidence_summary=evidence_summary,
            diagnostics_summary=diagnostics_summary,
            include_synthesis=include_synthesis,
        )
        if include_execution_summary:
            execution_summary = execution_summary.model_copy(
                update={
                    "theme_count": len(synthesis.theme_ids),
                    "conclusion_count": len(synthesis.conclusion_ids),
                    "recommendation_count": len(synthesis.recommendation_ids),
                }
            )
        merged_diagnostics = tuple(
            sorted(
                {
                    *(str(item).strip() for item in diagnostics if str(item).strip()),
                    *diagnostic_codes,
                    *synthesis.diagnostics,
                    *(
                        (f"evidence_status:{dependency_evidence.status.value}",)
                        if dependency_evidence is not None
                        and dependency_evidence.status
                        is DependencyParseStatus.PARTIALLY_SUCCEEDED
                        else ()
                    ),
                }
            )
        )
        all_hotspot_ids = tuple(
            item.hotspot_id
            for item in (
                *hotspot_inventory.production,
                *hotspot_inventory.test,
                *hotspot_inventory.unknown,
            )
        )
        return DependencyAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            status=status,
            repository_id=repository_id,
            dependency_pack_id=PACK_ID,
            dependency_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline,
            evidence_fingerprint=evidence_fingerprint
            or (
                dependency_evidence.evidence_fingerprint
                if dependency_evidence is not None
                else ""
            ),
            configuration_fingerprint=fingerprint,
            execution_summary=execution_summary,
            coverage=coverage,
            evidence_summary=evidence_summary,
            declaration_inventory=declaration_inventory,
            finding_inventory=finding_inventory,
            manifest_inventory=manifest_inventory,
            aggregation_inventory=aggregation_inventory,
            hotspot_inventory=hotspot_inventory,
            diagnostics_summary=diagnostics_summary,
            finding_ids=primary_finding_ids if include_findings else (),
            finding_summaries=production_refs if include_findings else (),
            all_finding_ids=all_finding_ids if include_findings else (),
            all_finding_summaries=all_refs if include_findings else (),
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
            traceability=(
                _section_traceability(
                    pack_id=PACK_ID,
                    limitations=limitations,
                    finding_ids=all_finding_ids if include_traceability else (),
                    manifest_ids=tuple(
                        item.manifest_inventory_id
                        for item in manifest_inventory.entries
                    )
                    if include_traceability
                    else (),
                    hotspot_ids=all_hotspot_ids if include_traceability else (),
                    theme_ids=synthesis.theme_ids if include_traceability else (),
                    conclusions=synthesis.conclusions if include_traceability else (),
                    recommendation_ids=(
                        synthesis.recommendation_ids if include_traceability else ()
                    ),
                )
                if include_traceability
                else DependencyTraceabilityIndex()
            ),
            enterprise_context_used=False,
            business_impact="unknown",
            metadata={
                "assessment_milestone": "4.4.5",
                "synthesis_version": synthesis.synthesis_version,
                "hotspot_ordering": (
                    "presentation_only:"
                    "production>test>unknown,"
                    "highest_severity,distinct_rules,finding_count,manifest_path"
                ),
                "manifest_finding_concentration_threshold": "0.40",
            },
        )


def _resolve_status(
    *,
    pack_enabled: bool,
    evidence_enabled: bool,
    evidence: AggregatedDependencyEvidence | None,
    production_parse_failures: int,
) -> DependencyAssessmentStatus:
    """Resolve assessment status from production evidence usability.

    Test/fixture parse failures and unsupported-but-diagnosed constructs do not
    force partially_succeeded when production evidence remains usable.
    Evidence-level partial status is preserved in coverage and diagnostics.
    """

    if not pack_enabled:
        return DependencyAssessmentStatus.DISABLED
    if not evidence_enabled or evidence is None:
        return DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE
    if evidence.status is DependencyParseStatus.FAILED:
        return DependencyAssessmentStatus.FAILED
    if evidence.coverage.manifests_supported == 0:
        return DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE
    if production_parse_failures > 0:
        return DependencyAssessmentStatus.PARTIALLY_SUCCEEDED
    if not production_manifests_usable(evidence):
        # Supported manifests may be test/fixture-only; inventory remains usable.
        return DependencyAssessmentStatus.SUCCEEDED
    return DependencyAssessmentStatus.SUCCEEDED

