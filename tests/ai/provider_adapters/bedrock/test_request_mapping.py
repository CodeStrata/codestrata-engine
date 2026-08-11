"""Request mapping: Converse kwargs, prompt-instruction JSON, no OpenAI JSON mode."""

from __future__ import annotations

from codestrata.ai.provider_adapters.bedrock.request_mapping import (
    STRUCTURED_JSON_INSTRUCTION,
    build_converse_kwargs,
    request_shape,
)
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from tests.ai.provider_adapters.bedrock import fakes


def test_structured_json_converse_kwargs_shape() -> None:
    kwargs = build_converse_kwargs(fakes.provider_request())
    assert set(kwargs) >= {"modelId", "messages", "inferenceConfig", "system"}
    assert "response_format" not in kwargs
    assert kwargs["modelId"] == fakes.DEFAULT_MODEL_ID
    assert kwargs["messages"][0]["role"] == "user"
    assert kwargs["inferenceConfig"]["maxTokens"] == 5000
    assert kwargs["inferenceConfig"]["temperature"] == 0.0
    assert kwargs["system"][0]["text"].endswith(STRUCTURED_JSON_INSTRUCTION)


def test_text_expectation_omits_json_instruction() -> None:
    kwargs = build_converse_kwargs(
        fakes.provider_request(response_expectation=ResponseExpectation.TEXT)
    )
    system_text = kwargs.get("system", [{}])[0].get("text", "")
    assert STRUCTURED_JSON_INSTRUCTION not in system_text
    assert "response_format" not in kwargs


def test_request_shape_omits_prompt_and_model_values() -> None:
    shape = request_shape(fakes.provider_request())
    rendered = str(shape)
    assert "Synthetic instruction" not in rendered
    assert fakes.DEFAULT_MODEL_ID not in rendered
    assert shape["system_block_present"] is True
    assert shape["message_roles"] == ["user"]
    assert shape["json_mode_requested"] is False
