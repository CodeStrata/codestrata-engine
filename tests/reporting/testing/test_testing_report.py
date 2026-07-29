"""Test report adapter and presentation tests (Phase 4.6.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.application.testing.assessment.inventory import execution_facts_from_status_map
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
from codestrata.domain.testing.ids import (
    HYGIENE_RULE_IDS,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)
from codestrata.domain.testing.synthesis.enums import TestSynthesisStatus, TestThemeKind
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.testing.adapter import TestingReportAdapter
from codestrata.reporting.testing.models import (
    TESTING_REPORT_SECTION_ID,
    TESTING_REPORT_SECTION_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_FORBIDDEN = (
    "well tested",
    "testing passed",
    "tests passed",
    "no testing issues",
    "tests are sufficient",
    "fully tested",
)


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
        evidence_fingerprint="report-fp-1",
    )


def _finding(rule_id: str, finding_id: str) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.TESTING,
        metadata={"confidence": "high"},
    )


def _facts(matched: set[str]):
    return execution_facts_from_status_map(
        {
            rule_id: ("matched" if rule_id in matched else "not_matched")
            for rule_id in HYGIENE_RULE_IDS
        }
    )


def _section_with_findings():
    findings = (
        _finding(RULE_DISABLED_OR_SKIPPED, "f-001"),
        _finding(RULE_UNCONFIRMED_CANDIDATES, "f-002"),
    )
    return TestAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        evidence=_evidence(),
        rules_executed=4,
        rules_matched=2,
        rules_not_matched=2,
        rule_execution_facts=_facts({RULE_DISABLED_OR_SKIPPED, RULE_UNCONFIRMED_CANDIDATES}),
        evidence_fingerprint="report-fp-1",
        configuration_payload="report-config",
    )


def _empty_report_input(**kwargs):
    repo = Repository(name="fixture", path=Path("."), url=None)
    analysis = AnalysisResult(
        repository=repo,
        findings=(),
        technologies=(),
        recommendations=(),
    )
    return ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        report_title="Fixture Report",
        **kwargs,
    )


def test_report_contract_and_gate_default(tmp_path: Path) -> None:
    assert TESTING_REPORT_SECTION_ID == "report.testing"
    assert TESTING_REPORT_SECTION_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.testing.enabled is False
    assert settings.assessment.sections.testing.enabled is False


def test_report_gate_independent(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [assessment.sections.testing]
        enabled = true
        [report.sections.testing]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.report.sections.testing.enabled is True
    assert settings.assessment.sections.testing.enabled is True


def test_adapter_projects_inventory_and_synthesis() -> None:
    section = _section_with_findings()
    report = TestingReportAdapter().adapt(section)
    assert report.status == TestAssessmentStatus.SUCCEEDED.value
    assert report.overall_posture_summary
    assert report.inventory_summary.finding_count == 2
    assert "f-001" in report.inventory_summary.finding_ids
    assert report.execution_summary.rules_executed == 4
    assert report.execution_summary.rules_matched == 2
    assert report.themes
    assert TestThemeKind.DISABLED_OR_SKIPPED_TESTS.value in {item.kind for item in report.themes}
    assert report.conclusions
    assert report.recommendations
    joined = " ".join(
        [
            report.executive_summary,
            report.overall_posture_summary,
            *(item.summary for item in report.themes),
        ]
    ).lower()
    for phrase in _FORBIDDEN:
        assert phrase not in joined or "does not" in joined


def test_zero_findings_and_disabled_statuses() -> None:
    empty = TestAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        evidence=_evidence(),
        rules_executed=4,
        rules_matched=0,
        rules_not_matched=4,
        rule_execution_facts=_facts(set()),
        evidence_fingerprint="report-fp-1",
        configuration_payload="empty",
    )
    report = TestingReportAdapter().adapt(empty)
    assert report.synthesis_status == TestSynthesisStatus.EMPTY.value
    assert report.inventory_summary.none_detected_statement
    assert report.inventory_summary.finding_count == 0

    disabled = TestAssessmentAssembler().assemble_disabled(repository_id="repo:x")
    disabled_report = TestingReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    insufficient = TestAssessmentAssembler().assemble_insufficient_evidence(repository_id="repo:x")
    insufficient_report = TestingReportAdapter().adapt(insufficient)
    assert insufficient_report.status == "insufficient_evidence"


def test_synthesis_gated_off_keeps_inventory() -> None:
    section = _section_with_findings()
    report = TestingReportAdapter().adapt(
        section,
        include_themes=False,
        include_conclusions=False,
        include_recommendations=False,
    )
    assert report.inventory_summary.finding_count == 2
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()


def test_json_and_html_integration_and_determinism() -> None:
    section = _section_with_findings()
    report = TestingReportAdapter().adapt(section)
    left_input = _empty_report_input(testing_report=report)
    right_input = _empty_report_input(testing_report=report)
    left_doc = build_assessment_json_document(left_input)
    right_doc = build_assessment_json_document(right_input)
    assert "testing" in left_doc["assessment"]
    assert dumps_stable_json(left_doc) == dumps_stable_json(right_doc)
    assert left_doc["assessment"]["testing"]["section_id"] == TESTING_REPORT_SECTION_ID

    view = build_html_report_view_model(left_input)
    assert view.testing_report is not None
    html = HtmlReportRenderer().render(view)
    assert 'id="testing-assessment"' in html
    assert "Testing Assessment" in html
    assert "Overall Test Posture" in html
    assert "Rule Execution Summary" in html
    assert "Inventory Summary" in html
    assert "f-001" in html

    hidden = build_html_report_view_model(_empty_report_input(testing_report=None))
    hidden_html = HtmlReportRenderer().render(hidden)
    assert 'id="testing-assessment"' not in hidden_html


def test_adapter_failure_isolation() -> None:
    section = _section_with_findings()
    with patch.object(
        TestingReportAdapter,
        "adapt",
        side_effect=RuntimeError("boom"),
    ):
        try:
            TestingReportAdapter().adapt(section)
            raised = False
        except RuntimeError:
            raised = True
    assert raised is True
    # Assessment section remains usable independently.
    assert section.status is TestAssessmentStatus.SUCCEEDED
    assert section.finding_inventory.finding_count == 2


def test_recommendation_traceability() -> None:
    section = _section_with_findings()
    report = TestingReportAdapter().adapt(section)
    hygiene_recs = [item for item in report.recommendations if item.finding_ids]
    assert hygiene_recs
    for item in hygiene_recs:
        assert item.conclusion_ids
        assert item.rule_ids
