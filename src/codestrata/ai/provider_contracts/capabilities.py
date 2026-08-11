"""Typed capability payloads.

Slice 11.2 defines exactly one capability payload type,
:class:`ModernizationAdvisorInput`, for the ``modernization_advisor``
capability. It intentionally represents *finalized, provider-neutral text*
rather than any provider's wire format:

* It is **not** an OpenAI Chat Completions ``messages: list[dict]`` array.
* It is **not** a Bedrock Converse ``messages``/``system`` dict shape.

An adapter (future work, not implemented by this slice) would be responsible
for wrapping ``instruction_text``/``context_payload_text`` into whichever
wire format its SDK requires. This module does not change, and is not
consulted by, any actual prompt construction in
``codestrata.ai.enrichment``/``codestrata.ai.prompts`` today.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId

_MAX_INSTRUCTION_TEXT_LENGTH = 200_000
_MAX_CONTEXT_PAYLOAD_TEXT_LENGTH = 2_000_000


@dataclass(frozen=True, slots=True)
class ModernizationAdvisorInput:
    """Finalized, provider-neutral text input for the Modernization Advisor capability.

    ``instruction_text`` is the finalized instruction/system intent text;
    ``context_payload_text`` is the finalized serialized analysis context
    text. Both are treated as already-composed by the caller — this type
    carries them, it does not build or template them.
    """

    instruction_text: str
    context_payload_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.instruction_text, str) or not self.instruction_text.strip():
            raise ProviderContractValidationError(
                "ModernizationAdvisorInput.instruction_text must be a non-empty string"
            )
        if len(self.instruction_text) > _MAX_INSTRUCTION_TEXT_LENGTH:
            raise ProviderContractValidationError(
                "ModernizationAdvisorInput.instruction_text exceeds the maximum length"
            )
        if not isinstance(self.context_payload_text, str):
            raise ProviderContractValidationError(
                "ModernizationAdvisorInput.context_payload_text must be a string"
            )
        if len(self.context_payload_text) > _MAX_CONTEXT_PAYLOAD_TEXT_LENGTH:
            raise ProviderContractValidationError(
                "ModernizationAdvisorInput.context_payload_text exceeds the maximum length"
            )


# Capability -> payload type declarations, used by requests.py to validate
# that a request's payload matches its declared capability. A future slice
# adding a second capability would add one entry here (and a matching
# dataclass) without touching any existing entry.
CAPABILITY_PAYLOAD_TYPES: dict[CapabilityId, type] = {
    CapabilityId.MODERNIZATION_ADVISOR: ModernizationAdvisorInput,
}


def capability_for_payload(payload: object) -> CapabilityId | None:
    """Return the capability whose declared payload type matches ``payload``, if any."""

    for capability, payload_type in CAPABILITY_PAYLOAD_TYPES.items():
        if isinstance(payload, payload_type):
            return capability
    return None


__all__ = [
    "CAPABILITY_PAYLOAD_TYPES",
    "ModernizationAdvisorInput",
    "capability_for_payload",
]
