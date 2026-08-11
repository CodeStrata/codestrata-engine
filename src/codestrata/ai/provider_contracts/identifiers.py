"""Opaque, validated identifiers: provider ID, capability ID, model reference."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.policy import ALLOWED_CAPABILITY_IDS, ALLOWED_PROVIDER_IDS

_REDACTED_MODEL_REFERENCE = "[model_ref]"
_MAX_MODEL_REFERENCE_LENGTH = 256


class ProviderId(StrEnum):
    """Stable Engine provider identifiers for the provider-platform contracts.

    ``openai`` and ``bedrock`` match the ``codestrata assess`` registry keys
    (Slice 11.1 ``ENGINE_PROVIDER_IDS``). ``openrouter`` identifies the
    Slice 11.9 OpenRouter adapter; it is **not** registered in
    ``AssessAIProviderRegistry`` and is not the assess default (Decision B /
    Slice 11.8). Analytics-layer ``provider_family`` labels (e.g.
    ``aws_bedrock``) remain out of scope here.
    """

    OPENAI = "openai"
    BEDROCK = "bedrock"
    OPENROUTER = "openrouter"


assert tuple(sorted(p.value for p in ProviderId)) == tuple(sorted(ALLOWED_PROVIDER_IDS)), (
    "ProviderId enum values must exactly match policy.ALLOWED_PROVIDER_IDS"
)


class CapabilityId(StrEnum):
    """Stable capability identifiers.

    ``modernization_advisor`` matches the analytics capability catalog
    (``APPROVED_AI_CAPABILITIES``). "Modernization Advisor" is a
    product-facing display name only; it is never used as the identifier
    value.
    """

    MODERNIZATION_ADVISOR = "modernization_advisor"


assert tuple(c.value for c in CapabilityId) == ALLOWED_CAPABILITY_IDS, (
    "CapabilityId enum values must exactly match policy.ALLOWED_CAPABILITY_IDS"
)


@dataclass(frozen=True, slots=True)
class ProviderModelReference:
    """An opaque, validated model identifier string.

    The raw value is never exposed through ``__repr__``/``__str__`` or
    through :meth:`redacted`; callers that need the raw value for adapter
    wiring must read ``.value`` explicitly. Diagnostics, logs, registries,
    and verification reports must always use :meth:`redacted` instead.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ProviderContractValidationError(
                "ProviderModelReference value must be a non-empty string"
            )
        if len(self.value) > _MAX_MODEL_REFERENCE_LENGTH:
            raise ProviderContractValidationError(
                f"ProviderModelReference value must be at most "
                f"{_MAX_MODEL_REFERENCE_LENGTH} characters"
            )

    def redacted(self) -> str:
        return _REDACTED_MODEL_REFERENCE

    def __repr__(self) -> str:
        return f"ProviderModelReference({self.redacted()})"

    def __str__(self) -> str:
        return self.redacted()


__all__ = [
    "CapabilityId",
    "ProviderId",
    "ProviderModelReference",
]
