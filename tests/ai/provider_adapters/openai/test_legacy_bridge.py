"""Legacy bridge: same folding in, same legacy exception types and messages out."""

from __future__ import annotations

import pytest

from codestrata.ai.prompts.models import PromptMessage
from codestrata.ai.provider_adapters.openai import error_mapping, legacy_bridge
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
)
from codestrata.ai.providers.models import ModelInvocationOptions
from tests.ai.provider_adapters.openai import fakes


def test_folding_splits_instructions_from_context() -> None:
    payload = legacy_bridge.fold_prompt_request(fakes.prompt_request())

    assert isinstance(payload, ModernizationAdvisorInput)
    assert payload.instruction_text == (
        "System rules.\n\nDeveloper instructions:\nDeveloper rules."
    )
    assert payload.context_payload_text == '{"findings": []}'


def test_folding_does_not_add_the_json_instruction() -> None:
    """The JSON trailer is an OpenAI wire concern owned by ``request_mapping``."""

    payload = legacy_bridge.fold_prompt_request(fakes.prompt_request())

    assert "Respond with a single JSON object" not in payload.instruction_text


def test_multiple_user_messages_are_joined_in_order() -> None:
    request = fakes.prompt_request(
        extra_messages=[PromptMessage(role="user", content="second block")]
    )

    payload = legacy_bridge.fold_prompt_request(request)

    assert payload.context_payload_text == '{"findings": []}\n\nsecond block'


def test_prompt_without_a_user_message_raises_the_legacy_configuration_error() -> None:
    with pytest.raises(AIProviderConfigurationError) as caught:
        legacy_bridge.fold_prompt_request(fakes.prompt_request(user=None))

    assert "at least one user message" in str(caught.value)


def test_prompt_without_instructions_falls_back_to_the_json_instruction() -> None:
    payload = legacy_bridge.fold_prompt_request(
        fakes.prompt_request(system=None, developer=None)
    )

    assert payload.instruction_text == legacy_bridge.INSTRUCTION_TEXT_FALLBACK


def test_execution_options_carry_the_legacy_invocation_options() -> None:
    options = ModelInvocationOptions(
        model_id="gpt-4o-mini",
        temperature=0.2,
        max_output_tokens=1024,
        timeout_seconds=30.0,
    )

    mapped = legacy_bridge.build_execution_options(options)

    assert mapped.temperature == 0.2
    assert mapped.max_tokens == 1024
    assert mapped.timeout_seconds == 30.0


def test_provider_request_targets_the_modernization_advisor_capability() -> None:
    request = legacy_bridge.build_provider_request(
        fakes.prompt_request(),
        ModelInvocationOptions(model_id="gpt-4o-mini", max_output_tokens=2048),
        model_id="gpt-4o-mini",
    )

    assert request.capability is CapabilityId.MODERNIZATION_ADVISOR
    assert request.response_expectation is ResponseExpectation.STRUCTURED_JSON
    assert request.model_reference.value == "gpt-4o-mini"


def test_metadata_reports_provider_model_usage_and_latency() -> None:
    detail = fakes.invocation_detail(
        latency_ms=125.0,
        request_id="chatcmpl-3",
        stop_reason="stop",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
    )

    metadata = legacy_bridge.build_model_invocation_metadata(
        model_id="gpt-4o-mini", detail=detail
    )

    assert metadata.provider == "openai"
    assert metadata.model_id == "gpt-4o-mini"
    assert metadata.request_id == "chatcmpl-3"
    assert metadata.latency_ms == 125.0
    assert metadata.stop_reason == "stop"
    assert metadata.usage.input_tokens == 10
    assert metadata.usage.total_tokens == 30


def test_caller_supplied_request_id_overrides_the_provider_one() -> None:
    detail = fakes.invocation_detail(request_id="chatcmpl-3")

    metadata = legacy_bridge.build_model_invocation_metadata(
        model_id="gpt-4o-mini", detail=detail, request_id_override="caller-req-1"
    )

    assert metadata.request_id == "caller-req-1"


