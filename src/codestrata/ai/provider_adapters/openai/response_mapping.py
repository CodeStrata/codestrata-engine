"""Map an OpenAI Chat Completions response onto an ``AIProviderResult``.

Field reads happen in the same order, and with the same tolerance, as the
pre-migration ``openai_provider._extract_chat_response``: first
``choices[0].message.content`` (a non-blank string is required), then
``usage``, then ``finish_reason`` and the response ``id``. Any attribute
error while reading is a bounded ``invalid_response`` failure rather than an
exception, so ``AIProvider.execute()`` can stay non-raising (CR-3).

``request_id``/``stop_reason`` are not fields on ``AIProviderResult`` — the
contract deliberately keeps provider request IDs out of results and usage
records. They are still needed to populate the legacy
``ModelInvocationMetadata`` that ``codestrata assess`` reports today, so they
travel on :class:`OpenAIInvocationDetail`, a bridge-only value passed to the
adapter's detail sink. Nothing places an ``OpenAIInvocationDetail`` inside an
``AIProviderResult``, a diagnostic view, or a verification report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_adapters.openai import error_mapping, usage_mapping
from codestrata.ai.provider_contracts.errors import AIProviderError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.usage import UsageCompletionStatus

# Mirrors responses.AIProviderResultContent's own ceiling. Checked here first
# so an implausibly large response degrades into a bounded invalid_response
# failure instead of a ProviderContractValidationError escaping execute().
MAX_RESPONSE_TEXT_LENGTH = 2_000_000

_OVERSIZED_RESPONSE_DETAIL = "OpenAI response text exceeded the maximum supported length"

_COMPLETION_STATUS_BY_EXECUTION_STATUS: dict[ProviderExecutionStatus, UsageCompletionStatus] = {
    ProviderExecutionStatus.SUCCESS: UsageCompletionStatus.SUCCESS,
    ProviderExecutionStatus.FAILED: UsageCompletionStatus.FAILED,
    ProviderExecutionStatus.UNAVAILABLE: UsageCompletionStatus.UNAVAILABLE,
    ProviderExecutionStatus.SKIPPED: UsageCompletionStatus.SKIPPED,
}


@dataclass(frozen=True, slots=True)
class ExtractedChatResponse:
    """The fields read off a successful Chat Completions response."""

    text: str
    stop_reason: str | None
    request_id: str | None
    usage_object: Any


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    """Either the extracted response fields or a bounded reason extraction failed."""

    extracted: ExtractedChatResponse | None = None
    failure: error_mapping.MappedFailure | None = None

    @property
    def ok(self) -> bool:
        return self.extracted is not None


@dataclass(frozen=True, slots=True)
class OpenAIInvocationDetail:
    """Bridge-only per-invocation details the legacy result contract needs.

    Deliberately not part of any ``AIProviderResult``: ``request_id`` is a
    provider-issued identifier and ``legacy_error_detail`` is sanitized
    exception text, neither of which the contract permits in a result, a
    diagnostic view, or a report.
    """

    latency_ms: float
    request_id: str | None = None
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error_code: str | None = None
    legacy_error_detail: str = ""


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def extract_chat_response(response: Any) -> ExtractionOutcome:
    """Read the assistant text, usage, stop reason, and request ID off ``response``."""

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
                    error=error_mapping.build_error(error_mapping.CODE_UNREADABLE_RESPONSE),
                    legacy_detail=_OVERSIZED_RESPONSE_DETAIL,
                )
            )
        usage_object = getattr(response, "usage", None)
        stop_reason = _optional_str(getattr(choice, "finish_reason", None))
        request_id = _optional_str(getattr(response, "id", None))
    except Exception as error:  # noqa: BLE001 - provider response boundary
        return ExtractionOutcome(failure=error_mapping.classify_unreadable_response(error))

    return ExtractionOutcome(
        extracted=ExtractedChatResponse(
            text=content,
            stop_reason=stop_reason,
            request_id=request_id,
            usage_object=usage_object,
        )
    )


def decode_structured_payload(text: str) -> dict[str, object] | None:
    """Decode ``text`` as a JSON object, or return ``None`` when it is not one.

    A decode failure is never an error: the pre-migration provider returned
    raw text and let the caller decide how to parse it, and that division of
    responsibility is preserved.
    """

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
) -> tuple[AIProviderResult, OpenAIInvocationDetail]:
    """Build the SUCCESS result plus the bridge-only invocation detail."""

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
    detail = OpenAIInvocationDetail(
        latency_ms=latency_ms,
        request_id=extracted.request_id,
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
) -> tuple[AIProviderResult, OpenAIInvocationDetail]:
    """Build a FAILED/UNAVAILABLE result plus the bridge-only invocation detail."""

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
    detail = OpenAIInvocationDetail(
        latency_ms=latency_ms,
        error_code=error.code,
        legacy_error_detail=failure.legacy_detail,
    )
    return result, detail


__all__ = [
    "MAX_RESPONSE_TEXT_LENGTH",
    "ExtractedChatResponse",
    "ExtractionOutcome",
    "OpenAIInvocationDetail",
    "build_failure_result",
    "build_success_result",
    "decode_structured_payload",
    "extract_chat_response",
]
