"""Compatibility wrapper preserves public surface and lazy client construction."""

from __future__ import annotations

import json

import pytest

from codestrata.ai.providers.bedrock import (
    BEDROCK_PROVIDER_NAME,
    BedrockAIModelProvider,
    build_converse_request,
    extract_converse_response,
    split_prompt_for_converse,
)
from codestrata.ai.providers.exceptions import AIProviderConfigurationError, AIProviderTimeoutError
from codestrata.ai.providers.models import ModelInvocationOptions
from tests.ai.provider_adapters.bedrock import fakes
from verification.bedrock_provider_migration import fixtures


def test_public_exports_and_provider_name() -> None:
    assert BEDROCK_PROVIDER_NAME == "bedrock"
    assert callable(build_converse_request)
    assert callable(extract_converse_response)
    assert callable(split_prompt_for_converse)


def test_constructor_is_lazy_with_injected_client() -> None:
    client = fakes.Client()
    provider = BedrockAIModelProvider(client=client)
    assert client.calls == []
    result = provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    assert len(client.calls) == 1
    assert result.metadata.provider == "bedrock"
    assert json.loads(result.raw_response_text)["executive_summary"]["headline"] == "H"


def test_throttling_still_raises_timeout_error() -> None:
    provider = BedrockAIModelProvider(client=fakes.Client(fakes.client_error("ThrottlingException")))
    with pytest.raises(AIProviderTimeoutError):
        provider.invoke(fixtures.model_request(), fixtures.invocation_options())


def test_empty_model_id_still_raises_configuration_error() -> None:
    provider = BedrockAIModelProvider(client=fakes.Client())
    with pytest.raises(AIProviderConfigurationError):
        provider.invoke(
            fixtures.model_request(),
            fixtures.invocation_options(model_id="   "),
        )


def test_build_converse_request_has_no_response_format() -> None:
    kwargs = build_converse_request(
        fixtures.prompt_request(),
        ModelInvocationOptions(model_id=fakes.DEFAULT_MODEL_ID, max_output_tokens=5000),
    )
    assert "response_format" not in kwargs
    assert kwargs["modelId"] == fakes.DEFAULT_MODEL_ID
