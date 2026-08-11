"""Unit tests for provider_contracts.identifiers."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)


def test_provider_id_values_are_openai_bedrock_and_openrouter() -> None:
    assert {p.value for p in ProviderId} == {"openai", "bedrock", "openrouter"}


def test_capability_id_values_are_exactly_modernization_advisor() -> None:
    assert {c.value for c in CapabilityId} == {"modernization_advisor"}


def test_provider_model_reference_holds_raw_value_for_adapter_use() -> None:
    ref = ProviderModelReference("gpt-4o-mini")
    assert ref.value == "gpt-4o-mini"


def test_provider_model_reference_redacted_never_leaks_raw_value() -> None:
    ref = ProviderModelReference("super-secret-internal-model-id")
    assert ref.redacted() == "[model_ref]"
    assert "super-secret-internal-model-id" not in ref.redacted()


def test_provider_model_reference_repr_and_str_are_redacted() -> None:
    ref = ProviderModelReference("amazon.nova-lite-v1:0")
    assert "amazon.nova-lite-v1:0" not in repr(ref)
    assert "amazon.nova-lite-v1:0" not in str(ref)
    assert repr(ref) == "ProviderModelReference([model_ref])"
    assert str(ref) == "[model_ref]"


@pytest.mark.parametrize("bad_value", ["", "   ", None])
def test_provider_model_reference_rejects_empty_values(bad_value: object) -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderModelReference(bad_value)  # type: ignore[arg-type]


def test_provider_model_reference_rejects_overlong_values() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderModelReference("x" * 257)
