"""Unit tests for provider_contracts.requests."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)


def _payload() -> ModernizationAdvisorInput:
    return ModernizationAdvisorInput(instruction_text="do the thing", context_payload_text="ctx")


def test_request_defaults_contract_version_and_execution_options() -> None:
    request = AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=_payload(),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("gpt-4o-mini"),
    )
    assert request.contract_version == "1.0"
    assert request.execution_options == ExecutionOptions()


def test_request_is_frozen() -> None:
    request = AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=_payload(),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("gpt-4o-mini"),
    )
    with pytest.raises(AttributeError):
        request.contract_version = "2.0"  # type: ignore[misc]


def test_request_rejects_payload_capability_mismatch() -> None:
    class OtherPayload:
        pass

    with pytest.raises(ProviderContractValidationError):
        AIProviderRequest(
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            payload=OtherPayload(),
            response_expectation=ResponseExpectation.TEXT,
            model_reference=ProviderModelReference("gpt-4o-mini"),
        )


def test_request_rejects_unsupported_contract_version() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRequest(
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            payload=_payload(),
            response_expectation=ResponseExpectation.TEXT,
            model_reference=ProviderModelReference("gpt-4o-mini"),
            contract_version="99.0",
        )


def test_execution_options_accepts_none_by_default() -> None:
    options = ExecutionOptions()
    assert options.timeout_seconds is None
    assert options.temperature is None
    assert options.max_tokens is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_tokens": 0},
        {"max_tokens": -5},
    ],
)
def test_execution_options_rejects_out_of_bounds_values(kwargs: dict[str, float]) -> None:
    with pytest.raises(ProviderContractValidationError):
        ExecutionOptions(**kwargs)


def test_execution_options_are_optional_and_not_claimed_to_be_wired() -> None:
    # CR-2: presence of these fields must never be read as "wired." This test
    # simply documents that constructing options has no side effects.
    options = ExecutionOptions(timeout_seconds=30.0, temperature=0.2, max_tokens=512)
    assert options.timeout_seconds == 30.0
    assert options.temperature == 0.2
    assert options.max_tokens == 512
