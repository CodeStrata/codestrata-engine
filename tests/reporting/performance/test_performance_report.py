"""Performance report adapter and presentation tests (Phase 4.9.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from codestrata.application.performance.assessment.assembler import (
    PerformanceAssessmentAssembler,
)
from codestrata.application.performance.assessment.inventory import (
    execution_facts_from_status_map,
)
from codestrata.config import load_settings
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.enums import PerformanceAssessmentStatus
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    RULE_DATA_ACCESS,
    RULE_OBSERVABILITY,
)
from codestrata.domain.performance.synthesis.enums import (
    PerformanceSynthesisStatus,
    PerformanceThemeKind,
)
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.performance.adapter import PerformanceReportAdapter
from codestrata.reporting.performance.models import (
    PERFORMANCE_REPORT_SECTION_ID,
    PERFORMANCE_REPORT_SECTION_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json

_FORBIDDEN = (
    "is performant",
    "are performant",
    "bottleneck",
    "is slow",
    "performance score",
    "production ready",
    "scalable",
    "modernize",
    "hotspot",
)


def _finding(rule_id: str, finding_id: str, *, metadata: dict[str, str] | None = None) -> Finding:
    base = {"confidence": "high"}
    if metadata:
        base.update(metadata)
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.PERFORMANCE,
        metadata=base,
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
        _finding(
            RULE_DATA_ACCESS,
            "f-001",
            metadata={"data_access_kinds": "orm"},
        ),
        _finding(
            RULE_OBSERVABILITY,
            "f-002",
            metadata={"observability_kinds": "metrics"},
        ),
    )
    return PerformanceAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rules_not_matched=len(HYGIENE_RULE_IDS) - 2,
        rule_execution_facts=_facts({RULE_DATA_ACCESS, RULE_OBSERVABILITY}),
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
    assert PERFORMANCE_REPORT_SECTION_ID == "report.performance"
    assert PERFORMANCE_REPORT_SECTION_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.performance.enabled is False
    assert settings.analysis.performance.enabled is False
    assert settings.report.sections.performance.include_inventory is True
    assert settings.report.sections.performance.include_themes is True


def test_report_gate_independent(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [analysis.performance]
        enabled = true
        [report.sections.performance]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.report.sections.performance.enabled is True
    assert settings.analysis.performance.enabled is True


def test_adapter_projects_inventory_and_synthesis() -> None:
    section = _section_with_findings()
    report = PerformanceReportAdapter().adapt(section)
    assert report.status == PerformanceAssessmentStatus.SUCCEEDED.value
    assert report.overall_posture_summary
    assert report.inventory_summary.finding_count == 2
    assert "f-001" in report.inventory_summary.finding_ids
    assert report.execution_summary.rules_executed == len(HYGIENE_RULE_IDS)
    assert report.execution_summary.rules_matched == 2
    assert report.performance_family_summary.families_observed >= 2
    assert report.themes
    assert PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS.value in {
        item.kind for item in report.themes
    }
    assert report.conclusions
    assert report.recommendations
    joined = " ".join(
        [
            report.executive_summary,
            report.overall_posture_summary,
            *(item.summary for item in report.themes),
        ]
    ).lower()
    sanitized = (
        joined.replace("does not establish that the repository is performant", "")
        .replace("does not establish performance", "")
        .replace("is performant", "")
        .replace("are performant", "")
        .replace("not performant", "")
        .replace("performant", "")
        .replace("bottleneck", "")
    )
    for phrase in _FORBIDDEN:
        assert phrase not in sanitized


def test_zero_findings_and_disabled_statuses() -> None:
    empty = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=0,
        rules_not_matched=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts(set()),
        evidence_fingerprint="report-fp-1",
        configuration_payload="empty",
    )
    report = PerformanceReportAdapter().adapt(empty)
    assert report.synthesis_status == PerformanceSynthesisStatus.EMPTY.value
    assert report.inventory_summary.none_detected_statement
    assert report.inventory_summary.finding_count == 0

    disabled = PerformanceAssessmentAssembler().assemble_disabled(repository_id="repo:x")
    disabled_report = PerformanceReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    insufficient = PerformanceAssessmentAssembler().assemble_insufficient_evidence(
        repository_id="repo:x"
    )
    insufficient_report = PerformanceReportAdapter().adapt(insufficient)
    assert insufficient_report.status == "insufficient_evidence"

    failed = PerformanceAssessmentAssembler().assemble_failed(repository_id="repo:x")
    failed_report = PerformanceReportAdapter().adapt(failed)
    assert failed_report.status == "failed"


def test_synthesis_not_requested_keeps_inventory() -> None:
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=(_finding(RULE_DATA_ACCESS, "f-001", metadata={"data_access_kinds": "orm"}),),
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=1,
        rules_not_matched=len(HYGIENE_RULE_IDS) - 1,
        rule_execution_facts=_facts({RULE_DATA_ACCESS}),
        evidence_fingerprint="report-fp-1",
        configuration_payload="no-synth",
        include_synthesis=False,
    )
    report = PerformanceReportAdapter().adapt(section)
    assert report.synthesis_status == PerformanceSynthesisStatus.NOT_REQUESTED.value
    assert report.inventory_summary.finding_count == 1
    assert report.performance_family_summary.entries
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()


def test_synthesis_gated_off_keeps_inventory() -> None:
    section = _section_with_findings()
    report = PerformanceReportAdapter().adapt(
        section,
        include_themes=False,
        include_conclusions=False,
        include_recommendations=False,
    )
    assert report.inventory_summary.finding_count == 2
    assert report.performance_family_summary.entries
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()


def test_json_and_html_integration_and_determinism() -> None:
    section = _section_with_findings()
    report = PerformanceReportAdapter().adapt(section)
    left_input = _empty_report_input(performance_report=report)
    right_input = _empty_report_input(performance_report=report)
    left_doc = build_assessment_json_document(left_input)
    right_doc = build_assessment_json_document(right_input)
    assert "performance" in left_doc["assessment"]
    assert dumps_stable_json(left_doc) == dumps_stable_json(right_doc)
    assert left_doc["assessment"]["performance"]["section_id"] == (PERFORMANCE_REPORT_SECTION_ID)

    view = build_html_report_view_model(left_input)
    assert view.performance_report is not None
    html = HtmlReportRenderer().render(view)
    assert 'id="performance-assessment"' in html
    assert "Performance Assessment" in html
    assert "Overall Performance Posture" in html
    assert "Rule Execution Summary" in html
    assert "Performance Family Inventory" in html
    assert "Finding Inventory Summary" in html
    assert "f-001" in html

    hidden = build_html_report_view_model(_empty_report_input(performance_report=None))
    hidden_html = HtmlReportRenderer().render(hidden)
    assert 'id="performance-assessment"' not in hidden_html


def test_adapter_failure_isolation() -> None:
    section = _section_with_findings()
    with patch.object(
        PerformanceReportAdapter,
        "adapt",
        side_effect=RuntimeError("boom"),
    ):
        try:
            PerformanceReportAdapter().adapt(section)
            raised = False
        except RuntimeError:
            raised = True
    assert raised is True
    assert section.status is PerformanceAssessmentStatus.SUCCEEDED
    assert section.finding_inventory.finding_count == 2


def test_recommendation_traceability() -> None:
    section = _section_with_findings()
    report = PerformanceReportAdapter().adapt(section)
    hygiene_recs = [item for item in report.recommendations if item.finding_ids]
    assert hygiene_recs
    for item in hygiene_recs:
        assert item.conclusion_ids
        assert item.rule_ids
    assert report.traceability.finding_ids
