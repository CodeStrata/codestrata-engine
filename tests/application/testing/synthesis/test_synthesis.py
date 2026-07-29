"""Test synthesis tests (Phase 4.6.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.application.testing.assessment.artifacts import (
    testing_assessment_payload as build_testing_assessment_payload,
)
from codestrata.application.testing.assessment.artifacts import (
    write_testing_assessment_artifact,
)
from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.application.testing.assessment.inventory import execution_facts_from_status_map
from codestrata.application.testing.synthesis import synthesize_testing
from codestrata.config import load_settings
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    RepositoryTestingParseStatus,
    TestFileRole,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    MarkerFactEvidence,
    RepositoryTestingEvidenceCoverage,
    TestFileCandidateEvidence,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.enums import TestAssessmentStatus
from codestrata.domain.testing.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.testing.assessment.models import (
    TestFindingInventory,
    TestRuleInventory,
)
from codestrata.domain.testing.ids import (
    HYGIENE_RULE_IDS,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)
from codestrata.domain.testing.synthesis.enums import (
    TestConclusionKind,
    TestRecommendationKind,
    TestSynthesisStatus,
    TestThemeKind,
)
from codestrata.domain.testing.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _evidence() -> AggregatedRepositoryTestingEvidence:
    return AggregatedRepositoryTestingEvidence(
        repository_id="repo:fixture",
        status=RepositoryTestingParseStatus.SUCCEEDED,
        file_candidates=(
            TestFileCandidateEvidence(
                evidence_id="cand:tests/a.py",
                path="tests/a.py",
                role=TestFileRole.UNIT_TEST,
                provenance=_prov(),
            ),
        ),
        marker_facts=(
            MarkerFactEvidence(
                evidence_id="marker:tests/a.py:disabled",
                path="tests/a.py",
                marker_type=TestMarkerType.DISABLED,
                marker_text="@Disabled",
                provenance=_prov(),
            ),
        ),
        coverage=RepositoryTestingEvidenceCoverage(
            candidate_files_inspected=1,
            marker_facts=1,
            languages_represented=("python",),
        ),
        evidence_fingerprint="syn-fp-1",
    )


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    confidence: str = "high",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.TESTING,
        metadata={"confidence": confidence},
    )


def _facts_all_matched(matched: set[str]) -> tuple:
    status = {
        rule_id: ("matched" if rule_id in matched else "not_matched")
        for rule_id in HYGIENE_RULE_IDS
    }
    return execution_facts_from_status_map(status)


def test_schema_and_synthesis_gate(tmp_path: Path) -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [rules]
        enabled = true
        [rules.testing]
        enabled = true
        [assessment.sections.testing]
        enabled = true
        include_synthesis = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.assessment.sections.testing.include_synthesis is False
    section = TestAssessmentAssembler().assemble(
        repository_id="repo:gate",
        findings=(),
        evidence=_evidence(),
        include_synthesis=False,
        rules_executed=4,
        rule_execution_facts=_facts_all_matched(set()),
        evidence_fingerprint="syn-fp-1",
    )
    assert section.section_version == "1.2.0"
    assert section.synthesis.status is TestSynthesisStatus.NOT_REQUESTED
    assert section.metadata.get("assessment_milestone") == "4.6.5"
    assert section.metadata.get("synthesis_version") == SYNTHESIS_VERSION


def test_zero_findings_neutral_posture() -> None:
    inventory = TestFindingInventory()
    rules = TestRuleInventory(
        rules_planned=4,
        rules_executed=4,
        rules_matched=0,
        rules_not_matched=4,
    )
    result = synthesize_testing(
        repository_id="repo:empty",
        pack_enabled=True,
        section_status=TestAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=inventory,
        rule_inventory=rules,
        evidence_status="succeeded",
    )
    assert result.status is TestSynthesisStatus.EMPTY
    kinds = {item.kind for item in result.themes}
    assert TestThemeKind.TESTING_HYGIENE_LANDSCAPE in kinds
    assert TestThemeKind.RULE_EXECUTION_COVERAGE in kinds
    assert TestThemeKind.NO_HYGIENE_FINDINGS in kinds
    assert TestThemeKind.DISABLED_OR_SKIPPED_TESTS not in kinds
    assert result.overall_posture_summary
    joined = " ".join(
        [
            result.overall_posture_summary,
            *(item.summary for item in result.conclusions),
        ]
    ).lower()
    assert "well tested" not in joined or "does not" in joined
    assert "testing passed" not in joined
    assert "release ready" not in joined or "does not" in joined


def test_each_supported_theme() -> None:
    cases = [
        (
            RULE_DISABLED_OR_SKIPPED,
            TestThemeKind.DISABLED_OR_SKIPPED_TESTS,
            TestConclusionKind.DISABLED_OR_SKIPPED_TESTS_OBSERVED,
            TestRecommendationKind.REVIEW_DISABLED_OR_SKIPPED_TESTS,
        ),
        (
            RULE_UNCONFIRMED_CANDIDATES,
            TestThemeKind.TEST_DISCOVERY_CONFIDENCE,
            TestConclusionKind.TEST_DISCOVERY_UNCERTAINTY_OBSERVED,
            TestRecommendationKind.IMPROVE_TEST_DISCOVERY_SIGNALING,
        ),
        (
            RULE_DECLARED_WITHOUT_OBSERVATION,
            TestThemeKind.FRAMEWORK_DECLARATION_CONSISTENCY,
            TestConclusionKind.FRAMEWORK_DECLARATION_GAP_OBSERVED,
            TestRecommendationKind.ALIGN_FRAMEWORK_DECLARATION_AND_OBSERVATION,
        ),
        (
            RULE_COVERAGE_WITHOUT_CI_INVOCATION,
            TestThemeKind.COVERAGE_AND_CI_ALIGNMENT,
            TestConclusionKind.COVERAGE_WITHOUT_CI_OBSERVED,
            TestRecommendationKind.ALIGN_COVERAGE_CONFIG_WITH_CI,
        ),
    ]
    for rule_id, theme_kind, conclusion_kind, recommendation_kind in cases:
        finding = _finding(rule_id=rule_id, finding_id=f"f-{rule_id}")
        result = synthesize_testing(
            repository_id="repo:themes",
            pack_enabled=True,
            section_status=TestAssessmentStatus.SUCCEEDED,
            findings=(finding,),
            finding_inventory=TestFindingInventory(
                finding_ids=(finding.id,),
                finding_count=1,
                rule_counts={rule_id: 1},
            ),
            rule_inventory=TestRuleInventory(
                rules_planned=4,
                rules_executed=4,
                rules_matched=1,
                rules_not_matched=3,
            ),
        )
        assert result.status is TestSynthesisStatus.SUCCEEDED
        assert theme_kind in {item.kind for item in result.themes}
        assert conclusion_kind in {item.kind for item in result.conclusions}
        assert recommendation_kind in {item.kind for item in result.recommendations}
        rec = next(item for item in result.recommendations if item.kind is recommendation_kind)
        assert finding.id in rec.finding_ids
        assert rule_id in rec.rule_ids
        assert rec.conclusion_ids


def test_mixed_findings_and_traceability(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-001"),
        _finding(
            rule_id=RULE_UNCONFIRMED_CANDIDATES,
            finding_id="f-002",
            severity=FindingSeverity.INFORMATIONAL,
            confidence="medium",
        ),
    )
    section = TestAssessmentAssembler().assemble(
        repository_id="repo:mixed",
        findings=findings,
        evidence=_evidence(),
        rules_executed=4,
        rules_matched=2,
        rules_not_matched=2,
        rule_execution_facts=_facts_all_matched(
            {RULE_DISABLED_OR_SKIPPED, RULE_UNCONFIRMED_CANDIDATES}
        ),
        evidence_fingerprint="syn-fp-1",
        configuration_payload="mixed-config",
    )
    assert section.synthesis.status is TestSynthesisStatus.SUCCEEDED
    theme_kinds = {item.kind for item in section.themes}
    assert TestThemeKind.DISABLED_OR_SKIPPED_TESTS in theme_kinds
    assert TestThemeKind.TEST_DISCOVERY_CONFIDENCE in theme_kinds
    assert TestThemeKind.FRAMEWORK_DECLARATION_CONSISTENCY not in theme_kinds
    assert TestThemeKind.COVERAGE_AND_CI_ALIGNMENT not in theme_kinds
    assert section.execution_summary.theme_count == len(section.themes)
    assert section.execution_summary.conclusion_count == len(section.conclusions)
    assert section.execution_summary.recommendation_count == len(section.recommendations)
    for recommendation in section.recommendations:
        assert recommendation.conclusion_ids
        if recommendation.kind in {
            TestRecommendationKind.REVIEW_DISABLED_OR_SKIPPED_TESTS,
            TestRecommendationKind.IMPROVE_TEST_DISCOVERY_SIGNALING,
            TestRecommendationKind.ALIGN_FRAMEWORK_DECLARATION_AND_OBSERVATION,
            TestRecommendationKind.ALIGN_COVERAGE_CONFIG_WITH_CI,
        }:
            assert recommendation.finding_ids
            assert recommendation.rule_ids
    body = dumps_stable_json(build_testing_assessment_payload(section))
    assert '"themes"' in body
    assert '"conclusions"' in body
    assert '"recommendations"' in body
    assert '"overall_posture_summary"' in body
    write_testing_assessment_artifact(section, tmp_path)
    assert (tmp_path / "testing-assessment.json").read_text(encoding="utf-8") == body


def test_deterministic_ordering_and_ids() -> None:
    findings = (
        _finding(rule_id=RULE_UNCONFIRMED_CANDIDATES, finding_id="f-b"),
        _finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-a"),
    )
    left = synthesize_testing(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=TestAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=TestFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=TestRuleInventory(
            rules_planned=4,
            rules_executed=4,
            rules_matched=2,
            rules_not_matched=2,
        ),
    )
    right = synthesize_testing(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=TestAssessmentStatus.SUCCEEDED,
        findings=tuple(reversed(findings)),
        finding_inventory=TestFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=TestRuleInventory(
            rules_planned=4,
            rules_executed=4,
            rules_matched=2,
            rules_not_matched=2,
        ),
    )
    assert left.model_dump_json() == right.model_dump_json()
    assert left.theme_ids == tuple(item.theme_id for item in left.themes)
    assert left.conclusion_ids == tuple(item.conclusion_id for item in left.conclusions)
    assert all(item.startswith("test-theme:") for item in left.theme_ids)
    assert all(item.startswith("test-conclusion:") for item in left.conclusion_ids)
    assert all(item.startswith("test-recommendation:") for item in left.recommendation_ids)


def test_disabled_and_insufficient_synthesis() -> None:
    disabled = synthesize_testing(
        repository_id="repo:x",
        pack_enabled=False,
        section_status=TestAssessmentStatus.DISABLED,
    )
    assert disabled.status is TestSynthesisStatus.DISABLED
    insufficient = synthesize_testing(
        repository_id="repo:x",
        pack_enabled=True,
        section_status=TestAssessmentStatus.INSUFFICIENT_EVIDENCE,
    )
    assert insufficient.status is TestSynthesisStatus.INSUFFICIENT_EVIDENCE


def test_synthesis_failure_isolation() -> None:
    with patch(
        "codestrata.application.testing.assessment.assembler.synthesize_testing",
        side_effect=RuntimeError("boom"),
    ):
        section = TestAssessmentAssembler().assemble(
            repository_id="repo:fail",
            findings=(),
            evidence=_evidence(),
            rules_executed=4,
            rule_execution_facts=_facts_all_matched(set()),
            evidence_fingerprint="syn-fp-1",
        )
    assert section.synthesis.status is TestSynthesisStatus.FAILED
    assert section.finding_inventory.finding_count == 0
    assert any("synthesis_failed" in item for item in section.diagnostics)
