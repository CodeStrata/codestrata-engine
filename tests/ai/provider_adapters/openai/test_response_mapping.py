"""Response mapping: tolerant field reads, bounded failures, no raised exceptions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from codestrata.ai.provider_adapters.openai import error_mapping, response_mapping
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.provider_contracts.serialization import serialize_result_for_diagnostics
from codestrata.ai.provider_contracts.usage import UsageCompletionStatus
from tests.ai.provider_adapters.openai import fakes

_CAPABILITY = CapabilityId.MODERNIZATION_ADVISOR


def test_extract_reads_text_usage_stop_reason_and_request_id() -> None:
    response = fakes.json_response({"a": 1}, id="chatcmpl-7")

    outcome = response_mapping.extract_chat_response(response)

    assert outcome.ok
    assert outcome.extracted is not None
    assert outcome.extracted.text == '{"a": 1}'
    assert outcome.extracted.stop_reason == "stop"
    assert outcome.extracted.request_id == "chatcmpl-7"
    assert outcome.extracted.usage_object.prompt_tokens == 10


@pytest.mark.parametrize("content", ["", "   ", "\n\t", None, 42, {"not": "a string"}])
def test_blank_or_non_string_content_is_a_bounded_empty_response_failure(content: object) -> None:
    outcome = response_mapping.extract_chat_response(fakes.text_response(content))

    assert not outcome.ok
    assert outcome.failure is not None
    assert outcome.failure.error.code == error_mapping.CODE_EMPTY_RESPONSE
    assert outcome.failure.error.category is ErrorCategory.INVALID_RESPONSE


def test_missing_choices_is_a_bounded_unreadable_failure_not_an_exception() -> None:
    outcome = response_mapping.extract_chat_response(SimpleNamespace())

    assert outcome.failure is not None
    assert outcome.failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE


def test_empty_choices_list_is_a_bounded_unreadable_failure() -> None:
    outcome = response_mapping.extract_chat_response(SimpleNamespace(choices=[]))

    assert outcome.failure is not None
    assert outcome.failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE


def test_oversized_response_degrades_instead_of_raising() -> None:
    oversized = "x" * (response_mapping.MAX_RESPONSE_TEXT_LENGTH + 1)

    outcome = response_mapping.extract_chat_response(fakes.text_response(oversized))

    assert outcome.failure is not None
    assert outcome.failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE
    assert oversized not in outcome.failure.legacy_detail


def test_missing_usage_and_finish_reason_are_tolerated() -> None:
    response = fakes.text_response("text")
    del response.usage
    response.choices[0].finish_reason = None
    response.id = None

    outcome = response_mapping.extract_chat_response(response)

    assert outcome.extracted is not None
    assert outcome.extracted.usage_object is None
    assert outcome.extracted.stop_reason is None
    assert outcome.extracted.request_id is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ("not json", None),
        ("[1, 2]", None),
        ('"a string"', None),
        ("null", None),
    ],
)
def test_decode_structured_payload_only_accepts_json_objects(
    text: str, expected: dict[str, object] | None
) -> None:
    assert response_mapping.decode_structured_payload(text) == expected


def _extracted(text: str = '{"a": 1}') -> response_mapping.ExtractedChatResponse:
    outcome = response_mapping.extract_chat_response(fakes.text_response(text))
    assert outcome.extracted is not None
    return outcome.extracted


def test_success_result_carries_text_payload_usage_and_limitations() -> None:
    result, detail = response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        extracted=_extracted(),
        latency_ms=12.5,
        limitations=("bedrock_remains_legacy",),
    )

    assert result.status is ProviderExecutionStatus.SUCCESS
    assert result.provider_id is ProviderId.OPENAI
    assert result.content is not None
    assert result.content.text == '{"a": 1}'
    assert result.content.structured_payload == {"a": 1}
    assert result.usage is not None
    assert result.usage.completion_status is UsageCompletionStatus.SUCCESS
    assert result.usage.latency_ms == 12.5
    assert result.limitations == ("bedrock_remains_legacy",)
    assert detail.latency_ms == 12.5
    assert detail.stop_reason == "stop"


def test_text_expectation_does_not_decode_a_structured_payload() -> None:
    result, _ = response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        response_expectation=ResponseExpectation.TEXT,
        extracted=_extracted(),
        latency_ms=0.0,
    )

    assert result.content is not None
    assert result.content.structured_payload is None


def test_non_json_success_text_is_returned_without_a_payload_or_error() -> None:
    result, _ = response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        extracted=_extracted("plain prose"),
        latency_ms=0.0,
    )

    assert result.status is ProviderExecutionStatus.SUCCESS
    assert result.error is None
    assert result.content is not None
    assert result.content.structured_payload is None


@pytest.mark.parametrize(
    ("status", "expected_completion"),
    [
        (ProviderExecutionStatus.FAILED, UsageCompletionStatus.FAILED),
        (ProviderExecutionStatus.UNAVAILABLE, UsageCompletionStatus.UNAVAILABLE),
    ],
)
def test_failure_result_maps_status_onto_usage_completion_status(
    status: ProviderExecutionStatus, expected_completion: UsageCompletionStatus
) -> None:
    failure = error_mapping.MappedFailure(
        error=error_mapping.build_error(error_mapping.CODE_TIMEOUT),
        legacy_detail="sanitized detail",
    )

    result, detail = response_mapping.build_failure_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        status=status,
        failure=failure,
        latency_ms=4.0,
    )

    assert result.status is status
    assert result.error is not None
    assert result.error.code == error_mapping.CODE_TIMEOUT
    assert result.content is None
    assert result.usage is not None
    assert result.usage.completion_status is expected_completion
    assert detail.error_code == error_mapping.CODE_TIMEOUT
    assert detail.legacy_error_detail == "sanitized detail"


def test_failure_result_never_carries_the_legacy_detail_into_the_result() -> None:
    failure = error_mapping.MappedFailure(
        error=error_mapping.build_error(error_mapping.CODE_AUTHENTICATION_FAILED),
        legacy_detail="Incorrect API key sk-abc",
    )

    result, _ = response_mapping.build_failure_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        status=ProviderExecutionStatus.FAILED,
        failure=failure,
        latency_ms=0.0,
    )

    assert result.error is not None
    assert "Incorrect API key" not in result.error.detail
    assert "sk-abc" not in serialize_result_for_diagnostics(result)


def test_invocation_detail_is_not_reachable_from_a_result() -> None:
    _, detail = response_mapping.build_success_result(
        provider_id=ProviderId.OPENAI,
        capability=_CAPABILITY,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        extracted=_extracted(),
        latency_ms=1.0,
    )

    assert isinstance(detail, response_mapping.OpenAIInvocationDetail)
    assert not hasattr(detail, "text")
