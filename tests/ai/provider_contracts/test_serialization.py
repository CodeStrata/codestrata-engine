"""Unit tests for provider_contracts.serialization."""

from __future__ import annotations

import json

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.serialization import (
    canonical_json,
    serialize_request_for_diagnostics,
    serialize_result_for_diagnostics,
)

_SECRET_INSTRUCTION = "top secret prompt with credential sk-FAKESECRET1234567890"
_SECRET_MODEL = "internal-only-model-codename-zebra"
_SECRET_RESPONSE_TEXT = "the model said sk-FAKERESPONSESECRET000000"


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=_SECRET_INSTRUCTION, context_payload_text="ctx"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference(_SECRET_MODEL),
    )


def test_canonical_json_has_sorted_keys_and_no_extra_whitespace() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{"a":2,"b":1}'


def test_serialize_request_for_diagnostics_excludes_prompt_and_raw_model_value() -> None:
    text = serialize_request_for_diagnostics(_request())
    assert _SECRET_INSTRUCTION not in text
    assert _SECRET_MODEL not in text
    assert "ctx" not in text
    payload = json.loads(text)
    assert payload == dict(sorted(payload.items()))


def test_serialize_result_for_diagnostics_excludes_response_text() -> None:
    result = AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SUCCESS,
        content=AIProviderResultContent(text=_SECRET_RESPONSE_TEXT),
    )
    text = serialize_result_for_diagnostics(result)
    assert _SECRET_RESPONSE_TEXT not in text
    assert "has_content" in text


def test_serialize_result_for_diagnostics_excludes_error_detail_text() -> None:
    secret_detail = "provider said something we must not echo verbatim"
    result = AIProviderResult(
        provider_id=ProviderId.BEDROCK,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.FAILED,
        error=AIProviderError(
            category=ErrorCategory.INTERNAL_FAILURE, code="x", detail=secret_detail
        ),
    )
    text = serialize_result_for_diagnostics(result)
    assert secret_detail not in text


def test_serialization_contains_no_timestamp_looking_fields() -> None:
    text = serialize_request_for_diagnostics(_request())
    for token in ("timestamp", "created_at", '"date"'):
        assert token not in text
