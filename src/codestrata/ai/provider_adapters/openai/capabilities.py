"""What the OpenAI adapter declares it supports.

The declarations are not re-authored here: they are read from the static
Slice 11.5 catalog (``provider_contracts.capability_catalogs.
OPENAI_CAPABILITY_PROFILE``) so that "what the catalog says OpenAI supports"
and "what the adapter actually answers ``supports()`` with" can never drift.

The catalog profile still carries the ``"not_wired_to_runtime"`` limitation
label. That label was accurate when Slice 11.5 authored it and is
intentionally left unchanged by Slice 11.6 so prior-slice verification
verdicts stay stable; ``engine/docs/ai-provider-openai.md`` records that for
OpenAI specifically the timeout/retry policies *are* now honored by this
adapter's executor wiring.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_catalogs import OPENAI_CAPABILITY_PROFILE
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

OPENAI_PROVIDER_ID: ProviderId = ProviderId.OPENAI

SUPPORTED_CAPABILITY_IDS: frozenset[CapabilityId] = frozenset(
    OPENAI_CAPABILITY_PROFILE.supported_capability_ids
)

# The adapter uses the OpenAI Chat Completions native JSON mode
# (``response_format={"type": "json_object"}``) when the request asks for
# structured JSON, exactly as the pre-migration provider did.
SUPPORTS_NATIVE_STRUCTURED_JSON: bool = OPENAI_CAPABILITY_PROFILE.supports_structured_json


def openai_capability_profile() -> ProviderCapabilityProfile:
    """Return the static OpenAI capability profile this adapter answers from."""

    return OPENAI_CAPABILITY_PROFILE


def declares_capability(capability: CapabilityId) -> bool:
    """Return whether the OpenAI adapter declares support for ``capability``.

    Never constructs a client, reads the environment, or makes a network
    call — capability discovery is a pure lookup.
    """

    return isinstance(capability, CapabilityId) and capability in SUPPORTED_CAPABILITY_IDS


__all__ = [
    "OPENAI_PROVIDER_ID",
    "SUPPORTED_CAPABILITY_IDS",
    "SUPPORTS_NATIVE_STRUCTURED_JSON",
    "declares_capability",
    "openai_capability_profile",
]
