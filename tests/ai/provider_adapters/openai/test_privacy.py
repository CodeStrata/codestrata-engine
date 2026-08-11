"""Privacy: no credential, prompt, response, base URL, or request ID escapes a safe surface."""

from __future__ import annotations

import json

import pytest

from codestrata.ai.provider_adapters.openai import diagnostics, error_mapping, request_mapping
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.serialization import serialize_result_for_diagnostics
from codestrata.config.settings import OpenAISettings
from tests.ai.provider_adapters.openai import fakes

_SECRET_KEY = "sk-super-secret-value"
_SECRET_BASE_URL = "https://private-gateway.example.internal/v1"
_SECRET_PROMPT = "PROPRIETARY-SOURCE-SNIPPET"
_SECRET_RESPONSE = "PROPRIETARY-RESPONSE-TEXT"
_SECRET_REQUEST_ID = "chatcmpl-secret-request-id"

_FORBIDDEN = (
    _SECRET_KEY,
    _SECRET_BASE_URL,
    "private-gateway",
    _SECRET_PROMPT,
    _SECRET_RESPONSE,
    _SECRET_REQUEST_ID,
)


def _assert_clean(text: str) -> None:
    for secret in _FORBIDDEN:
        assert secret not in text, f"{secret!r} leaked into a safe surface"


@pytest.fixture
def secret_adapter(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MY_KEY_VAR", _SECRET_KEY)
    client = fakes.FakeClient(
        fakes.text_response(_SECRET_RESPONSE, id=_SECRET_REQUEST_ID)
    )
    return build_openai_provider(
        openai_settings=OpenAISettings(api_key_env="MY_KEY_VAR", base_url=_SECRET_BASE_URL),
        client=client,
    )


def test_adapter_diagnostic_view_leaks_nothing(secret_adapter) -> None:
    _assert_clean(json.dumps(diagnostics.diagnostic_view_of_adapter(secret_adapter)))


def test_result_diagnostics_leak_nothing(secret_adapter) -> None:
    request = fakes.provider_request(
        payload=fakes.advisor_payload(context_payload_text=_SECRET_PROMPT)
    )
    result = secret_adapter.execute(request)

    _assert_clean(json.dumps(diagnostics.diagnostic_view_of_provider_result(result)))
    _assert_clean(serialize_result_for_diagnostics(result))


def test_execution_diagnostics_leak_nothing(secret_adapter) -> None:
    request = fakes.provider_request(
        payload=fakes.advisor_payload(context_payload_text=_SECRET_PROMPT)
    )
    execution = build_openai_executor(secret_adapter).execute(request)

    _assert_clean(json.dumps(diagnostics.diagnostic_view_of_execution(execution)))


def test_request_shape_leaks_no_prompt_or_model(secret_adapter) -> None:
    request = fakes.provider_request(
        payload=fakes.advisor_payload(
            instruction_text=_SECRET_PROMPT, context_payload_text=_SECRET_PROMPT
        )
    )

    _assert_clean(json.dumps(request_mapping.request_shape(request)))


def test_bounded_errors_leak_no_sdk_text() -> None:
    failure = error_mapping.classify_sdk_exception(
        fakes.named_exception("AuthenticationError", f"Incorrect API key: {_SECRET_KEY}")
    )

    assert _SECRET_KEY not in failure.error.detail
    assert _SECRET_KEY not in failure.error.code


def test_configuration_repr_leaks_nothing(secret_adapter) -> None:
    _assert_clean(repr(secret_adapter.configuration))
    _assert_clean(repr(secret_adapter.configuration.client_inputs))
    _assert_clean(json.dumps(secret_adapter.configuration.redacted()))


def test_failure_result_diagnostics_leak_no_sanitized_exception_text() -> None:
    adapter = build_openai_provider(
        client=fakes.FakeClient(
            fakes.named_exception("BadRequestError", f"model rejected {_SECRET_PROMPT}")
        )
    )

    result = adapter.execute(fakes.provider_request())

    _assert_clean(json.dumps(diagnostics.diagnostic_view_of_provider_result(result)))
    _assert_clean(serialize_result_for_diagnostics(result))
