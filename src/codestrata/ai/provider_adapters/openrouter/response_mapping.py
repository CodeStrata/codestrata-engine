"""Map an OpenAI-compatible Chat Completions response onto AIProviderResult."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_adapters.openrouter import error_mapping, usage_mapping
from codestrata.ai.provider_contracts.errors import AIProviderError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.usage import UsageCompletionStatus

MAX_RESPONSE_TEXT_LENGTH = 2_000_000

_COMPLETION_STATUS_BY_EXECUTION_STATUS: dict[ProviderExecutionStatus, UsageCompletionStatus] = {
    ProviderExecutionStatus.SUCCESS: UsageCompletionStatus.SUCCESS,
    ProviderExecutionStatus.FAILED: UsageCompletionStatus.FAILED,
    ProviderExecutionStatus.UNAVAILABLE: UsageCompletionStatus.UNAVAILABLE,
    ProviderExecutionStatus.SKIPPED: UsageCompletionStatus.SKIPPED,
}


@dataclass(frozen=True, slots=True)
class ExtractedChatResponse:
    text: str
    stop_reason: str | None
    usage_object: Any


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    extracted: ExtractedChatResponse | None = None
    failure: error_mapping.MappedFailure | None = None

    @property
    def ok(self) -> bool:
        return self.extracted is not None


@dataclass(frozen=True, slots=True)
class OpenRouterInvocationDetail:
    """Private per-invocation detail — never placed on AIProviderResult."""

    latency_ms: float
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error_code: str | None = None
    legacy_error_detail: str = ""


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def extract_chat_response(response: Any) -> ExtractionOutcome:
    try:
        choice = response.choices[0]
        content = choice.message.content
        if not isinstance(content, str) or not content.strip():
            return ExtractionOutcome(
                failure=error_mapping.MappedFailure(
                    error=error_mapping.build_error(error_mapping.CODE_EMPTY_RESPONSE)
                )
            )
        if len(content) > MAX_RESPONSE_TEXT_LENGTH:
            return ExtractionOutcome(
                failure=error_mapping.MappedFailure(
                    error=error_mapping.build_error(error_mapping.CODE_UNREADABLE_RESPONSE)
                )
            )
        # Intentionally ignore response.id / routing / upstream provider metadata.
        usage_object = getattr(response, "usage", None)
        stop_reason = _optional_str(getattr(choice, "finish_reason", None))
    except Exception as error:  # noqa: BLE001
        return ExtractionOutcome(failure=error_mapping.classify_unreadable_response(error))

    return ExtractionOutcome(
        extracted=ExtractedChatResponse(
            text=content,
            stop_reason=stop_reason,
            usage_object=usage_object,
        )
    )


def decode_structured_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def build_success_result(
    *,
    provider_id: ProviderId,
    capability: CapabilityId,
    response_expectation: ResponseExpectation,
    extracted: ExtractedChatResponse,
    latency_ms: float,
    retry_count: int = 0,
    limitations: tuple[str, ...] = (),
) -> tuple[AIProviderResult, OpenRouterInvocationDetail]:
    mapped_usage = usage_mapping.map_usage(
        extracted.usage_object,
        latency_ms=latency_ms,
        completion_status=UsageCompletionStatus.SUCCESS,
        retry_count=retry_count,
    )
    structured_payload = (
        decode_structured_payload(extracted.text)
        if response_expectation is ResponseExpectation.STRUCTURED_JSON
        else None
    )
    result = AIProviderResult(
        provider_id=provider_id,
        capability=capability,
        status=ProviderExecutionStatus.SUCCESS,
        content=AIProviderResultContent(
            text=extracted.text, structured_payload=structured_payload
        ),
        usage=mapped_usage.usage,
        limitations=limitations,
    )
    detail = OpenRouterInvocationDetail(
        latency_ms=latency_ms,
        stop_reason=extracted.stop_reason,
        input_tokens=mapped_usage.raw_totals.input_tokens,
        output_tokens=mapped_usage.raw_totals.output_tokens,
        total_tokens=mapped_usage.raw_totals.total_tokens,
    )
    return result, detail


def build_failure_result(
    *,
    provider_id: ProviderId,
    capability: CapabilityId,
    status: ProviderExecutionStatus,
    failure: error_mapping.MappedFailure,
    latency_ms: float,
    retry_count: int = 0,
    limitations: tuple[str, ...] = (),
) -> tuple[AIProviderResult, OpenRouterInvocationDetail]:
    error: AIProviderError = failure.error
    result = AIProviderResult(
        provider_id=provider_id,
        capability=capability,
        status=status,
        error=error,
        usage=usage_mapping.failure_usage(
            latency_ms=latency_ms,
            completion_status=_COMPLETION_STATUS_BY_EXECUTION_STATUS[status],
            retry_count=retry_count,
        ),
        limitations=limitations,
    )
    detail = OpenRouterInvocationDetail(
        latency_ms=latency_ms,
        error_code=error.code,
        legacy_error_detail=failure.legacy_detail,
    )
    return result, detail


__all__ = [
    "MAX_RESPONSE_TEXT_LENGTH",
    "ExtractedChatResponse",
    "ExtractionOutcome",
    "OpenRouterInvocationDetail",
    "build_failure_result",
    "build_success_result",
    "decode_structured_payload",
    "extract_chat_response",
]
