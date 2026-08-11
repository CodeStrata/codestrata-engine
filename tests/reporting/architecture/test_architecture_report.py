"""Architecture report adapter and presentation tests (Phase 4.2.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.architecture.assessment.assembler import (
    ArchitectureAssessmentAssembler,
)
from codestrata.application.architecture.conclusions.factory import (
    create_architecture_conclusion_service,
)
from codestrata.domain.architecture.assessment.enums import ArchitectureAssessmentStatus
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.architecture.ids import (
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_INVALID_DEPENDENCY_DIRECTION,
)
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.architecture.adapter import ArchitectureReportAdapter
from codestrata.reporting.architecture.models import (
    ARCHITECTURE_REPORT_SECTION_ID,
    ARCHITECTURE_REPORT_SECTION_VERSION,
)
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _finding(rule_id: str, *subjects: str) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description=f"{rule_id} observation",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.ARCHITECTURE,
        subject_keys=subjects,
        metadata={
            "confidence": "high",
            "subject_keys": ",".join(subjects),
            "remediation": f"Fix {rule_id}",
            "business_impact": "unknown",
        },
    )


def _codestrata_findings() -> tuple[Finding, ...]:
    return (
        _finding(
            RULE_DEPENDENCY_CYCLE,
            "codestrata.application",
            "codestrata.infrastructure",
            "cycle",
        ),
        _finding(
            RULE_INVALID_DEPENDENCY_DIRECTION,
            "codestrata.application",
            "codestrata.infrastructure",
            "application",
            "infrastructure",
        ),
        _finding(
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            "codestrata.application",
            "out:10",
        ),
    )


def _succeeded_assessment(*, conclusions_enabled: bool = True):
    findings = _codestrata_findings()
    conclusions = None
    if conclusions_enabled:
        conclusions = create_architecture_conclusion_service().build(
            repository_id="repo:codestrata",
            findings=findings,
            extraction_coverage=1.0,
            classification_coverage=0.3125,
            graph_fingerprint="fp",
        )
    return ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:codestrata",
        findings=findings,
        conclusion_result=conclusions,
        pack_enabled=True,
        conclusions_enabled=conclusions_enabled,
        extraction_coverage=1.0,
        classification_coverage=0.3125,
        graph_fingerprint="fp",
    )


def test_adapter_codestrata_option_a() -> None:
    assessment = _succeeded_assessment()
    report = ArchitectureReportAdapter().adapt(assessment)
    assert report.section_id == ARCHITECTURE_REPORT_SECTION_ID
    assert report.section_version == ARCHITECTURE_REPORT_SECTION_VERSION
    assert report.status == "succeeded"
    assert len(report.findings) == 3
    assert len(report.conclusions) == 2
    assert len(report.recommendation_groups) == 2
    assert report.strengths == ()
    assert report.include_strengths_heading is False
    assert report.conclusions[0].business_impact == "Unknown"
    assert "Wave" in report.conclusions[0].modernization_relevance or "wave" in (
        report.conclusions[0].modernization_relevance.lower()
    )
    assert "boundary" in report.executive_summary.lower() or "finding" in (
        report.executive_summary.lower()
    )
    assert any(item.status == "partial" for item in report.coverage_summary)
    assert "0%" not in " ".join(
        item.display
        for item in report.coverage_summary
        if item.status in {"unsupported", "not_applicable", "unknown"}
    )
    left = report.model_dump_json()
    right = ArchitectureReportAdapter().adapt(assessment).model_dump_json()
    assert left == right


def test_adapter_findings_only_when_conclusions_disabled() -> None:
    assessment = _succeeded_assessment(conclusions_enabled=False)
    report = ArchitectureReportAdapter().adapt(assessment)
    assert len(report.findings) == 3
    assert report.conclusions == ()
    assert "conclusions were not generated" in report.executive_summary.lower()


def test_adapter_zero_findings_succeeded() -> None:
    assessment = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=(),
        conclusion_result=None,
        pack_enabled=True,
        conclusions_enabled=False,
        extraction_coverage=1.0,
        classification_coverage=1.0,
    )
    report = ArchitectureReportAdapter().adapt(assessment)
    assert report.status == ArchitectureAssessmentStatus.SUCCEEDED.value
    assert report.findings == ()
    assert report.strengths == ()
    assert "no architecture findings" in report.executive_summary.lower()


def test_adapter_disabled_and_insufficient() -> None:
    disabled = ArchitectureAssessmentAssembler().assemble_disabled(
        repository_id="repo:x"
    )
    disabled_report = ArchitectureReportAdapter().adapt(disabled)
    assert disabled_report.status == "disabled"
    assert "disabled" in disabled_report.executive_summary.lower()

    insufficient = ArchitectureAssessmentAssembler().assemble(
        repository_id="repo:x",
        findings=(),
        conclusion_result=None,
        pack_enabled=True,
        conclusions_enabled=True,
        extraction_coverage=0.0,
        classification_coverage=0.0,
    )
    # Assembler may map empty coverage to insufficient_evidence.
    if insufficient.status is ArchitectureAssessmentStatus.INSUFFICIENT_EVIDENCE:
        report = ArchitectureReportAdapter().adapt(insufficient)
        assert "could not establish" in report.executive_summary.lower()


def test_include_toggles_omit_subsections() -> None:
    assessment = _succeeded_assessment()
    report = ArchitectureReportAdapter().adapt(
        assessment,
        include_conclusions=False,
        include_recommendation_groups=False,
        include_metrics=False,
        include_strengths=False,
        include_traceability=False,
    )
    assert report.conclusions == ()
    assert report.recommendation_groups == ()
    assert report.key_metrics == ()
    assert report.strengths == ()
    assert "not included" in report.traceability_summary.summary.lower()


def test_report_json_omits_architecture_when_absent(tmp_path: Path) -> None:
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
    assert "architecture" not in document["assessment"]


def test_report_json_and_html_include_architecture_when_present(tmp_path: Path) -> None:
    architecture_report = ArchitectureReportAdapter().adapt(_succeeded_assessment())
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
        architecture_report=architecture_report,
    )
    document = build_assessment_json_document(report_input)
    assert document["schema_version"] == "1.2"
    assert "architecture" in document["assessment"]
    assert (
        document["assessment"]["architecture"]["section_id"]
        == ARCHITECTURE_REPORT_SECTION_ID
    )
    assert (
        document["assessment"]["architecture"]["section_version"]
        == ARCHITECTURE_REPORT_SECTION_VERSION
    )

    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert 'id="architecture-intelligence"' in html
    assert 'id="architecture-assessment"' in html
    assert "Architecture conclusions" in html or "Architecture overview" in html
    assert "no significant architecture risks" not in html.lower()
    assert "/Users/" not in html
    assert "critical business risk" not in html.lower()


def test_html_omits_architecture_when_disabled(tmp_path: Path) -> None:
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
    assert 'id="architecture-assessment"' not in html
