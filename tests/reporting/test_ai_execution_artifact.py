"""Tests for the internal advisor-execution.json artifact."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderInvocationError,
    AIResponseParsingError,
)
from codestrata.ai.providers.models import (
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.ai.recommendations.validation import DeterministicRecommendationNormalizationRemoval
from codestrata.reporting.ai_execution import (
    AI_EXECUTION_FILENAME,
    build_ai_execution_document,
    try_write_ai_execution_artifact,
    write_ai_execution_artifact,
)
from codestrata.reporting.ai_status import stages_for_status
from codestrata.reporting.modernization_models import (
    AIAttemptInfo,
    AIExecutionStatus,
    AssessmentMode,
)
from tests.test_assess_cli import FakeProvider, RecordingConsole, _recommendation_result, _run


class _ParsingFailingProvider(AIModelProvider):
    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        metadata = ModelInvocationMetadata(
            provider="bedrock",
            model_id=options.model_id,
            request_id="req-parse",
            latency_ms=10.0,
            usage=ModelUsage(input_tokens=1, output_tokens=2, total_tokens=3),
            stop_reason="end_turn",
        )
        raise AIResponseParsingError(
            "Model response is not valid JSON",
            metadata=metadata,
            raw_response_text="{not-json",
            parsed_payload=None,
        )


class _ProviderFailingProvider(AIModelProvider):
    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        raise AIProviderInvocationError("temporary service failure")


def test_successful_ai_invocation_creates_execution_artifact(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.AI_ENHANCED, provider=FakeProvider())
    path = result.run_directory / AI_EXECUTION_FILENAME
    assert path.is_file()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["artifact"] == "advisor-execution"
    assert document["schema_version"] == "1.0.0"
    assert document["execution_status"] == "succeeded"
    assert document["failure"] is None
    assert document["raw_model_text"]
    assert document["parsed_model_response"] is not None
    assert document["accepted_ai_result"] is not None
    assert document["authoritative_evidence_coverage"] is not None
    report_json = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert report_json["assessment"]["ai"]["internal_execution_artifact"] == AI_EXECUTION_FILENAME
    html = result.html_report_path.read_text(encoding="utf-8")
    assert "advisor-execution.json" not in html
    assert "internal_execution_artifact" not in html


def test_deterministic_only_run_does_not_create_execution_artifact(tmp_path: Path) -> None:
    result, _, _ = _run(tmp_path, mode=AssessmentMode.DETERMINISTIC, model_id=None)
    assert not (result.run_directory / AI_EXECUTION_FILENAME).exists()
    report_json = json.loads(result.json_report_path.read_text(encoding="utf-8"))
    assert report_json["assessment"]["ai"].get("internal_execution_artifact") in {None, ""}


def test_provider_failure_creates_execution_artifact(tmp_path: Path) -> None:
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.AI_ENHANCED,
        provider=_ProviderFailingProvider(),
    )
    path = result.run_directory / AI_EXECUTION_FILENAME
    assert path.is_file()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["execution_status"] == "provider_failed"
    assert document["accepted_ai_result"] is None
    assert document["failure"]["stage"] == "provider"


def test_parsing_failure_preserves_raw_and_null_parsed(tmp_path: Path) -> None:
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.AI_ENHANCED,
        provider=_ParsingFailingProvider(),
    )
    execution_path = result.run_directory / AI_EXECUTION_FILENAME
    document = json.loads(execution_path.read_text(encoding="utf-8"))
    assert document["execution_status"] == "parsing_failed"
    assert document["raw_model_text"] == "{not-json"
    assert document["parsed_model_response"] is None
    assert document["accepted_ai_result"] is None


def test_success_preserves_raw_parsed_and_accepted_layers() -> None:
    accepted = _recommendation_result()
    model_coverage = {
        "total_findings": 99,
        "findings_considered": 1,
        "findings_referenced": 0,
        "coverage_percentage": 0.0,
        "input_truncated": False,
    }
    parsed = accepted.model_dump(mode="json")
    parsed["evidence_coverage"] = model_coverage
    attempt = AIAttemptInfo(
        provider="fake",
        model_id="test-model",
        input_tokens=9,
        output_tokens=11,
        total_tokens=20,
        latency_ms=12.5,
        stop_reason="end_turn",
        stages_completed=stages_for_status(AIExecutionStatus.SUCCEEDED),
    )
    document = build_ai_execution_document(
        status=AIExecutionStatus.SUCCEEDED,
        attempt=attempt,
        raw_model_text=json.dumps(parsed),
        parsed_model_response=parsed,
        accepted_ai_result=accepted,
        timestamp=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    assert document["parsed_model_response"]["evidence_coverage"]["total_findings"] == 99
    assert document["accepted_ai_result"]["evidence_coverage"] == (
        accepted.evidence_coverage.model_dump(mode="json")
    )
    assert document["authoritative_evidence_coverage"] == (
        accepted.evidence_coverage.model_dump(mode="json")
    )
    assert document["normalization"] is None


def test_normalization_metadata_present_when_det_refs_removed() -> None:
    accepted = _recommendation_result()
    document = build_ai_execution_document(
        status=AIExecutionStatus.SUCCEEDED,
        attempt=AIAttemptInfo(
            provider="fake",
            model_id="test-model",
            stages_completed=stages_for_status(AIExecutionStatus.SUCCEEDED),
        ),
        accepted_ai_result=accepted,
        normalization_removals=(
            DeterministicRecommendationNormalizationRemoval(
                recommendation_id="AI-REC-001",
                removed_ids=("REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN",),
            ),
        ),
        timestamp=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    assert document["normalization"]["removed_unknown_deterministic_recommendation_ids"] == [
        {
            "recommendation_id": "AI-REC-001",
            "removed_ids": ["REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN"],
        }
    ]


def test_execution_artifact_write_failure_warns_but_does_not_fail_assessment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "codestrata.application.assessment.service.try_write_ai_execution_artifact",
        lambda *_a, **_k: None,
    )
    console = RecordingConsole()
    result, _, _ = _run(
        tmp_path,
        mode=AssessmentMode.AI_ENHANCED,
        provider=FakeProvider(),
        console=console,
    )
    assert result.html_report_path.is_file()
    assert result.json_report_path.is_file()
    assert result.ai_executed is True
    joined = "\n".join(console.messages)
    assert "AI execution artifact could not be written" in joined


def test_json_output_is_deterministic(tmp_path: Path) -> None:
    attempt = AIAttemptInfo(
        provider="fake",
        model_id="test-model",
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
        latency_ms=4.0,
        stop_reason="end_turn",
        stages_completed=stages_for_status(AIExecutionStatus.SUCCEEDED),
    )
    accepted = _recommendation_result()
    first = build_ai_execution_document(
        status=AIExecutionStatus.SUCCEEDED,
        attempt=attempt,
        raw_model_text="{}",
        parsed_model_response={"ok": True},
        accepted_ai_result=accepted,
        timestamp=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    second = build_ai_execution_document(
        status=AIExecutionStatus.SUCCEEDED,
        attempt=attempt,
        raw_model_text="{}",
        parsed_model_response={"ok": True},
        accepted_ai_result=accepted,
        timestamp=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    path_a = write_ai_execution_artifact(tmp_path / "a", first)
    path_b = write_ai_execution_artifact(tmp_path / "b", second)
    assert path_a.read_text(encoding="utf-8") == path_b.read_text(encoding="utf-8")


def test_try_write_returns_none_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "codestrata.reporting.ai_execution.write_ai_execution_artifact",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    assert try_write_ai_execution_artifact(tmp_path, {"artifact": "advisor-execution"}) is None
