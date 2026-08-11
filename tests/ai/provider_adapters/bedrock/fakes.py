"""In-memory Bedrock Converse doubles. No AWS, credentials, or network."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)

DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
ENRICHMENT_TEXT = (
    '{"executive_summary": {"headline": "H", "narrative": "N"}, "themes": []}'
)


class Client:
    """Minimal ``converse(**kwargs)`` surface the adapter uses."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._outcome = converse_response() if outcome is None else outcome
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def converse_response(
    text: Any = ENRICHMENT_TEXT,
    *,
    input_tokens: int | None = 11,
    output_tokens: int | None = 22,
    total_tokens: int | None = None,
    stop_reason: str | None = "end_turn",
    request_id: str | None = "synthetic-request-id",
    latency_ms: float | None = None,
    include_usage: bool = True,
) -> dict[str, Any]:
    blocks = [{"text": item} for item in ([text] if isinstance(text, str) else text)]
    response: dict[str, Any] = {
        "output": {"message": {"role": "assistant", "content": blocks}},
    }
    if stop_reason is not None:
        response["stopReason"] = stop_reason
    if request_id is not None:
        response["ResponseMetadata"] = {"RequestId": request_id}
    if include_usage:
        usage: dict[str, Any] = {}
        if input_tokens is not None:
            usage["inputTokens"] = input_tokens
        if output_tokens is not None:
            usage["outputTokens"] = output_tokens
        if total_tokens is not None:
            usage["totalTokens"] = total_tokens
        response["usage"] = usage
    if latency_ms is not None:
        response["metrics"] = {"latencyMs": latency_ms}
    return response


def named_exception(class_name: str, message: str = "synthetic failure") -> Exception:
    return type(class_name, (Exception,), {})(message)


def client_error(code: str, message: str = "synthetic failure") -> Exception:
    error = type("ClientError", (Exception,), {})(message)
    error.response = {  # type: ignore[attr-defined]
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"RequestId": "synthetic-error-request-id"},
    }
    return error


def provider_request(
    *,
    model_id: str = DEFAULT_MODEL_ID,
    response_expectation: ResponseExpectation = ResponseExpectation.STRUCTURED_JSON,
    temperature: float = 0.0,
    max_tokens: int = 5000,
) -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="Synthetic instruction.",
            context_payload_text='{"synthetic": true}',
        ),
        response_expectation=response_expectation,
        model_reference=ProviderModelReference(value=model_id),
        execution_options=ExecutionOptions(
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=60.0,
        ),
    )
