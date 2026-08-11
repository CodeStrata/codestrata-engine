"""The adapter itself: ``execute()`` never raises for an expected failure (CR-3)."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_adapters.openai.adapter import ADAPTER_LIMITATIONS, OpenAIProvider
from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
from codestrata.ai.provider_adapters.openai.response_mapping import OpenAIInvocationDetail
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.provider import AIProvider
from tests.ai.provider_adapters.openai import fakes


def _adapter(
    outcome: object | None = None, **kwargs: object
) -> tuple[OpenAIProvider, fakes.FakeClient, list[OpenAIInvocationDetail]]:
    client = fakes.FakeClient(outcome)
    details: list[OpenAIInvocationDetail] = []
    adapter = build_openai_provider(client=client, detail_sink=details.append, **kwargs)  # type: ignore[arg-type]
    return adapter, client, details


def test_adapter_satisfies_the_ai_provider_protocol() -> None:
    adapter, _, _ = _adapter()

    assert isinstance(adapter, AIProvider)
    assert adapter.provider_id is ProviderId.OPENAI


def test_supports_declares_the_modernization_advisor_capability() -> None:
    adapter, client, _ = _adapter()

    assert adapter.supports(CapabilityId.MODERNIZATION_ADVISOR) is True
    assert adapter.supports("modernization_advisor") is False  # type: ignore[arg-type]
    assert client.calls == []


def test_successful_execution_returns_text_payload_and_usage() -> None:
    adapter, client, details = _adapter(fakes.json_response({"headline": "H"}, id="chatcmpl-1"))

    result = adapter.execute(fakes.provider_request())

    assert result.status is ProviderExecutionStatus.SUCCESS
    assert result.content is not None
    assert result.content.structured_payload == {"headline": "H"}
    assert result.usage is not None
    assert result.usage.input_tokens == 10
    assert result.usage.request_count == 1
    assert result.usage.retry_count == 0
    assert len(client.calls) == 1
    assert details[-1].request_id == "chatcmpl-1"
    assert details[-1].stop_reason == "stop"


def test_result_carries_the_adapter_limitations() -> None:
    adapter, _, _ = _adapter()

    result = adapter.execute(fakes.provider_request())

    assert result.limitations == ADAPTER_LIMITATIONS
    assert "bedrock_remains_legacy" in result.limitations
    assert "single_attempt_by_default" in result.limitations


@pytest.mark.parametrize(
    ("exception_name", "expected_code"),
    [
        ("AuthenticationError", error_mapping.CODE_AUTHENTICATION_FAILED),
        ("PermissionDeniedError", error_mapping.CODE_AUTHORIZATION_FAILED),
        ("NotFoundError", error_mapping.CODE_INVALID_MODEL),
        ("BadRequestError", error_mapping.CODE_INVALID_REQUEST),
        ("UnprocessableEntityError", error_mapping.CODE_INVALID_REQUEST),
        ("APITimeoutError", error_mapping.CODE_TIMEOUT),
        ("RateLimitError", error_mapping.CODE_RATE_LIMITED),
        ("APIConnectionError", error_mapping.CODE_PROVIDER_UNAVAILABLE),
        ("InternalServerError", error_mapping.CODE_PROVIDER_UNAVAILABLE),
        ("SomethingElse", error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE),
    ],
)
def test_sdk_exceptions_become_failed_results_not_raises(
    exception_name: str, expected_code: str
) -> None:
    adapter, _, _ = _adapter(fakes.named_exception(exception_name))

    result = adapter.execute(fakes.provider_request())

    assert result.status is ProviderExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == expected_code
    assert result.content is None


def test_empty_assistant_text_becomes_a_failed_result() -> None:
    adapter, _, _ = _adapter(fakes.text_response("   "))

    result = adapter.execute(fakes.provider_request())

    assert result.status is ProviderExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == error_mapping.CODE_EMPTY_RESPONSE


def test_missing_api_key_is_unavailable_and_attempts_no_call() -> None:
    details: list[OpenAIInvocationDetail] = []
    adapter = build_openai_provider(
        environment_reader=lambda _name: None, detail_sink=details.append
    )

    result = adapter.execute(fakes.provider_request())

    assert result.status is ProviderExecutionStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.code == error_mapping.CODE_MISSING_API_KEY
    assert result.usage is not None
    assert result.usage.latency_ms == 0.0


def test_unsupported_capability_is_skipped_without_touching_a_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.ai.provider_adapters.openai import capabilities

    adapter, client, _ = _adapter()
    monkeypatch.setattr(capabilities, "declares_capability", lambda _capability: False)

    result = adapter.execute(fakes.provider_request())

    assert result.status is ProviderExecutionStatus.SKIPPED
    assert result.error is None
    assert client.calls == []


def test_unmappable_request_becomes_a_failed_result() -> None:
    adapter, client, _ = _adapter()
    request = fakes.provider_request()
    object.__setattr__(request, "payload", "not a payload")

    result = adapter.execute(request)

    assert result.status is ProviderExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == error_mapping.CODE_PROMPT_MAPPING_FAILED
    assert client.calls == []


def test_non_request_argument_is_a_programming_error_and_raises() -> None:
    adapter, _, _ = _adapter()

    with pytest.raises(ProviderContractValidationError):
        adapter.execute(object())  # type: ignore[arg-type]


def test_keyboard_interrupt_is_not_swallowed() -> None:
    adapter, _, _ = _adapter(KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        adapter.execute(fakes.provider_request())


def test_system_exit_is_not_swallowed() -> None:
    adapter, _, _ = _adapter(SystemExit(2))

    with pytest.raises(SystemExit):
        adapter.execute(fakes.provider_request())


def test_no_client_is_constructed_until_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    from codestrata.ai.provider_adapters.openai import client as client_module

    def exploding_resolve(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("resolve_client must not run before execute()")

    monkeypatch.setattr(client_module, "resolve_client", exploding_resolve)

    adapter = build_openai_provider()
    assert adapter.provider_id is ProviderId.OPENAI
    assert adapter.supports(CapabilityId.MODERNIZATION_ADVISOR) is True
    assert adapter.client_injected is False


def test_adapter_holds_no_per_invocation_state() -> None:
    adapter, _, details = _adapter(fakes.json_response({"a": 1}, id="chatcmpl-9"))

    adapter.execute(fakes.provider_request())
    adapter.execute(fakes.provider_request())

    assert len(details) == 2
    assert not any("chatcmpl" in str(value) for value in vars(adapter).values())


def test_two_adapters_do_not_share_state() -> None:
    first, _, first_details = _adapter(fakes.json_response({"a": 1}, id="chatcmpl-a"))
    second, _, second_details = _adapter(fakes.named_exception("RateLimitError"))

    first.execute(fakes.provider_request())
    second.execute(fakes.provider_request())

    assert first_details[-1].request_id == "chatcmpl-a"
    assert second_details[-1].error_code == error_mapping.CODE_RATE_LIMITED
    assert second_details[-1].request_id is None


def test_latency_is_measured_from_the_injected_clock() -> None:
    ticks = iter([100.0, 100.25])
    client = fakes.FakeClient(fakes.json_response({"a": 1}))
    details: list[OpenAIInvocationDetail] = []
    adapter = OpenAIProvider(
        fakes.runtime_configuration(),
        client=client,
        detail_sink=details.append,
        clock=lambda: next(ticks),
    )

    result = adapter.execute(fakes.provider_request())

    assert result.usage is not None
    assert result.usage.latency_ms == pytest.approx(250.0)
    assert details[-1].latency_ms == pytest.approx(250.0)


def test_detail_sink_is_optional() -> None:
    adapter = OpenAIProvider(fakes.runtime_configuration(), client=fakes.FakeClient())

    assert adapter.execute(fakes.provider_request()).status is ProviderExecutionStatus.SUCCESS


def test_invalid_constructor_arguments_are_rejected() -> None:
    with pytest.raises(ProviderContractValidationError):
        OpenAIProvider("not a configuration")  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        OpenAIProvider(fakes.runtime_configuration(), detail_sink="not callable")  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        OpenAIProvider(fakes.runtime_configuration(), clock="not callable")  # type: ignore[arg-type]


def test_execute_sends_the_expected_kwargs_to_the_sdk() -> None:
    adapter, client, _ = _adapter()

    adapter.execute(fakes.provider_request())

    kwargs = client.calls[0]
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in kwargs["messages"]] == ["system", "user"]
