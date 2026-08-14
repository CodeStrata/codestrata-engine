"""The public assess-path wrapper: unchanged API, unchanged raise-based fail-soft."""

from __future__ import annotations

import inspect
import json

import pytest

from codestrata.ai.prompts import ModernizationPromptBuilder
from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.providers import openai_provider as openai_provider_module
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import (
    ModelInvocationOptions,
    ModernizationModelRequest,
)
from codestrata.ai.providers.openai_provider import (
    OPENAI_PROVIDER_NAME,
    OpenAIAIModelProvider,
)
from codestrata.ai.recommendations import ai_recommendation_result_to_json
from tests.ai.provider_adapters.openai import fakes
from tests.ai.test_ai_model_providers import _context, _valid_result

_ENRICHMENT_PAYLOAD = {
    "executive_summary": {"headline": "H", "narrative": "N"},
    "themes": [{"title": "T", "summary": "S"}],
    "priorities": [],
    "risks": [],
    "suggested_next_steps": [],
    "provider_metadata": {"provider": "openai", "model_id": "gpt-4o-mini"},
    "limitations": [],
}


def _model_request() -> ModernizationModelRequest:
    context = _context("SEC001", "SEC002")
    return ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )


def _options(**kwargs: object) -> ModelInvocationOptions:
    defaults: dict[str, object] = {
        "model_id": "gpt-4o-mini",
        "temperature": 0.0,
        "max_output_tokens": 2048,
        "timeout_seconds": 30.0,
    }
    defaults.update(kwargs)
    return ModelInvocationOptions(**defaults)  # type: ignore[arg-type]


def test_public_surface_is_unchanged() -> None:
    assert OPENAI_PROVIDER_NAME == "openai"
    assert issubclass(OpenAIAIModelProvider, AIModelProvider)
    assert list(inspect.signature(OpenAIAIModelProvider.__init__).parameters) == [
        "self",
        "settings",
        "openai_settings",
        "timeout_seconds",
        "client",
    ]


def test_successful_invocation_returns_metadata_and_raw_text() -> None:
    client = fakes.FakeClient(fakes.json_response(_ENRICHMENT_PAYLOAD, id="chatcmpl-1"))

    result = OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert result.metadata.provider == "openai"
    assert result.metadata.model_id == "gpt-4o-mini"
    assert result.metadata.request_id == "chatcmpl-1"
    assert result.metadata.usage.input_tokens == 10
    assert result.metadata.usage.output_tokens == 20
    assert result.metadata.usage.total_tokens == 30
    assert result.metadata.stop_reason == "stop"
    assert json.loads(result.raw_response_text)["executive_summary"]["headline"] == "H"


def test_enrichment_shaped_payload_short_circuits_the_recommendation_parse() -> None:
    client = fakes.FakeClient(fakes.json_response(_ENRICHMENT_PAYLOAD))

    result = OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert result.recommendation_result is None


def test_legacy_recommendation_payload_is_still_parsed() -> None:
    payload = ai_recommendation_result_to_json(_valid_result(), indent=None)
    client = fakes.FakeClient(fakes.text_response(payload))

    result = OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert result.recommendation_result is not None


def test_undecodable_response_raises_the_legacy_parsing_error_with_metadata() -> None:
    client = fakes.FakeClient(fakes.text_response("not json at all"))

    with pytest.raises(AIResponseParsingError) as caught:
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert caught.value.metadata is not None
    assert caught.value.metadata.provider == "openai"
    assert caught.value.raw_response_text == "not json at all"


def test_wrong_shaped_response_raises_the_legacy_validation_error_with_metadata() -> None:
    client = fakes.FakeClient(fakes.text_response('{"unexpected": "shape"}'))

    with pytest.raises(AIResponseValidationError) as caught:
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert caught.value.metadata is not None
    assert caught.value.metadata.provider == "openai"
    assert caught.value.raw_response_text == '{"unexpected": "shape"}'


def test_blank_model_id_raises_before_any_call() -> None:
    client = fakes.FakeClient()

    with pytest.raises(AIProviderConfigurationError):
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options(model_id="   "))

    assert client.calls == []


def test_non_positive_timeout_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match=r"timeout_seconds must be within"):
        OpenAIAIModelProvider(timeout_seconds=0)


