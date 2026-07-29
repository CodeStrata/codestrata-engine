"""Test assessment assembler (Phase 4.6.5).

Projects Test Hygiene findings, inventories, and deterministic synthesis into
TestAssessmentSection. No report projection.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.testing.helpers import evidence_is_usable
from codestrata.application.testing.assessment.inventory import (
    TestingRuleExecutionFact,
    build_confidence_inventory,
    build_finding_inventory,
    build_rule_inventory,
    build_severity_inventory,
    coerce_execution_facts,
    findings_by_rule_counts,
)
from codestrata.application.testing.synthesis import synthesize_testing
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
)
from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.enums import (
    TestAssessmentStatus,
    TestCoverageAreaStatus,
    TestCoverageMaturity,
    TestLimitationCategory,
    TestTraceabilityRelation,
)
from codestrata.domain.testing.assessment.identifiers import (
    MAX_TRACEABILITY_ENTRIES,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_configuration_fingerprint,
    build_empty_section_fingerprint,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.testing.assessment.models import (
    TestAssessmentSection,
    TestConfidenceInventory,
    TestCoverageArea,
    TestCoverageSummary,
    TestExecutionSummary,
    TestFindingInventory,
    TestLimitation,
    TestRuleInventory,
    TestSeverityInventory,
    TestTraceabilityEdge,
    TestTraceabilityIndex,
)
from codestrata.domain.testing.ids import HYGIENE_RULE_IDS, PACK_ID, PACK_VERSION
from codestrata.domain.testing.synthesis.enums import TestSynthesisStatus
from codestrata.domain.testing.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.testing.synthesis.models import TestingSynthesisResult

_MILESTONE = "4.6.5"
_ZERO_FINDINGS_SUMMARY = (
    "No Test Hygiene findings were produced by the enabled rule pack from the "
    "available repository evidence."
)


def _limitation(
    *,
    category: TestLimitationCategory,
    summary: str,
    affected_capability: str,
    importance: str = "contextual",
) -> TestLimitation:
    return TestLimitation(
        limitation_id=build_limitation_id(category=category.value, summary=summary),
        category=category,
        summary=summary,
        affected_capability=affected_capability,
        importance=importance,
    )


def _foundation_limitations(*, pack_enabled: bool) -> tuple[TestLimitation, ...]:
    items = [
        _limitation(
            category=TestLimitationCategory.FOUNDATION_ONLY,
            summary=("Test Intelligence analysis is not implemented in this phase."),
            affected_capability="testing_assessment",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.TEST_DISCOVERY_NOT_IMPLEMENTED,
            summary="Test files are not discovered or classified.",
            affected_capability="test_discovery",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.FRAMEWORK_DETECTION_NOT_IMPLEMENTED,
            summary="Test frameworks are not detected.",
            affected_capability="framework_detection",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.BUILD_INSPECTION_NOT_IMPLEMENTED,
            summary=("Build and dependency configuration is not inspected for testing tools."),
            affected_capability="build_inspection",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.TEST_EXECUTION_NOT_PERFORMED,
            summary=("Test execution is not performed. Test pass/fail status is not evaluated."),
            affected_capability="test_execution",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.COVERAGE_NOT_MEASURED,
            summary="Runtime code coverage is not measured.",
            affected_capability="coverage",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.DISABLED_TEST_DETECTION_NOT_IMPLEMENTED,
            summary=("Disabled, ignored, or quarantined tests are not detected."),
            affected_capability="disabled_tests",
        ),
        _limitation(
            category=TestLimitationCategory.TEST_TO_SOURCE_MAPPING_NOT_IMPLEMENTED,
            summary=("Test-to-production-code relationships are not evaluated."),
            affected_capability="test_to_source_mapping",
        ),
        _limitation(
            category=TestLimitationCategory.CI_INSPECTION_NOT_IMPLEMENTED,
            summary="CI test execution is not inspected.",
            affected_capability="ci_inspection",
        ),
        _limitation(
            category=TestLimitationCategory.MUTATION_TESTING_NOT_EVALUATED,
            summary="Mutation testing is not evaluated.",
            affected_capability="mutation_testing",
        ),
        _limitation(
            category=TestLimitationCategory.NO_TEST_QUALITY_CONCLUSION,
            summary=("No conclusion about test quality or release readiness can be drawn."),
            affected_capability="test_quality",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.RULES_NOT_IMPLEMENTED,
            summary=(
                "Test Intelligence rules are not registered yet; no testing rules ran."
                if pack_enabled
                else "Test rule pack is disabled; no testing rules ran."
            ),
            affected_capability="testing_rules",
            importance="critical",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _hygiene_limitations(*, pack_enabled: bool) -> tuple[TestLimitation, ...]:
    items = [
        _limitation(
            category=TestLimitationCategory.TEST_EXECUTION_NOT_PERFORMED,
            summary=("Test execution is not performed. Test pass/fail status is not evaluated."),
            affected_capability="test_execution",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.COVERAGE_NOT_MEASURED,
            summary=(
                "Runtime code coverage percentages are not measured; only "
                "repository-observable coverage configuration facts are used."
            ),
            affected_capability="coverage",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.TEST_TO_SOURCE_MAPPING_NOT_IMPLEMENTED,
            summary=("Test-to-production-code relationships are not evaluated."),
            affected_capability="test_to_source_mapping",
        ),
        _limitation(
            category=TestLimitationCategory.MUTATION_TESTING_NOT_EVALUATED,
            summary="Mutation testing is not evaluated.",
            affected_capability="mutation_testing",
        ),
        _limitation(
            category=TestLimitationCategory.NO_TEST_QUALITY_CONCLUSION,
            summary=(
                "Test Hygiene findings are repository-local hygiene signals "
                "only. Zero findings does not mean the repository is well "
                "tested or release ready."
            ),
            affected_capability="test_quality",
            importance="critical",
        ),
        _limitation(
            category=TestLimitationCategory.OTHER,
            summary=(
                "Test Hygiene rules consume AggregatedRepositoryTestingEvidence "
                "only and never re-read repository files."
                if pack_enabled
                else "Test rule pack is disabled; no testing rules ran."
            ),
            affected_capability="testing_rules",
            importance="critical",
        ),
    ]
    return tuple(sorted(items, key=lambda item: item.limitation_id))


def _coverage(
    *,
    pack_enabled: bool,
    evidence_available: bool = False,
    findings_count: int = 0,
    rules_executed: int = 0,
) -> TestCoverageSummary:
    planned = len(HYGIENE_RULE_IDS) if pack_enabled else 0
    areas = [
        TestCoverageArea(
            area_id="testing_capability_requested",
            status=TestCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=TestCoverageMaturity.MEDIUM if pack_enabled else TestCoverageMaturity.LOW,
            limitations=("hygiene_rules_only",) if pack_enabled else ("foundation_only",),
        ),
        TestCoverageArea(
            area_id="testing_rules_enabled",
            status=(
                TestCoverageAreaStatus.MEASURED
                if pack_enabled
                else TestCoverageAreaStatus.NOT_APPLICABLE
            ),
            numerator=rules_executed if pack_enabled else 0,
            denominator=planned,
            ratio=((rules_executed / planned) if pack_enabled and planned else None),
            maturity=TestCoverageMaturity.MEDIUM if pack_enabled else TestCoverageMaturity.LOW,
            limitations=() if pack_enabled else ("pack_disabled",),
        ),
        TestCoverageArea(
            area_id="testing_evidence_availability",
            status=(
                TestCoverageAreaStatus.MEASURED
                if evidence_available
                else TestCoverageAreaStatus.UNSUPPORTED
            ),
            numerator=1 if evidence_available else 0,
            denominator=1,
            ratio=1.0 if evidence_available else 0.0,
            maturity=(
                TestCoverageMaturity.MEDIUM if evidence_available else TestCoverageMaturity.LOW
            ),
            limitations=(
                () if evidence_available else ("repository_testing_evidence_unavailable",)
            ),
        ),
        TestCoverageArea(
            area_id="testing_findings_evaluated",
            status=TestCoverageAreaStatus.MEASURED,
            numerator=findings_count,
            denominator=findings_count,
            ratio=1.0 if findings_count else None,
            maturity=TestCoverageMaturity.MEDIUM if pack_enabled else TestCoverageMaturity.LOW,
            limitations=("hygiene_findings_only",) if pack_enabled else ("analytically_empty",),
        ),
        TestCoverageArea(
            area_id="testing_inventory_complete",
            status=TestCoverageAreaStatus.MEASURED,
            numerator=1 if pack_enabled else 0,
            denominator=1,
            ratio=1.0 if pack_enabled else 0.0,
            maturity=TestCoverageMaturity.MEDIUM if pack_enabled else TestCoverageMaturity.LOW,
            limitations=("inventory_only",) if pack_enabled else ("foundation_only",),
        ),
    ]
    return TestCoverageSummary(areas=tuple(sorted(areas, key=lambda item: item.area_id)))


def _lifecycle_traceability(
    *,
    pack_id: str,
    limitations: tuple[TestLimitation, ...],
    finding_ids: tuple[str, ...] = (),
    theme_ids: tuple[str, ...] = (),
    conclusion_ids: tuple[str, ...] = (),
    recommendation_ids: tuple[str, ...] = (),
) -> TestTraceabilityIndex:
    edges: list[TestTraceabilityEdge] = [
        TestTraceabilityEdge(
            edge_id=build_trace_edge_id(
                relation=TestTraceabilityRelation.SECTION_TO_PACK.value,
                source_id=SECTION_ID,
                target_id=pack_id,
            ),
            relation=TestTraceabilityRelation.SECTION_TO_PACK,
            source_id=SECTION_ID,
            target_id=pack_id,
        )
    ]
    for finding_id in finding_ids:
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_FINDING.value,
                    source_id=SECTION_ID,
                    target_id=finding_id,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_FINDING,
                source_id=SECTION_ID,
                target_id=finding_id,
            )
        )
    for theme_id in theme_ids:
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_THEME.value,
                    source_id=SECTION_ID,
                    target_id=theme_id,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_THEME,
                source_id=SECTION_ID,
                target_id=theme_id,
            )
        )
    for conclusion_id in conclusion_ids:
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_CONCLUSION.value,
                    source_id=SECTION_ID,
                    target_id=conclusion_id,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_CONCLUSION,
                source_id=SECTION_ID,
                target_id=conclusion_id,
            )
        )
    for recommendation_id in recommendation_ids:
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_RECOMMENDATION.value,
                    source_id=SECTION_ID,
                    target_id=recommendation_id,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_RECOMMENDATION,
                source_id=SECTION_ID,
                target_id=recommendation_id,
            )
        )
    for item in limitations:
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_LIMITATION.value,
                    source_id=SECTION_ID,
                    target_id=item.limitation_id,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_LIMITATION,
                source_id=SECTION_ID,
                target_id=item.limitation_id,
            )
        )
    for area in (
        "testing_capability_requested",
        "testing_rules_enabled",
        "testing_evidence_availability",
        "testing_findings_evaluated",
        "testing_inventory_complete",
    ):
        edges.append(
            TestTraceabilityEdge(
                edge_id=build_trace_edge_id(
                    relation=TestTraceabilityRelation.SECTION_TO_COVERAGE.value,
                    source_id=SECTION_ID,
                    target_id=area,
                ),
                relation=TestTraceabilityRelation.SECTION_TO_COVERAGE,
                source_id=SECTION_ID,
                target_id=area,
            )
        )
    ordered = tuple(sorted(edges, key=lambda item: item.edge_id))
    return TestTraceabilityIndex(edges=ordered[:MAX_TRACEABILITY_ENTRIES])


def _empty_inventories(
    *,
    pack_enabled: bool,
) -> tuple[
    TestFindingInventory,
    TestRuleInventory,
    TestSeverityInventory,
    TestConfidenceInventory,
]:
    rule_inventory = build_rule_inventory(
        findings=(),
        execution_facts=(),
        pack_enabled=pack_enabled,
    )
    return (
        TestFindingInventory(),
        rule_inventory,
        TestSeverityInventory(),
        TestConfidenceInventory(),
    )


def _build_section(
    *,
    repository_id: str,
    status: TestAssessmentStatus,
    pack_enabled: bool,
    section_enabled: bool,
    reason: str,
    rules_planned: int = 0,
    configuration_fingerprint: str | None = None,
) -> TestAssessmentSection:
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
    ) = _empty_inventories(pack_enabled=pack_enabled)
    return TestAssessmentSection(
        section_id=SECTION_ID,
        section_version=SECTION_SCHEMA_VERSION,
        assessment_id=assessment_id,
        status=status,
        capability="testing",
        repository_id=repository_id,
        testing_pack_id=PACK_ID,
        testing_pack_version=PACK_VERSION,
        evidence_pipeline="not_configured",
        configuration_fingerprint=fingerprint,
        execution_summary=TestExecutionSummary(
            testing_rules_planned=rules_planned,
            rules_executed=0,
            total_finding_count=0,
            visible_finding_count=0,
            pack_id=PACK_ID,
            pack_version=PACK_VERSION,
            pack_enabled=pack_enabled,
        ),
        coverage=_coverage(pack_enabled=pack_enabled),
        finding_inventory=finding_inventory,
        rule_inventory=rule_inventory,
        severity_inventory=severity_inventory,
        confidence_inventory=confidence_inventory,
        finding_ids=(),
        all_finding_ids=(),
        findings=(),
        limitations=limitations,
        diagnostics=(reason,),
        traceability=_lifecycle_traceability(pack_id=PACK_ID, limitations=limitations),
        metadata={
            "assessment_milestone": "4.6.1",
            "reason": reason,
            "summary": (
                "Analytically empty Test Intelligence foundation section. "
                "Does not establish that the repository is well tested or "
                "release ready."
            ),
        },
    )


class TestAssessmentAssembler:
    """Assemble Test assessment sections (foundation + hygiene + inventory)."""

    __test__ = False

    def assemble_disabled(
        self,
        *,
        repository_id: str,
        reason: str = "testing_pack_disabled",
    ) -> TestAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.DISABLED,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
        )

    def assemble_not_requested(
        self,
        *,
        repository_id: str,
        reason: str = "testing_section_not_requested",
    ) -> TestAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.NOT_REQUESTED,
            pack_enabled=False,
            section_enabled=False,
            reason=reason,
        )

    def assemble_empty(
        self,
        *,
        repository_id: str,
        pack_enabled: bool = True,
        reason: str = "no_testing_rules_registered",
    ) -> TestAssessmentSection:
        status = TestAssessmentStatus.SUCCEEDED if pack_enabled else TestAssessmentStatus.DISABLED
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
        reason: str = "testing_evidence_unavailable",
        configuration_payload: str = "",
    ) -> TestAssessmentSection:
        fingerprint = build_configuration_fingerprint(
            configuration_payload or f"insufficient|{repository_id}"
        )
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.INSUFFICIENT_EVIDENCE,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=0,
            configuration_fingerprint=fingerprint,
        )

    def assemble_partially_succeeded(
        self,
        *,
        repository_id: str,
        reason: str = "testing_assessment_partial",
    ) -> TestAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.PARTIALLY_SUCCEEDED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=0,
        )

    def assemble_failed(
        self,
        *,
        repository_id: str,
        reason: str = "testing_assessment_failed",
    ) -> TestAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.FAILED,
            pack_enabled=True,
            section_enabled=True,
            reason=reason,
            rules_planned=0,
        )

    def assemble_not_applicable(
        self,
        *,
        repository_id: str,
        reason: str = "testing_assessment_not_applicable",
    ) -> TestAssessmentSection:
        return _build_section(
            repository_id=repository_id,
            status=TestAssessmentStatus.NOT_APPLICABLE,
            pack_enabled=False,
            section_enabled=True,
            reason=reason,
        )

    def assemble(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding] = (),
        evidence: AggregatedRepositoryTestingEvidence | None = None,
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
    ) -> TestAssessmentSection:
        """Assemble a Test Hygiene assessment section with inventories and synthesis."""

        if not pack_enabled:
            return self.assemble_disabled(repository_id=repository_id)

        evidence_usable = evidence_is_usable(evidence)
        if evidence is None or not evidence_usable:
            return self.assemble_insufficient_evidence(
                repository_id=repository_id,
                reason="repository_testing_evidence_unavailable",
                configuration_payload=configuration_payload,
            )

        ordered_findings = tuple(
            sorted(findings, key=lambda item: (item.rule_id, item.id, item.title))
        )
        inventory_findings = ordered_findings if include_findings else ()
        finding_ids = tuple(item.id for item in inventory_findings)
        planned = rules_planned if rules_planned is not None else len(HYGIENE_RULE_IDS)
        execution_facts = coerce_execution_facts(rule_execution_facts)
        if not execution_facts and rules_executed:
            execution_facts = tuple(
                TestingRuleExecutionFact(
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
        status = TestAssessmentStatus.SUCCEEDED
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
                f"Test Hygiene pack produced {len(finding_ids)} finding"
                f"{'' if len(finding_ids) == 1 else 's'} from repository-testing "
                "evidence."
            )
        )

        synthesis = TestingSynthesisResult()
        synthesis_diagnostics: tuple[str, ...] = ()
        try:
            synthesis = synthesize_testing(
                repository_id=repository_id,
                pack_enabled=True,
                section_status=status,
                findings=inventory_findings,
                finding_inventory=finding_inventory,
                rule_inventory=rule_inventory,
                limitations=limitations,
                evidence_status=(evidence.status.value if evidence is not None else ""),
                include_synthesis=include_synthesis,
            )
            synthesis_diagnostics = synthesis.diagnostics
        except Exception as error:  # noqa: BLE001 - isolate synthesis failures
            synthesis = TestingSynthesisResult(
                status=TestSynthesisStatus.FAILED,
                synthesis_version=SYNTHESIS_VERSION,
                diagnostics=(f"synthesis_failed:{type(error).__name__}",),
            )
            synthesis_diagnostics = synthesis.diagnostics

        execution = (
            TestExecutionSummary(
                testing_rules_planned=planned,
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
            else TestExecutionSummary()
        )
        coverage = (
            _coverage(
                pack_enabled=True,
                evidence_available=True,
                findings_count=len(finding_ids),
                rules_executed=executed,
            )
            if include_coverage
            else TestCoverageSummary()
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
            else TestTraceabilityIndex()
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
        return TestAssessmentSection(
            section_id=SECTION_ID,
            section_version=SECTION_SCHEMA_VERSION,
            assessment_id=assessment_id,
            status=status,
            capability="testing",
            repository_id=repository_id,
            testing_pack_id=PACK_ID,
            testing_pack_version=PACK_VERSION,
            evidence_pipeline=evidence_pipeline or "repository_testing",
            evidence_fingerprint=evidence_fingerprint
            or (evidence.evidence_fingerprint if evidence is not None else ""),
            configuration_fingerprint=fingerprint,
            execution_summary=execution,
            coverage=coverage,
            finding_inventory=finding_inventory,
            rule_inventory=rule_inventory,
            severity_inventory=severity_inventory,
            confidence_inventory=confidence_inventory,
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
                "evidence_status": evidence.status.value,
                "synthesis_version": SYNTHESIS_VERSION,
                "overall_posture_summary": synthesis.overall_posture_summary,
            },
        )
