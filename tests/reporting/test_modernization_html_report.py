"""Tests for the modernization assessment HTML report."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.ai.agents.models import (
    AgentExecutionStatus,
    AgentExecutionTrace,
    ModernizationAssessmentResult,
)
from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.providers.models import ModelInvocationMetadata, ModelUsage
from codestrata.ai.recommendations import (
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    EvidenceCoverage,
    ModernizationPhase,
)
from codestrata.models import (
    AnalysisResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.reporting import (
    AIExecutionStatus,
    AssessmentMode,
    AssessmentTiming,
    ModernizationHTMLReportRenderer,
    ModernizationReportInput,
    ModernizationReportValidationError,
    modernization_report_input_from_json,
    modernization_report_input_to_json,
    sanitize_display_path,
    write_modernization_html_report,
)
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def _truncation(
    count: int = 0, *, truncated: bool = False, original: int | None = None
) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=truncated,
        original_count=original if original is not None else count,
        included_count=count,
    )


def _analysis_result(tmp_path: Path, *, repo_name: str = "sample-app") -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name=repo_name,
            path=tmp_path / "workspace" / repo_name,
            source_url="https://github.com/example/sample-app.git",
            default_branch="main",
            files=["src/App.java", "pom.xml"],
            total_files=2,
        ),
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                version="17",
                confidence=1.0,
                source="test",
            ),
            Technology(
                name="Maven",
                category=TechnologyCategory.BUILD_TOOL,
                confidence=1.0,
                source="test",
            ),
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=2,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="Critical finding",
                description="Secret exposure risk",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
                evidence=[
                    Evidence(file_path=".", description="Whole repository"),
                    Evidence(file_path="src/App.java", line_number=10),
                ],
                affected_technologies=["Java"],
            ),
            Finding(
                rule_id="SEC002",
                title="Medium finding",
                description="Dependency hygiene",
                category=FindingCategory.SECURITY,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="pom.xml", line_number=4)],
                affected_technologies=["Maven"],
            ),
        ],
    )


def _context(*, repo_name: str = "sample-app", truncated: bool = False) -> LLMAnalysisContext:
    findings = [
        LLMFindingEvidence(
            rule_id="SEC001",
            title="Critical finding",
            category="security",
            severity="critical",
            summary="Secret exposure risk",
            evidence=[LLMEvidenceLocation(path=".")],
            evidence_truncation=_truncation(1),
        ),
        LLMFindingEvidence(
            rule_id="SEC002",
            title="Medium finding",
            category="security",
            severity="medium",
            summary="Dependency hygiene",
            evidence_truncation=_truncation(),
        ),
    ]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name=repo_name,
            source_type="github",
            default_branch="main",
            commit_sha="abc1234",
            file_count=2,
        ),
        technologies=[
            LLMTechnologyEvidence(name="Java", category="language", version="17"),
            LLMTechnologyEvidence(name="Maven", category="build_tool"),
        ],
        metrics=LLMMetricsContext(
            file_count=2,
            source_file_count=1,
            test_file_count=0,
            finding_count=2,
            technology_count=2,
        ),
        findings=findings,
        findings_truncation=_truncation(
            count=2,
            truncated=truncated,
            original=5 if truncated else 2,
        ),
    )


def _recommendation(
    recommendation_id: str,
    *,
    related: list[str] | None = None,
    dependencies: list[str] | None = None,
    priority: AIRecommendationPriority = AIRecommendationPriority.HIGH,
) -> AIRecommendation:
    return AIRecommendation(
        recommendation_id=recommendation_id,
        title=f"Title {recommendation_id}",
        description=f"Description {recommendation_id}",
        rationale=f"Rationale {recommendation_id}",
        priority=priority,
        effort=AIRecommendationEffort.MEDIUM,
        impact=AIRecommendationImpact.HIGH,
        confidence=AIRecommendationConfidence.MEDIUM,
        related_finding_ids=related or [],
        suggested_actions=["Implement control"],
        dependencies=dependencies or [],
    )


def _assessment(
    *,
    related_ok: bool = True,
    raw_response: str | None = '<script>alert("x")</script>',
) -> ModernizationAssessmentResult:
    related_one = ["SEC001"] if related_ok else ["MISSING"]
    result = AIRecommendationResult(
        executive_summary="Executive summary of modernization opportunities.",
        overall_assessment="The application is moderately ready for modernization.",
        key_risks=["Secret exposure", "Weak dependency controls"],
        recommendations=[
            _recommendation("AI-REC-001", related=related_one),
            _recommendation(
                "AI-REC-002",
                related=["SEC002"] if related_ok else [],
                dependencies=["AI-REC-001"],
                priority=AIRecommendationPriority.MEDIUM,
            ),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Reduce critical risk",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Lower exposure"],
            ),
            ModernizationPhase(
                phase=2,
                name="Hardening",
                objective="Improve dependency hygiene",
                recommendations=["AI-REC-002"],
                expected_outcomes=["Safer builds"],
            ),
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=2,
            findings_considered=2,
            findings_referenced=2,
            coverage_percentage=100.0,
            input_truncated=False,
        ),
        limitations=["No runtime profiling data was available."],
    )
    return ModernizationAssessmentResult(
        recommendation_result=result,
        model_metadata=ModelInvocationMetadata(
            provider="fake",
            model_id="test-model",
            request_id="req-1",
            latency_ms=42.5,
            usage=ModelUsage(input_tokens=11, output_tokens=22, total_tokens=33),
            stop_reason="end_turn",
        ),
        trace=AgentExecutionTrace(
            trace_id="trace-1",
            started_at_utc=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            completed_at_utc=datetime(2026, 7, 21, 12, 1, tzinfo=UTC),
            total_latency_ms=1000.0,
            status=AgentExecutionStatus.COMPLETED,
            steps=(),
            tool_call_count=5,
            model_call_count=1,
            input_tokens=11,
            output_tokens=22,
            total_tokens=33,
        ),
        raw_model_response=raw_response,
    )


def _report_input(
    tmp_path: Path,
    *,
    truncated: bool = False,
    organization_name: str | None = "Example Org",
    confidentiality_notice: str | None = "Internal use only",
    assessment: ModernizationAssessmentResult | None = None,
    analysis: AnalysisResult | None = None,
    context: LLMAnalysisContext | None = None,
    assessment_mode: AssessmentMode = AssessmentMode.AI_ENHANCED,
) -> ModernizationReportInput:
    return ModernizationReportInput(
        analysis_result=analysis or _analysis_result(tmp_path),
        assessment_mode=assessment_mode,
        analysis_context=context or _context(truncated=truncated),
        assessment_result=assessment or _assessment(),
        ai_status=(
            AIExecutionStatus.SUCCEEDED
            if assessment_mode == AssessmentMode.AI_ENHANCED
            else AIExecutionStatus.NOT_REQUESTED
        ),
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        organization_name=organization_name,
        confidentiality_notice=confidentiality_notice,
    )


def test_complete_report_rendering(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path, truncated=True))
    assert "<!DOCTYPE html>" in html
    assert "Engineering Assessment" in html
    assert "CodeStrata" in html
    assert "Generated by CodeStrata Community Edition" in html
    assert "sample-app" in html
    assert "Example Org" in html
    assert "Internal use only" in html
    for section in (
        "Leadership Verdict",
        "Executive Summary",
        "Technology Overview",
        "Findings",
        "Priority Actions",
        "Technical Appendix",
        "Repository Profile",
        "Graph and Artifact References",
        "Assessment Metadata",
    ):
        assert section in html
    assert 'id="ai-enrichment"' not in html
    assert "Warnings" in html


def test_minimal_valid_report(tmp_path: Path) -> None:
    assessment = _assessment()
    minimal = ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=_context(),
        assessment_result=assessment,
        ai_status=AIExecutionStatus.SUCCEEDED,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    html = ModernizationHTMLReportRenderer().render(minimal)
    assert "Engineering Assessment" in html
    assert "CodeStrata" in html
    assert "sample-app" in html
    assert "Leadership Verdict" in html
    assert "Executive Summary" in html
    assert "Should I care?" in html


def test_deterministic_report_without_ai(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    html = ModernizationHTMLReportRenderer().render(report_input)
    assert "Leadership Verdict" in html
    assert "Executive Summary" in html
    assert 'id="ai-enrichment"' not in html
    assert "Priority Actions" in html
    assert "Findings" in html
    assert "Critical finding" in html
    assert "Java" in html
    assert "AI-REC-001" not in html
    assert "Agent version" not in html
    assert "SYSTEM PROMPT" not in html
    assert str(tmp_path) not in html


def test_deterministic_report_rejects_assessment_result(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must not include assessment_result"):
        ModernizationReportInput(
            analysis_result=_analysis_result(tmp_path),
            assessment_mode=AssessmentMode.DETERMINISTIC,
            assessment_result=_assessment(),
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        )


def test_deterministic_output(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    renderer = ModernizationHTMLReportRenderer()
    assert renderer.render(report_input) == renderer.render(report_input)


def test_executive_summary_and_ai_label(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert 'id="ai-enrichment"' not in html


def test_repository_overview_technology_and_metrics(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert "Findings" in html
    assert "Java" in html
    assert "Maven" in html
    assert "Findings" in html
    assert "Repository Profile" in html
    assert "Files" in html


def test_risks_recommendations_and_phases(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert "Critical finding" in html
    assert "SEC001" in html
    assert 'id="ai-enrichment"' not in html
    assert "AI-REC-001" not in html


def test_deterministic_findings_and_anchors(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert re.search(r'id="finding-[0-9a-f-]{36}"', html)
    assert "Rule ID" in html
    assert "SEC001" in html


def test_evidence_coverage_limitations_and_validation_note(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path, truncated=True))
    assert "Findings" in html
    assert "Priority Actions" in html
    assert 'id="ai-enrichment"' not in html


def test_execution_metadata(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert "test-model" in html
    assert "Assessment Metadata" in html
    assert "AI status" in html


def test_methodology_toc_print_css_and_csp(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert 'id="executive-summary"' in html
    assert 'id="leadership-verdict"' in html
    assert 'id="metadata"' in html
    assert "@media print" in html
    assert "Content-Security-Policy" in html
    assert "default-src 'none'" in html
    assert "script-src 'none'" in html


def test_analysis_coverage_section_disabled_static_analysis(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(
        ModernizationReportInput(
            analysis_result=_analysis_result(tmp_path),
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        )
    )
    assert "Assessment Metadata" in html
    assert "not_requested" in html
    assert 'id="ai-enrichment"' not in html


def test_analysis_coverage_unavailable_and_timing(tmp_path: Path) -> None:
    analysis = _analysis_result(tmp_path).model_copy(
        update={
            "static_analysis_results": [
                StaticAnalysisResult(
                    provider_id="pmd",
                    provider_name="pmd",
                    provider_version="7.0.0",
                    status=StaticAnalysisStatus.UNAVAILABLE,
                    findings=[],
                    duration_ms=12.5,
                    error_message="pmd not found",
                )
            ]
        }
    )
    html = ModernizationHTMLReportRenderer().render(
        ModernizationReportInput(
            analysis_result=analysis,
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
            timing=AssessmentTiming(
                total_ms=250.0,
                scan_ms=20.0,
                analysis_ms=100.0,
                static_analysis_ms=12.5,
                ai_ms=None,
                report_ms=15.0,
            ),
        )
    )
    assert "Assessment Metadata" in html
    assert "Total ms" in html
    assert "Scan ms" in html
    assert "Report ms" in html


def test_html_escaping_and_injection_prevention(tmp_path: Path) -> None:
    poisoned = _assessment()
    poisoned = ModernizationAssessmentResult(
        recommendation_result=AIRecommendationResult(
            executive_summary='<script>alert("xss")</script>',
            overall_assessment="<img src=x onerror=alert(1)>",
            key_risks=["<b>bold</b>"],
            recommendations=[
                _recommendation("AI-REC-001", related=["SEC001"]),
            ],
            modernization_phases=[],
            evidence_coverage=EvidenceCoverage(
                total_findings=1,
                findings_considered=1,
                findings_referenced=1,
                coverage_percentage=100.0,
            ),
            limitations=['<iframe src="http://evil"></iframe>'],
        ),
        model_metadata=poisoned.model_metadata,
        trace=poisoned.trace,
        raw_model_response='{"prompt":"SYSTEM INSTRUCTIONS","secret":"AKIAIOSFODNN7EXAMPLE"}',
    )
    html = ModernizationHTMLReportRenderer().render(
        _report_input(
            tmp_path,
            assessment=poisoned,
            organization_name="<script>org</script>",
            confidentiality_notice="<svg onload=alert(1)>",
        )
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<svg onload=" not in html
    assert "&lt;svg onload=" in html


def test_absence_of_raw_response_prompts_excerpts_credentials(tmp_path: Path) -> None:
    assessment = _assessment(
        raw_response=(
            "SYSTEM INSTRUCTIONS Developer instructions AKIAIOSFODNN7EXAMPLE excerpt=class App {}"
        )
    )
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path, assessment=assessment))
    assert "AKIAIOSFODNN7EXAMPLE" not in html
    assert "SYSTEM INSTRUCTIONS" not in html
    assert "Developer instructions" not in html
    assert "excerpt=class App {}" not in html
    assert assessment.raw_model_response is not None
    assert assessment.raw_model_response not in html
    assert str(tmp_path / "workspace" / "sample-app") not in html


def test_repository_path_sanitization() -> None:
    assert sanitize_display_path("/var/tmp/project/src/App.java") == "App.java"
    assert sanitize_display_path("src/App.java") == "src/App.java"
    assert sanitize_display_path(".") == "."


def test_inconsistent_repository_rejection(tmp_path: Path) -> None:
    with pytest.raises(ModernizationReportValidationError, match="Inconsistent repository"):
        ModernizationHTMLReportRenderer().render(
            _report_input(
                tmp_path,
                analysis=_analysis_result(tmp_path, repo_name="alpha"),
                context=_context(repo_name="beta"),
            )
        )


def test_invalid_recommendation_reference_rejection(tmp_path: Path) -> None:
    with pytest.raises(ModernizationReportValidationError, match="related_finding_ids|resolve"):
        ModernizationHTMLReportRenderer().render(
            _report_input(tmp_path, assessment=_assessment(related_ok=False))
        )


def test_invalid_phase_reference_rejection(tmp_path: Path) -> None:
    base = _assessment()
    broken = AIRecommendationResult.model_construct(
        schema_version=base.recommendation_result.schema_version,
        executive_summary=base.recommendation_result.executive_summary,
        overall_assessment=base.recommendation_result.overall_assessment,
        key_risks=base.recommendation_result.key_risks,
        recommendations=base.recommendation_result.recommendations,
        modernization_phases=[
            ModernizationPhase.model_construct(
                phase=1,
                name="Broken",
                objective="Objective",
                recommendations=["AI-REC-999"],
                expected_outcomes=[],
            )
        ],
        evidence_coverage=base.recommendation_result.evidence_coverage,
        limitations=base.recommendation_result.limitations,
    )
    assessment = ModernizationAssessmentResult.model_construct(
        recommendation_result=broken,
        model_metadata=base.model_metadata,
        trace=base.trace,
        raw_model_response=None,
    )
    with pytest.raises(
        ModernizationReportValidationError,
        match="Phase recommendation|unknown recommendation|omit recommendation",
    ):
        ModernizationHTMLReportRenderer().render(_report_input(tmp_path, assessment=assessment))


def test_json_round_trip(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    restored = modernization_report_input_from_json(
        modernization_report_input_to_json(report_input)
    )
    assert restored.report_title == report_input.report_title
    assert restored.analysis_context.repository.name == "sample-app"
    assert restored.assessment_result.model_metadata.model_id == "test-model"


def test_file_writing(tmp_path: Path) -> None:
    output = tmp_path / "out" / "modernization.html"
    path = write_modernization_html_report(_report_input(tmp_path), output)
    assert path == output
    content = output.read_text(encoding="utf-8")
    assert "Generated by" in content and "CodeStrata" in content


def test_no_external_assets_or_scripts(tmp_path: Path) -> None:
    html = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    lowered = html.lower()
    assert "<script" not in lowered
    assert "onclick=" not in lowered
    assert "onerror=" not in lowered
    assert "<link " not in lowered
    assert "cdn." not in lowered
    assert "@import" not in lowered
    assert 'src="http' not in lowered


def test_frozen_input_contract(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    with pytest.raises(ValidationError):
        report_input.report_title = "Changed"
    with pytest.raises(ValidationError):
        ModernizationReportInput(
            analysis_result=_analysis_result(tmp_path),
            assessment_mode=AssessmentMode.AI_ENHANCED,
            analysis_context=_context(),
            assessment_result=_assessment(),
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
            unexpected=True,  # type: ignore[call-arg]
        )
