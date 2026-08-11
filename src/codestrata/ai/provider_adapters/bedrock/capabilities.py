"""What the Bedrock adapter declares it supports.

The declarations are not re-authored here: they are read from the static
Slice 11.5 catalog (``provider_contracts.capability_catalogs.
BEDROCK_CAPABILITY_PROFILE``) so that "what the catalog says Bedrock
supports" and "what the adapter actually answers ``supports()`` with" can
never drift.

The profile's ``supports_structured_json=False`` is load-bearing, not
incidental: the Converse API has no OpenAI-style ``response_format``
equivalent, so structured JSON is requested by *prompt instruction only*
(``request_mapping.STRUCTURED_JSON_INSTRUCTION`` folded into the ``system``
block), exactly as the pre-migration provider did. The profile's
``"prompt_instruction_only"`` limitation label records that.

The catalog profile still carries the ``"not_wired_to_runtime"`` limitation
label. That label was accurate when Slice 11.5 authored it and is
intentionally left unchanged by Slice 11.7 so prior-slice verification
verdicts stay stable; ``engine/docs/ai-provider-bedrock.md`` records that
for Bedrock the timeout/retry policies *are* now honored by this adapter's
executor wiring.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_catalogs import BEDROCK_CAPABILITY_PROFILE
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

BEDROCK_PROVIDER_ID: ProviderId = ProviderId.BEDROCK

SUPPORTED_CAPABILITY_IDS: frozenset[CapabilityId] = frozenset(
    BEDROCK_CAPABILITY_PROFILE.supported_capability_ids
)

# Bedrock Converse exposes no native JSON mode. Structured JSON is requested
# through the prompt instruction only; this must stay ``False``.
SUPPORTS_NATIVE_STRUCTURED_JSON: bool = BEDROCK_CAPABILITY_PROFILE.supports_structured_json


def bedrock_capability_profile() -> ProviderCapabilityProfile:
    """Return the static Bedrock capability profile this adapter answers from."""

    return BEDROCK_CAPABILITY_PROFILE


def declares_capability(capability: CapabilityId) -> bool:
    """Return whether the Bedrock adapter declares support for ``capability``.

    Never constructs a client, reads the environment, or makes a network
    call — capability discovery is a pure lookup.
    """

    return isinstance(capability, CapabilityId) and capability in SUPPORTED_CAPABILITY_IDS


__all__ = [
    "BEDROCK_PROVIDER_ID",
    "SUPPORTED_CAPABILITY_IDS",
    "SUPPORTS_NATIVE_STRUCTURED_JSON",
    "bedrock_capability_profile",
    "declares_capability",
]
