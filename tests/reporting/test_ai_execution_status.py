"""Tests for AI execution lifecycle status, diagnostics, and report semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import AIResponseValidationError
from codestrata.ai.providers.models import (
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.reporters.report_paths import create_report_paths
from codestrata.reporting import (
    AIAttemptInfo,
    AIExecutionStage,
    AIExecutionStatus,
    AssessmentMode,
    AssessmentTiming,
    ModernizationHTMLReportRenderer,
    ModernizationReportInput,
    build_assessment_json_document,
    write_modernization_assessment_reports,
)
from codestrata.reporting.ai_execution import (
    AI_EXECUTION_FILENAME,
    build_ai_execution_document,
    write_ai_execution_artifact,
)
from codestrata.reporting.ai_status import (
    AI_FAILURE_CODE_VALIDATION,
    assessment_mode_display_label,
    customer_failure_message,
    stages_for_status,
)
from tests.reporting.test_assessment_json import _analysis_result, _assessment, _context
from tests.test_assess_cli import _run


def _validation_failed_input(tmp_path: Path) -> ModernizationReportInput:
    attempt = AIAttemptInfo(
        provider="bedrock",
        model_id="amazon.nova-lite-v1:0",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        latency_ms=850.5,
        stop_reason="end_turn",
        stages_completed=stages_for_status(AIExecutionStatus.VALIDATION_FAILED),
        failure_code=AI_FAILURE_CODE_VALIDATION,
        failure_detail=(
            "1 validation error for AIRecommendationResult\n"
            "modernization_phases.0.recommendation_ids\n"
            "  Value error, unknown recommendation id 'REC-999'"
        ),
    )
    return ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=_context(),
        assessment_result=None,
        ai_status=AIExecutionStatus.VALIDATION_FAILED,
        ai_failure_message=customer_failure_message(AIExecutionStatus.VALIDATION_FAILED),
        ai_attempt=attempt,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        warnings=(
            "AI response failed contract validation. Deterministic results were retained. "
            "[AI_VALIDATION_FAILED] Deterministic HTML and JSON reports were still written.",
        ),
        timing=AssessmentTiming(total_ms=1000.0, ai_ms=850.5),
    )


def test_ai_not_requested_status_and_html(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        ai_status=AIExecutionStatus.NOT_REQUESTED,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    assert document["assessment"]["ai"]["status"] == "not_requested"
    assert document["assessment"]["ai"]["executed"] is False
    assert document["assessment"]["ai"]["provider_invoked"] is False
    assert 'id="ai-enrichment"' not in html
    assert 'id="ai-enrichment"' not in html
    assert "Assessment Metadata" in html


def test_validation_failure_preserves_provider_metadata_in_html_and_json(
    tmp_path: Path,
) -> None:
    report_input = _validation_failed_input(tmp_path)
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    ai = document["assessment"]["ai"]

    assert ai["status"] == "validation_failed"
    assert ai["executed"] is False
    assert ai["result_included"] is False
    assert ai["provider_invoked"] is True
    assert ai["fallback_used"] is True
    assert ai["provider"] == "bedrock"
    assert ai["model_id"] == "amazon.nova-lite-v1:0"
    assert ai["input_tokens"] == 120
    assert ai["output_tokens"] == 80
    assert ai["total_tokens"] == 200
    assert ai["latency_ms"] == 850.5
    assert ai["stop_reason"] == "end_turn"
    assert ai["failure_code"] == "AI_VALIDATION_FAILED"
    assert "contract validation" in (ai["failure_message"] or "").lower()
    assert "unknown recommendation id" in (ai["failure_detail"] or "")
    assert "response_parsed" in ai["stages_completed"]
    assert "fallback_used" in ai["stages_completed"]

    assert assessment_mode_display_label(report_input) == (
        "Deterministic fallback after AI validation failure"
    )
    assert "Deterministic fallback after AI validation failure" in html
    assert 'id="ai-enrichment"' not in html
    assert "validation_failed" in html
    assert "amazon.nova-lite-v1:0" in html
    assert "AI response failed contract validation" in html
    assert "Deterministic results were retained" in html
    assert "Warnings" in html


def test_validation_failure_writes_execution_artifact_without_credentials(tmp_path: Path) -> None:
    attempt = AIAttemptInfo(
        provider="bedrock",
        model_id="amazon.nova-lite-v1:0",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        latency_ms=100.0,
        stop_reason="end_turn",
        stages_completed=stages_for_status(AIExecutionStatus.VALIDATION_FAILED),
        failure_code=AI_FAILURE_CODE_VALIDATION,
        failure_detail="unknown recommendation id REC-999",
    )
    document = build_ai_execution_document(
        status=AIExecutionStatus.VALIDATION_FAILED,
        attempt=attempt,
        raw_model_text='{"recommendations":[{"recommendation_id":"AI-REC-001"}]}',
        parsed_model_response={
            "recommendations": [{"recommendation_id": "AI-REC-001"}],
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "authorization": "Bearer secret",
        },
        accepted_ai_result=None,
        failure_message=customer_failure_message(AIExecutionStatus.VALIDATION_FAILED),
        failure_detail="unknown recommendation id REC-999",
        timestamp=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    path = write_ai_execution_artifact(tmp_path, document)
    assert path.name == AI_EXECUTION_FILENAME
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["artifact"] == "advisor-execution"
    assert loaded["schema_version"] == "1.0.0"
    assert loaded["execution_status"] == "validation_failed"
    assert loaded["raw_model_text"].startswith('{"recommendations"')
    assert loaded["parsed_model_response"]["recommendations"][0]["recommendation_id"] == (
        "AI-REC-001"
    )
    assert loaded["accepted_ai_result"] is None
    assert "aws_access_key_id" not in loaded["parsed_model_response"]
    assert "authorization" not in loaded["parsed_model_response"]
    assert "credential" not in json.dumps(loaded).lower()
    assert loaded["failure"]["code"] == "AI_VALIDATION_FAILED"
    assert "REC-999" in (loaded["failure"]["detail"] or "")


def test_validation_failure_keeps_deterministic_reports(tmp_path: Path) -> None:
    report_input = _validation_failed_input(tmp_path)
    paths = create_report_paths(report_input.analysis_result, tmp_path / "out")
    written = write_modernization_assessment_reports(report_input, paths)
    assert written.html_report_path.is_file()
    assert written.json_report_path.is_file()
    html = written.html_report_path.read_text(encoding="utf-8")
    payload = json.loads(written.json_report_path.read_text(encoding="utf-8"))
    assert "Findings" in html
    assert payload["assessment"]["ai"]["recommendations"] == []
    assert payload["assessment"]["ai"]["phases"] == []
    assert 'id="ai-enrichment"' not in html


def test_parsing_and_provider_and_auth_status_labels(tmp_path: Path) -> None:
    cases = [
        (AIExecutionStatus.PARSING_FAILED, "parsing_failed", "Parsing failed"),
        (AIExecutionStatus.PROVIDER_FAILED, "provider_failed", "Provider failed"),
        (
            AIExecutionStatus.AUTHENTICATION_FAILED,
            "authentication_failed",
            "Authentication failed",
        ),
    ]
    for status, expected_status, _expected_label in cases:
        report_input = ModernizationReportInput(
            analysis_result=_analysis_result(tmp_path),
            assessment_mode=AssessmentMode.AI_ENHANCED,
            analysis_context=_context(),
            ai_status=status,
            ai_failure_message=customer_failure_message(status),
            ai_attempt=AIAttemptInfo(
                provider="bedrock",
                model_id="amazon.nova-lite-v1:0",
                stages_completed=stages_for_status(status),
                failure_code=status.value.upper(),
            ),
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        )
        html = ModernizationHTMLReportRenderer().render(report_input)
        document = build_assessment_json_document(report_input)
        assert document["assessment"]["ai"]["status"] == expected_status
        assert document["assessment"]["ai"]["executed"] is False
        assert expected_status in html
        assert 'id="ai-enrichment"' not in html


def test_successful_ai_result_status(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=_context(),
        assessment_result=_assessment(),
        ai_status=AIExecutionStatus.SUCCEEDED,
        ai_attempt=AIAttemptInfo(
            provider="fake",
            model_id="test-model",
            input_tokens=9,
            output_tokens=11,
            total_tokens=20,
            latency_ms=12.5,
            stages_completed=stages_for_status(AIExecutionStatus.SUCCEEDED),
        ),
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    assert document["assessment"]["ai"]["status"] == "succeeded"
    assert document["assessment"]["ai"]["executed"] is True
    assert document["assessment"]["ai"]["result_included"] is True
    assert "Leadership Verdict" in html
    assert "Modernization Advisor" in html or "AI status" in html
    assert 'id="ai-enrichment"' not in html


class _ValidationFailingProvider(AIModelProvider):
    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        metadata = ModelInvocationMetadata(
            provider="bedrock",
            model_id=options.model_id,
            request_id="req-diag",
            latency_ms=321.0,
            usage=ModelUsage(input_tokens=44, output_tokens=55, total_tokens=99),
            stop_reason="end_turn",
        )
        raise AIResponseValidationError(
            "Model response failed context-aware recommendation validation: "
            "unknown recommendation id REC-999",
            metadata=metadata,
            raw_response_text='{"executive_summary":"x","recommendations":[]}',
            parsed_payload={
                "executive_summary": "x",
                "recommendations": [],
                "modernization_phases": [{"phase_id": "P1", "recommendation_ids": ["AI-REC-999"]}],
            },
            validation_details="unknown recommendation id REC-999",
        )


def test_assess_validation_failure_writes_execution_artifact_and_preserves_metadata(
    tmp_path: Path,
) -> None:
    result, provider, _ = _run(
        tmp_path,
        mode=AssessmentMode.AI_ENHANCED,
        provider=_ValidationFailingProvider(),
    )
    assert result.ai_executed is False
    assert provider is not None
    html = result.html_report_path.read_text(encoding="utf-8")
    document = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    ai = document["assessment"]["ai"]
    assert ai["status"] == "validation_failed"
    assert ai["provider"] == "bedrock"
    assert ai["model_id"]
    assert ai["input_tokens"] == 44
    assert ai["output_tokens"] == 55
    assert ai["total_tokens"] == 99
    assert ai["latency_ms"] == 321.0
    assert ai["failure_code"] == "AI_VALIDATION_FAILED"
    assert "contract validation" in (ai["failure_message"] or "").lower()
    assert "REC-999" in (ai["failure_detail"] or "")
    assert ai["internal_execution_artifact"] == "advisor-execution.json"
    assert 'id="ai-enrichment"' not in html
    assert "validation_failed" in html
    assert "advisor-execution.json" not in html

    execution_path = result.run_directory / AI_EXECUTION_FILENAME
    assert execution_path.is_file()
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    assert execution["execution_status"] == "validation_failed"
    assert execution["raw_model_text"]
    phase0 = execution["parsed_model_response"]["modernization_phases"][0]
    assert phase0["recommendation_ids"] == ["AI-REC-999"]
    assert execution["accepted_ai_result"] is None
    assert "aws_access_key" not in json.dumps(execution).lower()
    assert "authorization" not in json.dumps(execution).lower()


def test_stages_for_validation_failure() -> None:
    stages = stages_for_status(AIExecutionStatus.VALIDATION_FAILED)
    assert AIExecutionStage.REQUESTED in stages
    assert AIExecutionStage.PROVIDER_INVOKED in stages
    assert AIExecutionStage.RESPONSE_RECEIVED in stages
    assert AIExecutionStage.RESPONSE_PARSED in stages
    assert AIExecutionStage.FALLBACK_USED in stages
    assert AIExecutionStage.RESULT_INCLUDED not in stages
