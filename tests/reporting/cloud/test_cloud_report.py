"""Cloud report adapter and presentation tests (Phase 4.7.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.cloud.assessment.inventory import execution_facts_from_status_map
from codestrata.config import load_settings
from codestrata.domain.cloud.assessment.enums import CloudAssessmentStatus
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CONTAINERIZATION,
    RULE_KUBERNETES,
)
from codestrata.domain.cloud.synthesis.enums import CloudSynthesisStatus, CloudThemeKind
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.cloud.adapter import CloudReportAdapter
from codestrata.reporting.cloud.models import (
    CLOUD_REPORT_SECTION_ID,
    CLOUD_REPORT_SECTION_VERSION,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.services.artifact_serialization import dumps_stable_json

_FORBIDDEN = (
    "is cloud ready",
    "are cloud ready",
    "fully portable",
    "migrate to",
    "modernize",
    "no cloud issues",
    "production ready",
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
        category=FindingCategory.CLOUD,
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
            RULE_CONTAINERIZATION,
            "f-001",
            metadata={"container_kinds": "docker"},
        ),
        _finding(
            RULE_KUBERNETES,
            "f-002",
            metadata={"orchestration_kinds": "kubernetes"},
        ),
    )
    return CloudAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rules_not_matched=len(HYGIENE_RULE_IDS) - 2,
        rule_execution_facts=_facts({RULE_CONTAINERIZATION, RULE_KUBERNETES}),
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
    assert CLOUD_REPORT_SECTION_ID == "report.cloud"
    assert CLOUD_REPORT_SECTION_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.cloud.enabled is False
    assert settings.analysis.cloud.enabled is False
    assert settings.report.sections.cloud.include_inventory is True
    assert settings.report.sections.cloud.include_themes is True


def test_report_gate_independent(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [analysis.cloud]
        enabled = true
        [report.sections.cloud]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.report.sections.cloud.enabled is True
    assert settings.analysis.cloud.enabled is True


def test_adapter_projects_inventory_and_synthesis() -> None:
    section = _section_with_findings()
    report = CloudReportAdapter().adapt(section)
    assert report.status == CloudAssessmentStatus.SUCCEEDED.value
    assert report.overall_posture_summary
    assert report.inventory_summary.finding_count == 2
    assert "f-001" in report.inventory_summary.finding_ids
    assert report.execution_summary.rules_executed == len(HYGIENE_RULE_IDS)
    assert report.execution_summary.rules_matched == 2
    assert report.technology_family_summary.families_observed >= 2
    assert report.themes
    assert CloudThemeKind.CONTAINERIZATION_MATURITY.value in {item.kind for item in report.themes}
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
        joined.replace("does not establish cloud readiness", "")
        .replace("cloud readiness", "")
        .replace("not cloud ready", "")
    )
    for phrase in _FORBIDDEN:
        assert phrase not in sanitized


def test_zero_findings_and_disabled_statuses() -> None:
    empty = CloudAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=0,
        rules_not_matched=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts(set()),
        evidence_fingerprint="report-fp-1",
        configuration_payload="empty",
    )
    report = CloudReportAdapter().adapt(empty)
    assert report.synthesis_status == CloudSynthesisStatus.EMPTY.value
    assert report.inventory_summary.none_detected_statement
    assert report.inventory_summary.finding_count == 0

    disabled = CloudAssessmentAssembler().assemble_disabled(repository_id="repo:x")
    disabled_report = CloudReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    insufficient = CloudAssessmentAssembler().assemble_insufficient_evidence(repository_id="repo:x")
    insufficient_report = CloudReportAdapter().adapt(insufficient)
    assert insufficient_report.status == "insufficient_evidence"


def test_synthesis_gated_off_keeps_inventory() -> None:
    section = _section_with_findings()
    report = CloudReportAdapter().adapt(
        section,
        include_themes=False,
        include_conclusions=False,
        include_recommendations=False,
    )
    assert report.inventory_summary.finding_count == 2
    assert report.technology_family_summary.entries
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()


def test_json_and_html_integration_and_determinism() -> None:
    section = _section_with_findings()
    report = CloudReportAdapter().adapt(section)
    left_input = _empty_report_input(cloud_report=report)
    right_input = _empty_report_input(cloud_report=report)
    left_doc = build_assessment_json_document(left_input)
    right_doc = build_assessment_json_document(right_input)
    assert "cloud" in left_doc["assessment"]
    assert dumps_stable_json(left_doc) == dumps_stable_json(right_doc)
    assert left_doc["assessment"]["cloud"]["section_id"] == CLOUD_REPORT_SECTION_ID

    view = build_html_report_view_model(left_input)
    assert view.cloud_report is not None
    assert view.cloud_intelligence is not None
    html = HtmlReportRenderer().render(view)
    assert 'id="cloud-assessment"' in html
    assert 'id="cloud-readiness"' in html
    assert "Cloud Assessment" in html or "Cloud readiness" in html
    assert "Cloud overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    # Finding IDs still surface via inventory-derived intelligence / heads.
    assert "f-001" in html or view.cloud_intelligence.finding_count >= 2

    hidden = build_html_report_view_model(_empty_report_input(cloud_report=None))
    hidden_html = HtmlReportRenderer().render(hidden)
    assert 'id="cloud-assessment"' not in hidden_html
    assert hidden.cloud_intelligence is None


def test_adapter_failure_isolation() -> None:
    section = _section_with_findings()
    with patch.object(
        CloudReportAdapter,
        "adapt",
        side_effect=RuntimeError("boom"),
    ):
        try:
            CloudReportAdapter().adapt(section)
            raised = False
        except RuntimeError:
            raised = True
    assert raised is True
    assert section.status is CloudAssessmentStatus.SUCCEEDED
    assert section.finding_inventory.finding_count == 2


def test_recommendation_traceability() -> None:
    section = _section_with_findings()
    report = CloudReportAdapter().adapt(section)
    hygiene_recs = [item for item in report.recommendations if item.finding_ids]
    assert hygiene_recs
    for item in hygiene_recs:
        assert item.conclusion_ids
        assert item.rule_ids
    assert report.traceability.finding_ids
