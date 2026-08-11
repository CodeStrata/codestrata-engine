"""What the OpenRouter adapter declares it supports.

Declarations come from the static Slice 11.5/11.9 catalog entry
``OPENROUTER_CAPABILITY_PROFILE``. Capability discovery never constructs a
client or reads credentials.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_catalogs import OPENROUTER_CAPABILITY_PROFILE
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

OPENROUTER_PROVIDER_ID: ProviderId = ProviderId.OPENROUTER

SUPPORTED_CAPABILITY_IDS: frozenset[CapabilityId] = frozenset(
    OPENROUTER_CAPABILITY_PROFILE.supported_capability_ids
)

# Adapter-owned OpenAI-compatible JSON mode via response_format. Upstream model
# support may vary (see profile limitations).
SUPPORTS_NATIVE_STRUCTURED_JSON: bool = OPENROUTER_CAPABILITY_PROFILE.supports_structured_json


def openrouter_capability_profile() -> ProviderCapabilityProfile:
    """Return the static OpenRouter capability profile this adapter answers from."""

    return OPENROUTER_CAPABILITY_PROFILE


def declares_capability(capability: CapabilityId) -> bool:
    """Return whether the OpenRouter adapter declares support for ``capability``."""

    return isinstance(capability, CapabilityId) and capability in SUPPORTED_CAPABILITY_IDS


__all__ = [
    "OPENROUTER_PROVIDER_ID",
    "SUPPORTED_CAPABILITY_IDS",
    "SUPPORTS_NATIVE_STRUCTURED_JSON",
    "declares_capability",
    "openrouter_capability_profile",
]
