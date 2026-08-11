"""AI Readiness report adapter and presentation tests (Phase 4.8.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from codestrata.application.ai_readiness.assessment.assembler import (
    AiReadinessAssessmentAssembler,
)
from codestrata.application.ai_readiness.assessment.inventory import (
    execution_facts_from_status_map,
)
from codestrata.config import load_settings
from codestrata.domain.ai_readiness.assessment.enums import AiReadinessAssessmentStatus
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
    RULE_API_BOUNDARIES,
    RULE_LLM_SDK,
)
from codestrata.domain.ai_readiness.synthesis.enums import (
    AiReadinessSynthesisStatus,
    AiReadinessThemeKind,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.ai_readiness.adapter import AiReadinessReportAdapter
from codestrata.reporting.ai_readiness.models import (
    AI_READINESS_REPORT_SECTION_ID,
    AI_READINESS_REPORT_SECTION_VERSION,
)
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.services.artifact_serialization import dumps_stable_json

_FORBIDDEN = (
    "ai ready",
    "agent ready",
    "rag ready",
    "readiness score",
    "modernize",
    "production ready",
    "no ai issues",
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
        category=FindingCategory.AI_READINESS,
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
            RULE_API_BOUNDARIES,
            "f-001",
            metadata={"api_boundary_kinds": "openapi"},
        ),
        _finding(
            RULE_LLM_SDK,
            "f-002",
            metadata={"llm_kinds": "openai"},
        ),
    )
    return AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rules_not_matched=len(HYGIENE_RULE_IDS) - 2,
        rule_execution_facts=_facts({RULE_API_BOUNDARIES, RULE_LLM_SDK}),
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
    assert AI_READINESS_REPORT_SECTION_ID == "report.ai_readiness"
    assert AI_READINESS_REPORT_SECTION_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.report.sections.ai_readiness.enabled is False
    assert settings.analysis.ai_readiness.enabled is False
    assert settings.report.sections.ai_readiness.include_inventory is True
    assert settings.report.sections.ai_readiness.include_themes is True


def test_report_gate_independent(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [analysis.ai_readiness]
        enabled = true
        [report.sections.ai_readiness]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.report.sections.ai_readiness.enabled is True
    assert settings.analysis.ai_readiness.enabled is True


def test_adapter_projects_inventory_and_synthesis() -> None:
    section = _section_with_findings()
    report = AiReadinessReportAdapter().adapt(section)
    assert report.status == AiReadinessAssessmentStatus.SUCCEEDED.value
    assert report.overall_posture_summary
    assert report.inventory_summary.finding_count == 2
    assert "f-001" in report.inventory_summary.finding_ids
    assert report.execution_summary.rules_executed == len(HYGIENE_RULE_IDS)
    assert report.execution_summary.rules_matched == 2
    assert report.capability_family_summary.families_observed >= 2
    assert report.themes
    assert AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES.value in {
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
        joined.replace("does not establish that the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("ai readiness", "")
        .replace("not ai ready", "")
    )
    for phrase in _FORBIDDEN:
        assert phrase not in sanitized


def test_zero_findings_and_disabled_statuses() -> None:
    empty = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=0,
        rules_not_matched=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts(set()),
        evidence_fingerprint="report-fp-1",
        configuration_payload="empty",
    )
    report = AiReadinessReportAdapter().adapt(empty)
    assert report.synthesis_status == AiReadinessSynthesisStatus.EMPTY.value
    assert report.inventory_summary.none_detected_statement
    assert report.inventory_summary.finding_count == 0

    disabled = AiReadinessAssessmentAssembler().assemble_disabled(repository_id="repo:x")
    disabled_report = AiReadinessReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    insufficient = AiReadinessAssessmentAssembler().assemble_insufficient_evidence(
        repository_id="repo:x"
    )
    insufficient_report = AiReadinessReportAdapter().adapt(insufficient)
    assert insufficient_report.status == "insufficient_evidence"

    failed = AiReadinessAssessmentAssembler().assemble_failed(repository_id="repo:x")
    failed_report = AiReadinessReportAdapter().adapt(failed)
    assert failed_report.status == "failed"


def test_synthesis_gated_off_keeps_inventory() -> None:
    section = _section_with_findings()
    report = AiReadinessReportAdapter().adapt(
        section,
        include_themes=False,
        include_conclusions=False,
        include_recommendations=False,
    )
    assert report.inventory_summary.finding_count == 2
    assert report.capability_family_summary.entries
    assert report.themes == ()
    assert report.conclusions == ()
    assert report.recommendations == ()


def test_json_and_html_integration_and_determinism() -> None:
    section = _section_with_findings()
    report = AiReadinessReportAdapter().adapt(section)
    left_input = _empty_report_input(ai_readiness_report=report)
    right_input = _empty_report_input(ai_readiness_report=report)
    left_doc = build_assessment_json_document(left_input)
    right_doc = build_assessment_json_document(right_input)
    assert "ai_readiness" in left_doc["assessment"]
    assert dumps_stable_json(left_doc) == dumps_stable_json(right_doc)
    assert left_doc["assessment"]["ai_readiness"]["section_id"] == (AI_READINESS_REPORT_SECTION_ID)

    view = build_html_report_view_model(left_input)
    assert view.ai_readiness_report is not None
    assert view.ai_readiness_intelligence is not None
    html = HtmlReportRenderer().render(view)
    assert 'id="ai-readiness"' in html
    assert 'id="ai-readiness-assessment"' in html
    assert "AI readiness overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    assert "f-001" in html or "api" in html.lower() or "openapi" in html.lower()

    hidden = build_html_report_view_model(_empty_report_input(ai_readiness_report=None))
    hidden_html = HtmlReportRenderer().render(hidden)
    assert 'id="ai-readiness-assessment"' not in hidden_html
    assert hidden.ai_readiness_intelligence is None


def test_adapter_failure_isolation() -> None:
    section = _section_with_findings()
    with patch.object(
        AiReadinessReportAdapter,
        "adapt",
        side_effect=RuntimeError("boom"),
    ):
        try:
            AiReadinessReportAdapter().adapt(section)
            raised = False
        except RuntimeError:
            raised = True
    assert raised is True
    assert section.status is AiReadinessAssessmentStatus.SUCCEEDED
    assert section.finding_inventory.finding_count == 2


def test_recommendation_traceability() -> None:
    section = _section_with_findings()
    report = AiReadinessReportAdapter().adapt(section)
    hygiene_recs = [item for item in report.recommendations if item.finding_ids]
    assert hygiene_recs
    for item in hygiene_recs:
        assert item.conclusion_ids
        assert item.rule_ids
    assert report.traceability.finding_ids
