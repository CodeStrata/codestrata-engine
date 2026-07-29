"""Technical Debt report adapter and presentation tests (Phase 4.3.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
)
from codestrata.domain.technical_debt.ids import (
    RULE_EXCESSIVE_BRANCHING,
    RULE_LARGE_CALLABLE,
)
from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
)
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.reporting.technical_debt.adapter import TechnicalDebtReportAdapter
from codestrata.reporting.technical_debt.models import (
    TECHNICAL_DEBT_REPORT_SECTION_ID,
    TECHNICAL_DEBT_REPORT_SECTION_VERSION,
    TOP_PRODUCTION_HOTSPOTS,
)


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    classification: str = "source",
    metric: str = "physical_line_count",
    value: str = "80",
    threshold: str = "50",
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{metric}={value} threshold {threshold}",
        severity=severity,
        category=FindingCategory.TECHNICAL_DEBT,
        subject_keys=(path, symbol),
        metadata={
            "classification": classification,
            "language": "python" if path.endswith(".py") else "java",
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "severity_basis": f"value>{threshold}",
            "confidence": "high",
            "taxonomy_id": "technical-debt.complexity",
            "assessment_dimensions": "technical-debt",
            "subject_keys": f"{path},{symbol}",
            "path": path,
            "package": "/".join(path.split("/")[:-1]),
        },
    )


def _succeeded_assessment(*, include_test: bool = True):
    findings = [
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/codestrata/app.py",
            symbol="run#0@1",
            severity=FindingSeverity.HIGH,
            value="120",
        ),
        _finding(
            rule_id=RULE_EXCESSIVE_BRANCHING,
            path="src/codestrata/app.py",
            symbol="run#0@1",
            metric="branch_point_count",
            value="12",
            threshold="10",
        ),
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path="src/codestrata/other.py",
            symbol="other#0@1",
            value="70",
        ),
    ]
    if include_test:
        findings.append(
            _finding(
                rule_id=RULE_LARGE_CALLABLE,
                path="tests/test_app.py",
                symbol="test_big#0@1",
                classification="test",
                value="70",
            )
        )
    return TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=tuple(findings),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=3,
        files_analyzed=3,
        configuration_payload="stable-report",
    )


def test_adapter_succeeded_preserves_ids_and_bounds() -> None:
    assessment = _succeeded_assessment()
    report = TechnicalDebtReportAdapter().adapt(assessment)
    assert report.section_id == TECHNICAL_DEBT_REPORT_SECTION_ID
    assert report.section_version == TECHNICAL_DEBT_REPORT_SECTION_VERSION
    assert report.status == "succeeded"
    assert report.generated_from_assessment_section_version == assessment.section_version
    assert int(report.metadata["production_finding_count"]) == 3
    assert int(report.metadata["test_finding_count"]) == 1
    assert len(report.top_production_hotspots) <= TOP_PRODUCTION_HOTSPOTS
    assert report.top_production_hotspots[0].presentation_order == 1
    assert all(
        item.source_role == "production" for item in report.significant_themes
    )
    assert all(
        item.audience != TechnicalDebtConclusionAudience.TEST_OBSERVATION.value
        for item in report.conclusions
    )
    assert report.test_observation.present is True
    assert report.test_observation.finding_count == 1
    assert assessment.hotspot_inventory.production[0].hotspot_id == (
        report.top_production_hotspots[0].hotspot_id
    )
    assert "priority" not in report.hotspot_presentation_note.lower() or (
        "not a priority" in report.hotspot_presentation_note.lower()
    )
    assert "composite" in report.executive_summary.lower() or (
        "financial" in report.executive_summary.lower()
    )
    left = report.model_dump_json()
    right = TechnicalDebtReportAdapter().adapt(assessment).model_dump_json()
    assert left == right


def test_adapter_disabled_and_not_requested() -> None:
    disabled = TechnicalDebtAssessmentAssembler().assemble_disabled(
        repository_id="repo:x"
    )
    disabled_report = TechnicalDebtReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    not_requested = disabled.model_copy(
        update={"status": TechnicalDebtAssessmentStatus.NOT_REQUESTED}
    )
    not_requested_report = TechnicalDebtReportAdapter().adapt(not_requested)
    assert not_requested_report.status == "not_requested"
    assert "not requested" in not_requested_report.executive_summary.lower()


def test_adapter_empty_and_test_only() -> None:
    empty = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
    )
    empty_report = TechnicalDebtReportAdapter().adapt(empty)
    assert empty_report.status == TechnicalDebtAssessmentStatus.SUCCEEDED.value
    assert empty_report.top_production_hotspots == ()
    assert "no production-source" in empty_report.executive_summary.lower()

    test_only = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:test-only",
        findings=(
            _finding(
                rule_id=RULE_LARGE_CALLABLE,
                path="tests/test_app.py",
                symbol="test_big#0@1",
                classification="test",
                value="70",
            ),
        ),
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=1,
        files_analyzed=1,
    )
    test_report = TechnicalDebtReportAdapter().adapt(test_only)
    assert int(test_report.metadata["production_finding_count"]) == 0
    assert test_report.test_observation.present is True
    assert "test-maintainability" in test_report.executive_summary.lower()
    assert test_report.top_production_hotspots == ()


def test_include_toggles_omit_subsections() -> None:
    assessment = _succeeded_assessment()
    report = TechnicalDebtReportAdapter().adapt(
        assessment,
        include_conclusions=False,
        include_recommendations=False,
        include_metrics=False,
        include_themes=False,
        include_hotspots=False,
        include_test_observation=False,
        include_traceability=False,
    )
    assert report.conclusions == ()
    assert report.recommendations == ()
    assert report.key_metrics == ()
    assert report.significant_themes == ()
    assert report.top_production_hotspots == ()
    assert report.test_observation.present is False
    assert "not included" in report.traceability_summary.summary.lower()


def test_hotspot_bound_and_deterministic_order() -> None:
    findings = tuple(
        _finding(
            rule_id=RULE_LARGE_CALLABLE,
            path=f"src/pkg/file_{index:02d}.py",
            symbol=f"fn_{index}#0@1",
            severity=(
                FindingSeverity.HIGH if index < 3 else FindingSeverity.MEDIUM
            ),
            value=str(100 - index),
        )
        for index in range(25)
    )
    assessment = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:many",
        findings=findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        files_considered=25,
        files_analyzed=25,
    )
    report = TechnicalDebtReportAdapter().adapt(assessment, top_hotspot_limit=20)
    assert len(report.top_production_hotspots) == 20
    orders = [item.presentation_order for item in report.top_production_hotspots]
    assert orders == list(range(1, 21))
    ids = [item.hotspot_id for item in report.top_production_hotspots]
    assert ids == [
        item.hotspot_id for item in assessment.hotspot_inventory.production[:20]
    ]


def test_traceability_sample_is_bounded() -> None:
    assessment = _succeeded_assessment()
    report = TechnicalDebtReportAdapter().adapt(assessment)
    assert report.traceability_summary.edge_count == len(assessment.traceability.edges)
    assert len(report.traceability_summary.sample_edges) <= 12
    for edge in report.traceability_summary.sample_edges:
        assert edge.source_id
        assert edge.target_id
        assert edge.relation


def test_report_json_omits_technical_debt_when_absent(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path / "demo"),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
    )
    document = build_assessment_json_document(report_input)
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert "technical_debt" not in document["assessment"]


def test_report_json_and_html_include_technical_debt_when_present(
    tmp_path: Path,
) -> None:
    debt_report = TechnicalDebtReportAdapter().adapt(_succeeded_assessment())
    analysis = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path / "demo"),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
        technical_debt_report=debt_report,
    )
    document = build_assessment_json_document(report_input)
    assert document["schema_version"] == "1.2"
    assert "technical_debt" in document["assessment"]
    section = document["assessment"]["technical_debt"]
    assert section["section_id"] == TECHNICAL_DEBT_REPORT_SECTION_ID
    assert section["section_version"] == TECHNICAL_DEBT_REPORT_SECTION_VERSION
    assert section["top_production_hotspots"][0]["hotspot_id"]
    assert "test_observation" in section

    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert 'id="technical-debt-assessment"' in html
    assert "Technical Debt Assessment" in html
    assert "Top production hotspots" in html
    assert "Test-maintainability observation" in html
    assert "not production health" in html.lower()
    assert "priority ranking" in html.lower() or "not a priority" in html.lower()
    assert "/Users/" not in html
    assert "financial" in html.lower() or "composite" in html.lower()
    escaped = HtmlReportRenderer().render(
        build_html_report_view_model(
            report_input.model_copy(
                update={
                    "technical_debt_report": debt_report.model_copy(
                        update={
                            "executive_summary": '<script>alert("x")</script> debt'
                        }
                    )
                }
            )
        )
    )
    assert "<script>alert" not in escaped
    assert "&lt;script&gt;" in escaped


def test_html_omits_technical_debt_when_absent(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        repository=Repository(name="demo", path=tmp_path / "demo"),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
    )
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert 'id="technical-debt-assessment"' not in html


def test_adapter_failure_isolation_pattern() -> None:
    """Adapter exceptions must not escape the report orchestration boundary."""

    assessment = _succeeded_assessment()

    def _boom(_self: object, *_args: object, **_kwargs: object) -> object:
        raise RuntimeError("adapter boom")

    with patch.object(TechnicalDebtReportAdapter, "adapt", _boom):
        with pytest.raises(RuntimeError, match="adapter boom"):
            TechnicalDebtReportAdapter().adapt(assessment)

    # Orchestration contract: callers wrap adapt() and continue without the section.
    technical_debt_report_section = None
    technical_debt_report_status = None
    try:
        with patch.object(TechnicalDebtReportAdapter, "adapt", _boom):
            technical_debt_report_section = TechnicalDebtReportAdapter().adapt(
                assessment
            )
    except Exception:  # noqa: BLE001 - mirrors assessment service isolation
        technical_debt_report_section = None
        technical_debt_report_status = "failed"
    assert technical_debt_report_section is None
    assert technical_debt_report_status == "failed"
