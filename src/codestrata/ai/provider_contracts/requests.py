"""The immutable AI provider request envelope.

``AIProviderRequest`` never carries an arbitrary ``dict`` payload — the
``payload`` field is always a typed capability payload (see
``capabilities.py``) whose type is validated against the declared
``capability``.

``execution_options`` fields are optional, opaque numbers reserved for
possible future use. Per Slice 11.2 hard constraints (CR-2), no adapter or
call site reads or wires ``timeout_seconds``/``temperature``/``max_tokens``
today — their presence here is a contract placeholder only, not a claim that
any settings/timeout/retry behavior has changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from codestrata.ai.provider_contracts.capabilities import CAPABILITY_PAYLOAD_TYPES
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.policy import ALLOWED_RESPONSE_EXPECTATIONS
from codestrata.ai.provider_contracts.versions import (
    CURRENT_CONTRACT_VERSION,
    validate_contract_version,
)


class ResponseExpectation(StrEnum):
    """What shape of content the caller expects back from the provider."""

    TEXT = "text"
    STRUCTURED_JSON = "structured_json"


assert tuple(r.value for r in ResponseExpectation) == ALLOWED_RESPONSE_EXPECTATIONS, (
    "ResponseExpectation enum values must exactly match policy.ALLOWED_RESPONSE_EXPECTATIONS"
)

_MAX_TIMEOUT_SECONDS = 3600.0
_MAX_TEMPERATURE = 2.0
_MAX_TOKENS_CEILING = 1_000_000


@dataclass(frozen=True, slots=True)
class ExecutionOptions:
    """Optional, unwired execution hints. See module docstring."""

    timeout_seconds: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds is not None and not (
            0 < self.timeout_seconds <= _MAX_TIMEOUT_SECONDS
        ):
            raise ProviderContractValidationError(
                f"timeout_seconds must be within (0, {_MAX_TIMEOUT_SECONDS}]"
            )
        if self.temperature is not None and not (0 <= self.temperature <= _MAX_TEMPERATURE):
            raise ProviderContractValidationError(
                f"temperature must be within [0, {_MAX_TEMPERATURE}]"
            )
        if self.max_tokens is not None and not (0 < self.max_tokens <= _MAX_TOKENS_CEILING):
            raise ProviderContractValidationError(
                f"max_tokens must be within (0, {_MAX_TOKENS_CEILING}]"
            )


@dataclass(frozen=True, slots=True)
class AIProviderRequest:
    """Immutable envelope for a single provider-contract execution request."""

    capability: CapabilityId
    payload: object
    response_expectation: ResponseExpectation
    model_reference: ProviderModelReference
    execution_options: ExecutionOptions = field(default_factory=ExecutionOptions)
    contract_version: str = CURRENT_CONTRACT_VERSION.value

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        if not isinstance(self.capability, CapabilityId):
            raise ProviderContractValidationError(
                f"capability must be a CapabilityId, got {type(self.capability).__name__}"
            )
        if not isinstance(self.response_expectation, ResponseExpectation):
            raise ProviderContractValidationError(
                "response_expectation must be a ResponseExpectation, got "
                f"{type(self.response_expectation).__name__}"
            )
        if not isinstance(self.model_reference, ProviderModelReference):
            raise ProviderContractValidationError(
                "model_reference must be a ProviderModelReference, got "
                f"{type(self.model_reference).__name__}"
            )
        if not isinstance(self.execution_options, ExecutionOptions):
            raise ProviderContractValidationError(
                "execution_options must be an ExecutionOptions, got "
                f"{type(self.execution_options).__name__}"
            )
        expected_payload_type = CAPABILITY_PAYLOAD_TYPES.get(self.capability)
        if expected_payload_type is None or not isinstance(self.payload, expected_payload_type):
            raise ProviderContractValidationError(
                f"payload type {type(self.payload).__name__} does not match capability "
                f"{self.capability!r} (expected {getattr(expected_payload_type, '__name__', None)})"
            )


__all__ = [
    "AIProviderRequest",
    "ExecutionOptions",
    "ResponseExpectation",
]
