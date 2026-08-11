"""Request mapping: exact Chat Completions kwargs, and byte-stable prompt folding."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from codestrata.ai.provider_adapters.openai import legacy_bridge, request_mapping
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from tests.ai.provider_adapters.openai import fakes


def test_structured_json_request_maps_to_expected_kwargs() -> None:
    kwargs = request_mapping.build_chat_completion_kwargs(fakes.provider_request())

    assert sorted(kwargs) == [
        "max_tokens",
        "messages",
        "model",
        "response_format",
        "temperature",
    ]
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 2048
    assert kwargs["response_format"] == {"type": "json_object"}


def test_messages_are_system_then_user_in_that_order() -> None:
    kwargs = request_mapping.build_chat_completion_kwargs(fakes.provider_request())
    messages = kwargs["messages"]

    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[0]["content"] == (
        "Be precise.\n\n"
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )
    assert messages[1]["content"] == '{"findings": []}'


def test_json_instruction_text_is_the_pre_migration_sentence() -> None:
    assert request_mapping.STRUCTURED_JSON_INSTRUCTION == (
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )


def test_text_expectation_omits_json_mode_and_trailer() -> None:
    request = fakes.provider_request(response_expectation=ResponseExpectation.TEXT)

    kwargs = request_mapping.build_chat_completion_kwargs(request)

    assert "response_format" not in kwargs
    assert kwargs["messages"][0]["content"] == "Be precise."


def test_json_instruction_is_never_appended_twice() -> None:
    """The degenerate all-JSON-instruction prompt must stay byte-identical."""

    content = request_mapping.build_system_content(
        request_mapping.STRUCTURED_JSON_INSTRUCTION,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
    )

    assert content == request_mapping.STRUCTURED_JSON_INSTRUCTION


def test_omitted_execution_options_are_omitted_from_kwargs() -> None:
    request = fakes.provider_request(temperature=None, max_tokens=None)

    kwargs = request_mapping.build_chat_completion_kwargs(request)

    assert "temperature" not in kwargs
    assert "max_tokens" not in kwargs


def test_non_request_object_is_rejected() -> None:
    with pytest.raises(ProviderContractValidationError):
        request_mapping.build_chat_completion_kwargs(object())  # type: ignore[arg-type]


def test_non_advisor_payload_is_rejected() -> None:
    """The payload guard is defensive: the envelope already enforces the type."""

    request = fakes.provider_request()
    object.__setattr__(request, "payload", "not a payload")

    with pytest.raises(ProviderContractValidationError):
        request_mapping.build_chat_completion_kwargs(request)


def test_blank_model_reference_is_rejected() -> None:
    request = fakes.provider_request()
    object.__setattr__(request, "model_reference", SimpleNamespace(value="   "))

    with pytest.raises(ProviderContractValidationError):
        request_mapping.build_chat_completion_kwargs(request)


def test_request_shape_is_prompt_free_and_model_free() -> None:
    shape = request_mapping.request_shape(fakes.provider_request())

    assert shape == {
        "json_mode_requested": True,
        "kwarg_names": ["max_tokens", "messages", "model", "response_format", "temperature"],
        "message_count": 2,
        "message_roles": ["system", "user"],
    }
    serialized = json.dumps(shape)
    assert "Be precise" not in serialized
    assert "gpt-4o-mini" not in serialized
    assert "findings" not in serialized


def test_mapping_is_pure_and_repeatable() -> None:
    request = fakes.provider_request()

    first = request_mapping.build_chat_completion_kwargs(request)
    second = request_mapping.build_chat_completion_kwargs(request)

    assert first == second
    first["messages"].append({"role": "user", "content": "mutated"})
    assert len(request_mapping.build_chat_completion_kwargs(request)["messages"]) == 2


def _fold_and_fingerprint(**prompt_kwargs: str | None) -> tuple[list[dict[str, str]], str]:
    payload = legacy_bridge.fold_prompt_request(fakes.prompt_request(**prompt_kwargs))
    messages = request_mapping.build_chat_messages(
        payload, response_expectation=ResponseExpectation.STRUCTURED_JSON
    )
    encoded = json.dumps(messages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return messages, hashlib.sha256(encoded).hexdigest()


# Recorded against the pre-migration ``openai_provider._chat_messages`` output.
# A change to any of these digests is a change to what CodeStrata sends OpenAI.
_PROMPT_FINGERPRINTS: dict[str, tuple[dict[str, str | None], str]] = {
    "system_developer_user": (
        {},
        "871a60ad8f32ae3ab31920d3de33a673095ebd3a397b147a96b98df7fc17e540",
    ),
    "system_user": (
        {"developer": None},
        "1ff1b0721e4a523e005b32cf1de852bbceae08576b943ccecfc25cfaceb1ce67",
    ),
    "developer_user": (
        {"system": None},
        "0852c7752adfd1a874dfc0fe7a4429356ce3527215394df9aff7c05f4f03edf9",
    ),
    "user_only": (
        {"system": None, "developer": None},
        "9524711977eaf7a7cf5379a65959adcec59f4c8ee9dff0db7d08fab388877353",
    ),
}


@pytest.mark.parametrize("case", sorted(_PROMPT_FINGERPRINTS))
def test_prompt_folding_fingerprint_is_stable(case: str) -> None:
    prompt_kwargs, expected = _PROMPT_FINGERPRINTS[case]

    _, digest = _fold_and_fingerprint(**prompt_kwargs)

    assert digest == expected


def test_developer_message_keeps_its_legacy_prefix() -> None:
    messages, _ = _fold_and_fingerprint(system=None)

    assert messages[0]["content"].startswith("Developer instructions:\nDeveloper rules.")


def test_prompt_with_no_instructions_folds_to_the_json_instruction_only() -> None:
    messages, _ = _fold_and_fingerprint(system=None, developer=None)

    assert messages[0]["content"] == request_mapping.STRUCTURED_JSON_INSTRUCTION
    assert len(messages) == 2


def test_request_construction_rejects_mismatched_payload_before_mapping() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRequest(
            capability=fakes.provider_request().capability,
            payload="not a payload",
            response_expectation=ResponseExpectation.STRUCTURED_JSON,
            model_reference=ProviderModelReference(value="gpt-4o-mini"),
        )