@pytest.mark.parametrize(
    ("exception_name", "expected_type", "expected_message"),
    [
        (
            "AuthenticationError",
            AIProviderInvocationError,
            "OpenAI authentication failed. Verify API key and model access. Details: boom",
        ),
        (
            "PermissionDeniedError",
            AIProviderInvocationError,
            "OpenAI authentication failed. Verify API key and model access. Details: boom",
        ),
        ("APITimeoutError", AIProviderTimeoutError, "OpenAI temporary service failure: boom"),
        ("RateLimitError", AIProviderTimeoutError, "OpenAI temporary service failure: boom"),
        ("APIConnectionError", AIProviderTimeoutError, "OpenAI temporary service failure: boom"),
        ("InternalServerError", AIProviderTimeoutError, "OpenAI temporary service failure: boom"),
        (
            "BadRequestError",
            AIProviderInvocationError,
            "OpenAI invalid model or request configuration: boom",
        ),
        (
            "NotFoundError",
            AIProviderInvocationError,
            "OpenAI invalid model or request configuration: boom",
        ),
        (
            "UnprocessableEntityError",
            AIProviderInvocationError,
            "OpenAI invalid model or request configuration: boom",
        ),
    ],
)
def test_sdk_failures_raise_the_same_legacy_exception_and_message_as_before(
    exception_name: str, expected_type: type[Exception], expected_message: str
) -> None:
    client = fakes.FakeClient(fakes.named_exception(exception_name))

    with pytest.raises(expected_type) as caught:
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert type(caught.value) is expected_type
    assert str(caught.value) == expected_message


def test_empty_response_raises_the_legacy_invocation_error() -> None:
    client = fakes.FakeClient(fakes.text_response("   "))

    with pytest.raises(AIProviderInvocationError) as caught:
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert str(caught.value) == "OpenAI response did not include assistant text"


def test_missing_api_key_raises_the_legacy_configuration_error_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.config.settings import OpenAISettings

    monkeypatch.delenv("MY_KEY_VAR", raising=False)
    provider = OpenAIAIModelProvider(openai_settings=OpenAISettings(api_key_env="MY_KEY_VAR"))

    with pytest.raises(AIProviderConfigurationError) as caught:
        provider.invoke(_model_request(), _options())

    assert str(caught.value) == (
        "OpenAI API key not found in environment variable MY_KEY_VAR"
    )


def test_exactly_one_provider_call_is_made_per_invocation() -> None:
    client = fakes.FakeClient(fakes.named_exception("RateLimitError"))

    with pytest.raises(AIProviderTimeoutError):
        OpenAIAIModelProvider(client=client).invoke(_model_request(), _options())

    assert len(client.calls) == 1


def test_wire_kwargs_match_the_pre_migration_call_shape() -> None:
    client = fakes.FakeClient(fakes.json_response(_ENRICHMENT_PAYLOAD))

    OpenAIAIModelProvider(client=client).invoke(
        _model_request(), _options(temperature=0.3, max_output_tokens=1024)
    )

    kwargs = client.calls[0]
    assert sorted(kwargs) == [
        "max_tokens",
        "messages",
        "model",
        "response_format",
        "temperature",
    ]
    assert kwargs["temperature"] == 0.3
    assert kwargs["max_tokens"] == 1024
    assert kwargs["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in kwargs["messages"]] == ["system", "user"]
    assert kwargs["messages"][0]["content"].endswith(
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )


def test_prompt_request_is_not_mutated() -> None:
    client = fakes.FakeClient(fakes.json_response(_ENRICHMENT_PAYLOAD))
    request = _model_request()
    before = request.prompt_request.model_dump(mode="json")

    OpenAIAIModelProvider(client=client).invoke(request, _options())

    assert request.prompt_request.model_dump(mode="json") == before


def test_caller_request_id_overrides_the_provider_request_id() -> None:
    client = fakes.FakeClient(fakes.json_response(_ENRICHMENT_PAYLOAD, id="chatcmpl-1"))

    result = OpenAIAIModelProvider(client=client).invoke(
        _model_request(), _options(request_id="caller-1")
    )

    assert result.metadata.request_id == "caller-1"


def test_retained_module_helpers_stay_byte_compatible() -> None:
    """SV.11.1 characterizes these module-level helpers; they must keep working."""

    messages = openai_provider_module._chat_messages(fakes.prompt_request())
    assert [message["role"] for message in messages] == ["system", "user"]

    text, usage, stop_reason, request_id = openai_provider_module._extract_chat_response(
        fakes.text_response("hello", id="chatcmpl-2")
    )
    assert (text, stop_reason, request_id) == ("hello", "stop", "chatcmpl-2")
    assert usage.input_tokens == 10

    mapped = openai_provider_module._map_openai_exception(
        fakes.named_exception("RateLimitError")
    )
    assert isinstance(mapped, AIProviderTimeoutError)


def test_retained_extract_helper_raises_on_a_malformed_response() -> None:
    with pytest.raises(AIProviderInvocationError):
        openai_provider_module._extract_chat_response(fakes.text_response(""))


def test_wrapper_does_not_reference_the_unused_retry_helper() -> None:
    source = inspect.getsource(openai_provider_module)

    assert "retry_call" not in source


def test_module_does_not_import_the_openai_sdk_directly() -> None:
    source = inspect.getsource(openai_provider_module)

    assert "import openai" not in source


def test_error_codes_are_the_bridge_between_the_two_contracts() -> None:
    """The wrapper keys legacy exceptions off bounded codes, not exception text."""

    assert error_mapping.CODE_MISSING_API_KEY == "openai_api_key_env_not_set"
