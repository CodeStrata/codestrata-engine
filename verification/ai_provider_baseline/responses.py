"""Characterize provider response extraction with synthetic payloads (no network)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from codestrata.ai.providers.bedrock import extract_converse_response
from codestrata.ai.providers.exceptions import AIProviderInvocationError
from codestrata.ai.providers.openai_provider import _extract_chat_response
from verification.ai_provider_baseline.models import CheckResult

_FIXTURE_BEDROCK_RESPONSE = {
    "ResponseMetadata": {"RequestId": "fixture-request-id"},
    "metrics": {"latencyMs": 123.0},
    "output": {"message": {"content": [{"text": '{"ok": true}'}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
}


def _fake_openai_response() -> SimpleNamespace:
    choice = SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(content='{"ok": true}'),
    )
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    return SimpleNamespace(choices=[choice], id="fixture-response-id", usage=usage)


def bedrock_extraction_result() -> dict[str, object]:
    text, usage, stop_reason, request_id, latency = extract_converse_response(
        _FIXTURE_BEDROCK_RESPONSE
    )
    return {
        "latency_ms": latency,
        "raw_text": text,
        "request_id": request_id,
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        },
    }


def openai_extraction_result() -> dict[str, object]:
    text, usage, stop_reason, request_id = _extract_chat_response(_fake_openai_response())
    return {
        "raw_text": text,
        "request_id": request_id,
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        },
    }


def check_bedrock_response_extraction(_source_root: Path) -> CheckResult:
    result = bedrock_extraction_result()
    ok = (
        result["raw_text"] == '{"ok": true}'
        and result["usage"] == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        and result["request_id"] == "fixture-request-id"
    )
    return CheckResult(
        name="bedrock_converse_response_extraction",
        category="responses",
        ok=ok,
        detail=f"usage={result['usage']}",
        evidence=result,
    )


def check_openai_response_extraction(_source_root: Path) -> CheckResult:
    result = openai_extraction_result()
    ok = result["raw_text"] == '{"ok": true}' and result["usage"] == {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
    }
    return CheckResult(
        name="openai_chat_response_extraction",
        category="responses",
        ok=ok,
        detail=f"usage={result['usage']}",
        evidence=result,
    )


def check_missing_content_raises_invocation_error(_source_root: Path) -> CheckResult:
    malformed = {
        "output": {"message": {"content": []}},
    }
    try:
        extract_converse_response(malformed)
    except AIProviderInvocationError:
        return CheckResult(
            name="bedrock_missing_content_raises_invocation_error",
            category="responses",
            ok=True,
            detail="AIProviderInvocationError raised for missing assistant text",
        )
    return CheckResult(
        name="bedrock_missing_content_raises_invocation_error",
        category="responses",
        ok=False,
        detail="expected AIProviderInvocationError was not raised",
    )


def build_response_matrix() -> dict[str, object]:
    return {
        "bedrock": bedrock_extraction_result(),
        "openai": openai_extraction_result(),
    }


def run_response_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_bedrock_response_extraction(source_root),
        check_openai_response_extraction(source_root),
        check_missing_content_raises_invocation_error(source_root),
    ]
    return checks, build_response_matrix()


__all__ = [
    "bedrock_extraction_result",
    "build_response_matrix",
    "check_bedrock_response_extraction",
    "check_missing_content_raises_invocation_error",
    "check_openai_response_extraction",
    "openai_extraction_result",
    "run_response_checks",
]
