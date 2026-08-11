"""Map a Bedrock Converse response onto an ``AIProviderResult``.

Field reads happen in the same order, and with the same tolerance, as the
pre-migration ``bedrock.extract_converse_response``: the response must be a
mapping, then ``output``, then ``output.message``, then
``output.message.content`` (a list), then every ``{"text": ...}`` block in
that list is concatenated (non-dict blocks and non-string/empty ``text``
values are skipped), then ``usage``, ``stopReason``,
``ResponseMetadata.RequestId``, and ``metrics.latencyMs``. Each of those four
structural checks has its own diagnostic code so ``legacy_bridge`` can
rebuild the four distinct legacy messages. Any unexpected error while reading
is a bounded ``invalid_response`` failure rather than an exception, so
``AIProvider.execute()`` can stay non-raising (CR-3).

``request_id``/``stop_reason`` are not fields on ``AIProviderResult`` — the
contract deliberately keeps provider request IDs out of results and usage
records. They are still needed to populate the legacy
``ModelInvocationMetadata`` that ``codestrata assess`` reports today, so they
travel on :class:`BedrockInvocationDetail`, a bridge-only value passed to the
adapter's detail sink. Nothing places a ``BedrockInvocationDetail`` inside an
``AIProviderResult``, a diagnostic view, or a verification report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_adapters.bedrock import error_mapping, usage_mapping
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

_OVERSIZED_RESPONSE_DETAIL = "Bedrock response text exceeded the maximum supported length"

OUTPUT_KEY = "output"
MESSAGE_KEY = "message"
CONTENT_KEY = "content"
TEXT_KEY = "text"
USAGE_KEY = "usage"
METRICS_KEY = "metrics"
STOP_REASON_KEY = "stopReason"
RESPONSE_METADATA_KEY = "ResponseMetadata"
REQUEST_ID_KEY = "RequestId"

_COMPLETION_STATUS_BY_EXECUTION_STATUS: dict[ProviderExecutionStatus, UsageCompletionStatus] = {
    ProviderExecutionStatus.SUCCESS: UsageCompletionStatus.SUCCESS,
    ProviderExecutionStatus.FAILED: UsageCompletionStatus.FAILED,
    ProviderExecutionStatus.UNAVAILABLE: UsageCompletionStatus.UNAVAILABLE,
    ProviderExecutionStatus.SKIPPED: UsageCompletionStatus.SKIPPED,
}


@dataclass(frozen=True, slots=True)
class ExtractedConverseResponse:
    """The fields read off a successful Converse response."""

    text: str
    stop_reason: str | None
    request_id: str | None
    usage_payload: Any
    reported_latency_ms: float | None


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    """Either the extracted response fields or a bounded reason extraction failed."""

    extracted: ExtractedConverseResponse | None = None
    failure: error_mapping.MappedFailure | None = None

    @property
    def ok(self) -> bool:
        return self.extracted is not None


@dataclass(frozen=True, slots=True)
class BedrockInvocationDetail:
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
    legacy_error_label: str = ""


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _structural_failure(code: str) -> ExtractionOutcome:
    return ExtractionOutcome(
        failure=error_mapping.MappedFailure(error=error_mapping.build_error(code))
    )


def extract_request_id(response: Any) -> str | None:
    """Read ``ResponseMetadata.RequestId`` off a Converse response, or ``None``."""

    if not isinstance(response, dict):
        return None
    metadata = response.get(RESPONSE_METADATA_KEY)
    if not isinstance(metadata, dict):
        return None
    return _optional_str(metadata.get(REQUEST_ID_KEY))


def extract_converse_response(response: Any) -> ExtractionOutcome:
    """Read the assistant text, usage, stop reason, request ID, and latency."""

    try:
        if not isinstance(response, dict):
            return _structural_failure(error_mapping.CODE_RESPONSE_NOT_A_MAPPING)

        output = response.get(OUTPUT_KEY)
        if not isinstance(output, dict):
            return _structural_failure(error_mapping.CODE_RESPONSE_MISSING_OUTPUT)

        message = output.get(MESSAGE_KEY)
        if not isinstance(message, dict):
            return _structural_failure(error_mapping.CODE_RESPONSE_MISSING_MESSAGE)

        content = message.get(CONTENT_KEY)
        if not isinstance(content, list):
            return _structural_failure(error_mapping.CODE_RESPONSE_MISSING_CONTENT)

        text_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get(TEXT_KEY)
            if isinstance(text, str) and text:
                text_parts.append(text)
        if not text_parts:
            return _structural_failure(error_mapping.CODE_EMPTY_RESPONSE)

        raw_text = "".join(text_parts)
        if len(raw_text) > MAX_RESPONSE_TEXT_LENGTH:
            return ExtractionOutcome(
                failure=error_mapping.MappedFailure(
                    error=error_mapping.build_error(error_mapping.CODE_UNREADABLE_RESPONSE),
                    legacy_detail=_OVERSIZED_RESPONSE_DETAIL,
                )
            )

        usage_payload = response.get(USAGE_KEY)
        stop_reason = _optional_str(response.get(STOP_REASON_KEY))
        request_id = extract_request_id(response)
        reported_latency_ms = usage_mapping.extract_reported_latency_ms(
            response.get(METRICS_KEY)
        )
    except Exception as error:  # noqa: BLE001 - provider response boundary
        return ExtractionOutcome(failure=error_mapping.classify_unreadable_response(error))

    return ExtractionOutcome(
        extracted=ExtractedConverseResponse(
            text=raw_text,
            stop_reason=stop_reason,
            request_id=request_id,
            usage_payload=usage_payload,
            reported_latency_ms=reported_latency_ms,
        )
    )


def decode_structured_payload(text: str) -> dict[str, object] | None:
    """Decode ``text`` as a JSON object, or return ``None`` when it is not one.

    A decode failure is never an error: the pre-migration provider returned
    raw text and let the caller decide how to parse it, and that division of
    responsibility is preserved. Bedrock has no native JSON mode, so a
    structured-JSON request only *asks* for an object in the prompt.
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
    extracted: ExtractedConverseResponse,
    latency_ms: float,
    retry_count: int = 0,
    limitations: tuple[str, ...] = (),
) -> tuple[AIProviderResult, BedrockInvocationDetail]:
    """Build the SUCCESS result plus the bridge-only invocation detail."""

    mapped_usage = usage_mapping.map_usage(
        extracted.usage_payload,
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
    detail = BedrockInvocationDetail(
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
) -> tuple[AIProviderResult, BedrockInvocationDetail]:
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
    detail = BedrockInvocationDetail(
        latency_ms=latency_ms,
        error_code=error.code,
        legacy_error_detail=failure.legacy_detail,
        legacy_error_label=failure.legacy_label,
    )
    return result, detail


__all__ = [
    "CONTENT_KEY",
    "MAX_RESPONSE_TEXT_LENGTH",
    "MESSAGE_KEY",
    "METRICS_KEY",
    "OUTPUT_KEY",
    "REQUEST_ID_KEY",
    "RESPONSE_METADATA_KEY",
    "STOP_REASON_KEY",
    "TEXT_KEY",
    "USAGE_KEY",
    "BedrockInvocationDetail",
    "ExtractedConverseResponse",
    "ExtractionOutcome",
    "build_failure_result",
    "build_success_result",
    "decode_structured_payload",
    "extract_converse_response",
    "extract_request_id",
]
