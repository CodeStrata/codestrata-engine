"""Tests for sanitized modernization assessment JSON artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
    ASSESSMENT_JSON_SCHEMA_VERSION,
    AIExecutionStatus,
    AssessmentMode,
    AssessmentTiming,
    ModernizationReportInput,
    build_assessment_json_document,
    write_modernization_assessment_reports,
    write_modernization_json_report,
)
from codestrata.reporting.assessment_json import assessment_json_to_text
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def _truncation(count: int = 0) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=False,
        original_count=count,
        included_count=count,
    )


def _analysis_result(
    tmp_path: Path,
    *,
    repo_name: str = "sample-app",
    absolute_evidence: bool = False,
) -> AnalysisResult:
    evidence_path = (
        str(tmp_path / "workspace" / repo_name / "src" / "App.java")
        if absolute_evidence
        else "src/App.java"
    )
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
                evidence=[Evidence(file_path=evidence_path, line_number=10)],
                affected_technologies=["Java"],
            )
        ],
        static_analysis_results=[],
    )


def _context(*, repo_name: str = "sample-app") -> LLMAnalysisContext:
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name=repo_name,
            source_type="github",
            default_branch="main",
            file_count=2,
        ),
        technologies=[
            LLMTechnologyEvidence(name="Java", category="language", version="17"),
        ],
        metrics=LLMMetricsContext(
            file_count=2,
            finding_count=1,
            technology_count=1,
        ),
        findings=[
            LLMFindingEvidence(
                rule_id="SEC001",
                title="Critical finding",
                category="security",
                severity="critical",
                summary="Secret exposure risk",
                evidence=[LLMEvidenceLocation(path="src/App.java")],
                evidence_truncation=_truncation(1),
            )
        ],
        findings_truncation=_truncation(1),
    )


def _assessment() -> ModernizationAssessmentResult:
    result = AIRecommendationResult(
        executive_summary="Executive summary.",
        overall_assessment="Overall assessment.",
        key_risks=["Secret exposure"],
        recommendations=[
            AIRecommendation(
                recommendation_id="AI-REC-001",
                title="Rotate secrets",
                description="Remove secrets",
                rationale="Finding SEC001",
                priority=AIRecommendationPriority.HIGH,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.HIGH,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=["SEC001"],
                suggested_actions=["Rotate credentials"],
                dependencies=[],
            )
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Reduce risk",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Safer baseline"],
            )
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=1,
            findings_considered=1,
            findings_referenced=1,
            coverage_percentage=100.0,
        ),
        limitations=["No runtime data"],
    )
    return ModernizationAssessmentResult(
        recommendation_result=result,
        model_metadata=ModelInvocationMetadata(
            provider="fake",
            model_id="test-model",
            request_id="req-1",
            latency_ms=12.5,
            usage=ModelUsage(input_tokens=9, output_tokens=11, total_tokens=20),
            stop_reason="end_turn",
        ),
        trace=AgentExecutionTrace(
            trace_id="trace-1",
            started_at_utc=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            completed_at_utc=datetime(2026, 7, 21, 12, 1, tzinfo=UTC),
            total_latency_ms=1000.0,
            status=AgentExecutionStatus.COMPLETED,
            steps=(),
            tool_call_count=0,
            model_call_count=1,
            input_tokens=9,
            output_tokens=11,
            total_tokens=20,
        ),
        raw_model_response='{"secret":"AKIAIOSFODNN7EXAMPLE","prompt":"SYSTEM"}',
    )


def _deterministic_input(tmp_path: Path) -> ModernizationReportInput:
    return ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        repository_reference="example/sample-app",
        timing=AssessmentTiming(
            total_ms=100.0,
            scan_ms=10.0,
            analysis_ms=50.0,
            static_analysis_ms=None,
            ai_ms=None,
            report_ms=5.0,
        ),
    )


def _ai_input(tmp_path: Path) -> ModernizationReportInput:
    return ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=_context(),
        assessment_result=_assessment(),
        ai_status=AIExecutionStatus.SUCCEEDED,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        repository_reference="example/sample-app",
    )


def test_build_assessment_json_document_deterministic_shape(tmp_path: Path) -> None:
    document = build_assessment_json_document(_deterministic_input(tmp_path))
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert document["report_version"] == "1.2"
    assessment = document["assessment"]
    assert assessment["mode"] == "deterministic"
    assert assessment["summary"]["ai_executed"] is False
    assert assessment["summary"]["finding_count"] == 1
    assert assessment["summary"]["technology_count"] == 2
    assert assessment["summary"]["recommendation_count"] == 0
    assert assessment["summary"]["deterministic_recommendation_count"] == 0
    assert assessment["summary"]["ai_recommendation_count"] == 0
    assert assessment["summary"]["static_analysis_status"] == StaticAnalysisStatus.DISABLED.value
    assert "executive_summary" in assessment
    assert "repository_facts" in assessment
    assert assessment["deterministic_recommendations"] == []
    assert assessment["comparison"] is None
    ai = assessment["ai"]
    assert ai["executed"] is False
    assert ai["model_id"] is None
    assert ai["provider"] is None
    assert ai["input_tokens"] is None
    assert ai["output_tokens"] is None
    assert ai["total_tokens"] is None
    assert ai["recommendations"] == []
    assert ai["phases"] == []
    assert assessment["coverage"]["ai_interpretation"] == "not_requested"
    assert assessment["timing"]["total_ms"] == 100.0
    assert "path" not in assessment["repository"]


def test_ai_mode_includes_recommendations(tmp_path: Path) -> None:
    document = build_assessment_json_document(_ai_input(tmp_path))
    ai = document["assessment"]["ai"]
    assert ai["executed"] is True
    assert ai["model_id"] == "test-model"
    assert ai["input_tokens"] == 9
    assert ai["output_tokens"] == 11
    assert len(ai["recommendations"]) == 1
    assert ai["recommendations"][0]["recommendation_id"] == "AI-REC-001"
    assert len(ai["phases"]) == 1
    assert document["assessment"]["summary"]["recommendation_count"] == 0
    assert document["assessment"]["summary"]["ai_recommendation_count"] == 1
    assert document["assessment"]["coverage"]["ai_interpretation"] == "succeeded"


def test_no_absolute_paths_in_json(tmp_path: Path) -> None:
    analysis = _analysis_result(tmp_path, absolute_evidence=True).model_copy(
        update={
            "static_analysis_results": [
                StaticAnalysisResult(
                    provider_id="pmd",
                    provider_name="pmd",
                    status=StaticAnalysisStatus.UNAVAILABLE,
                    findings=[],
                    error_message=f"missing {tmp_path / 'bin' / 'pmd'}",
                )
            ]
        }
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        repository_reference="example/sample-app",
    )
    text = assessment_json_to_text(build_assessment_json_document(report_input))
    assert str(tmp_path) not in text
    assert str(tmp_path / "workspace" / "sample-app") not in text
    payload = json.loads(text)
    assert "path" not in payload["assessment"]["repository"]
    evidence_path = payload["assessment"]["findings"][0]["evidence"][0]["file_path"]
    assert evidence_path == "App.java"
    assert not evidence_path.startswith("/")
    sa_message = payload["assessment"]["static_analysis"]["message"]
    assert sa_message is not None
    assert str(tmp_path) not in sa_message
    assert "<path>" in sa_message


def test_write_modernization_json_report_atomic(tmp_path: Path) -> None:
    output = tmp_path / "out" / "assessment.json"
    path = write_modernization_json_report(_deterministic_input(tmp_path), output)
    assert path == output
    raw = output.read_bytes()
    assert raw.decode("utf-8").endswith("\n")
    payload = json.loads(raw)
    assert payload["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION


def test_write_modernization_assessment_reports_atomic(tmp_path: Path) -> None:
    from codestrata.reporters.report_paths import create_report_paths

    report_input = _deterministic_input(tmp_path)
    report_paths = create_report_paths(
        report_input.analysis_result,
        tmp_path / "out",
        timestamp="20260721-180000",
        create_directory=False,
    )
    written = write_modernization_assessment_reports(report_input, report_paths)
    assert written == report_paths
    assert report_paths.html_report_path.exists()
    assert report_paths.json_report_path.exists()
    assert not report_paths.text_report_path.exists()
    assert list(report_paths.run_directory.glob(".report.*.tmp")) == []
    text = report_paths.json_report_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    payload = json.loads(text)
    assert payload["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert payload["assessment"]["timing"]["report_ms"] is not None


def test_atomic_write_failure_leaves_no_final_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.reporters.report_paths import create_report_paths
    from codestrata.reporting import modernization_serialization as serialization

    report_input = _deterministic_input(tmp_path)
    report_paths = create_report_paths(
        report_input.analysis_result,
        tmp_path / "out",
        timestamp="20260721-180001",
        create_directory=False,
    )

    original_replace = serialization.os.replace
    calls = {"count": 0}

    def _failing_replace(src: object, dst: object) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated rename failure")
        return original_replace(src, dst)

    monkeypatch.setattr(serialization.os, "replace", _failing_replace)
    with pytest.raises(OSError, match="simulated rename failure"):
        write_modernization_assessment_reports(report_input, report_paths)

    assert not report_paths.html_report_path.exists()
    assert not report_paths.json_report_path.exists()
    assert not report_paths.text_report_path.exists()
    assert list(report_paths.run_directory.glob("*.tmp")) == []
    assert not report_paths.run_directory.exists() or not any(report_paths.run_directory.iterdir())


def test_schema_version_present(tmp_path: Path) -> None:
    document = build_assessment_json_document(_deterministic_input(tmp_path))
    assert document["schema_version"] == "1.2"
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_deterministic_ordering_sort_keys(tmp_path: Path) -> None:
    document = build_assessment_json_document(_deterministic_input(tmp_path))
    text = assessment_json_to_text(document)
    reloaded = json.loads(text)
    # sort_keys ensures stable key order in serialized output
    assert text.index('"assessment"') < text.index('"report_version"')
    assert text.index('"report_version"') < text.index('"schema_version"')
    names = [item["name"] for item in reloaded["assessment"]["technologies"]]
    assert names == ["Maven", "Java"]
    assert assessment_json_to_text(document) == assessment_json_to_text(document)