def test_inconsistent_provider_token_triple_is_reported_verbatim() -> None:
    """The contract usage type drops an inconsistent total; the legacy report must not."""

    detail = fakes.invocation_detail(input_tokens=10, output_tokens=20, total_tokens=999)

    metadata = legacy_bridge.build_model_invocation_metadata(
        model_id="gpt-4o-mini", detail=detail
    )

    assert metadata.usage.total_tokens == 999


_EXPECTED_LEGACY_EXCEPTIONS = {
    error_mapping.CODE_MISSING_DEPENDENCY: AIProviderConfigurationError,
    error_mapping.CODE_MISSING_API_KEY: AIProviderConfigurationError,
    error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED: AIProviderConfigurationError,
    error_mapping.CODE_AUTHENTICATION_FAILED: AIProviderInvocationError,
    error_mapping.CODE_AUTHORIZATION_FAILED: AIProviderInvocationError,
    error_mapping.CODE_INVALID_MODEL: AIProviderInvocationError,
    error_mapping.CODE_INVALID_REQUEST: AIProviderInvocationError,
    error_mapping.CODE_TIMEOUT: AIProviderTimeoutError,
    error_mapping.CODE_RATE_LIMITED: AIProviderTimeoutError,
    error_mapping.CODE_PROVIDER_UNAVAILABLE: AIProviderTimeoutError,
    error_mapping.CODE_EMPTY_RESPONSE: AIProviderInvocationError,
    error_mapping.CODE_UNREADABLE_RESPONSE: AIProviderInvocationError,
    error_mapping.CODE_PARSING_FAILED: AIProviderInvocationError,
    error_mapping.CODE_PROMPT_MAPPING_FAILED: AIProviderInvocationError,
    error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE: AIProviderInvocationError,
}


@pytest.mark.parametrize("code", sorted(_EXPECTED_LEGACY_EXCEPTIONS))
def test_every_code_maps_to_the_legacy_exception_type_it_used_to_raise(code: str) -> None:
    error = legacy_bridge.legacy_error_for(error_mapping.build_error(code), legacy_detail="detail")

    assert type(error) is _EXPECTED_LEGACY_EXCEPTIONS[code]


def test_every_error_code_is_covered_by_the_legacy_mapping() -> None:
    assert set(error_mapping.CATEGORY_BY_CODE) <= set(_EXPECTED_LEGACY_EXCEPTIONS)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (
            error_mapping.CODE_MISSING_DEPENDENCY,
            "OpenAI provider requires the optional 'openai' extra. "
            "Install with: pip install 'codestrata[openai]'",
        ),
        (
            error_mapping.CODE_AUTHENTICATION_FAILED,
            "OpenAI authentication failed. Verify API key and model access. Details: boom",
        ),
        (error_mapping.CODE_TIMEOUT, "OpenAI temporary service failure: boom"),
        (
            error_mapping.CODE_INVALID_MODEL,
            "OpenAI invalid model or request configuration: boom",
        ),
        (error_mapping.CODE_EMPTY_RESPONSE, "OpenAI response did not include assistant text"),
        (
            error_mapping.CODE_UNREADABLE_RESPONSE,
            "Failed to read OpenAI chat response: boom",
        ),
        (error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED, "Failed to configure OpenAI client: boom"),
        (error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE, "OpenAI invocation failed: boom"),
    ],
)
def test_legacy_messages_are_reproduced_verbatim(code: str, expected: str) -> None:
    error = legacy_bridge.legacy_error_for(error_mapping.build_error(code), legacy_detail="boom")

    assert str(error) == expected


def test_missing_key_message_names_the_environment_variable_not_its_value() -> None:
    error = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY),
        api_key_env_name="MY_KEY_VAR",
    )

    assert str(error) == "OpenAI API key not found in environment variable MY_KEY_VAR"


def test_missing_key_message_defaults_to_the_standard_variable_name() -> None:
    error = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY)
    )

    assert "OPENAI_API_KEY" in str(error)
