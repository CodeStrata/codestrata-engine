"""Unit tests for provider_contracts.capabilities."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capabilities import (
    CAPABILITY_PAYLOAD_TYPES,
    ModernizationAdvisorInput,
    capability_for_payload,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId


def test_modernization_advisor_input_holds_finalized_text_fields() -> None:
    payload = ModernizationAdvisorInput(
        instruction_text="Summarize modernization risks.",
        context_payload_text="{}",
    )
    assert payload.instruction_text == "Summarize modernization risks."
    assert payload.context_payload_text == "{}"


def test_modernization_advisor_input_allows_empty_context_payload_text() -> None:
    payload = ModernizationAdvisorInput(instruction_text="do the thing", context_payload_text="")
    assert payload.context_payload_text == ""


def test_modernization_advisor_input_rejects_empty_instruction_text() -> None:
    with pytest.raises(ProviderContractValidationError):
        ModernizationAdvisorInput(instruction_text="   ", context_payload_text="ctx")


def test_modernization_advisor_input_does_not_look_like_openai_or_bedrock_wire_format() -> None:
    payload = ModernizationAdvisorInput(instruction_text="a", context_payload_text="b")
    assert not hasattr(payload, "messages")
    assert not hasattr(payload, "system")
    assert not hasattr(payload, "inferenceConfig")


def test_capability_payload_types_registers_modernization_advisor() -> None:
    assert CAPABILITY_PAYLOAD_TYPES == {
        CapabilityId.MODERNIZATION_ADVISOR: ModernizationAdvisorInput,
    }


def test_capability_for_payload_resolves_known_payload() -> None:
    payload = ModernizationAdvisorInput(instruction_text="a", context_payload_text="b")
    assert capability_for_payload(payload) is CapabilityId.MODERNIZATION_ADVISOR


def test_capability_for_payload_returns_none_for_unknown_payload() -> None:
    assert capability_for_payload(object()) is None
