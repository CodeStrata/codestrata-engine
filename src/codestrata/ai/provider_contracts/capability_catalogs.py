"""Static capability catalogs for known Engine providers (declarations only).

OpenAI and Bedrock profiles describe migrated assess-path adapters. The
OpenRouter profile (Slice 11.9) describes the unwired OpenRouter adapter:
``modernization_advisor`` with OpenAI-compatible ``response_format`` support
at the *adapter* layer; individual upstream models may still refuse JSON
mode (recorded as a limitation). Streaming remains unsupported. Discovery
is static — never network, never client construction.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

BEDROCK_CAPABILITY_PROFILE = ProviderCapabilityProfile(
    provider_id=ProviderId.BEDROCK,
    supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
    supports_structured_json=False,
    supports_streaming=False,
    supports_timeout_policy=True,
    supports_retry_policy=True,
    reports_usage_metadata=True,
    reports_token_accounting=True,
    limitations=("prompt_instruction_only", "not_wired_to_runtime"),
)

OPENAI_CAPABILITY_PROFILE = ProviderCapabilityProfile(
    provider_id=ProviderId.OPENAI,
    supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
    supports_structured_json=True,
    supports_streaming=False,
    supports_timeout_policy=True,
    supports_retry_policy=True,
    reports_usage_metadata=True,
    reports_token_accounting=True,
    limitations=("not_wired_to_runtime",),
)

OPENROUTER_CAPABILITY_PROFILE = ProviderCapabilityProfile(
    provider_id=ProviderId.OPENROUTER,
    supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
    supports_structured_json=True,
    supports_streaming=False,
    supports_timeout_policy=True,
    supports_retry_policy=True,
    reports_usage_metadata=True,
    reports_token_accounting=True,
    limitations=("model_support_for_structured_json_varies",),
)

# Explicit, deterministic mapping — never built by scanning a directory or
# introspecting a registry, so iteration order and membership are stable.
KNOWN_PROVIDER_CAPABILITY_PROFILES: dict[ProviderId, ProviderCapabilityProfile] = {
    ProviderId.BEDROCK: BEDROCK_CAPABILITY_PROFILE,
    ProviderId.OPENAI: OPENAI_CAPABILITY_PROFILE,
    ProviderId.OPENROUTER: OPENROUTER_CAPABILITY_PROFILE,
}


def capability_profile_for(provider_id: ProviderId) -> ProviderCapabilityProfile:
    """Return the static capability profile for ``provider_id``.

    Raises :class:`KeyError` for any provider outside
    :data:`KNOWN_PROVIDER_CAPABILITY_PROFILES`.
    """

    return KNOWN_PROVIDER_CAPABILITY_PROFILES[provider_id]


def all_known_capability_profiles() -> tuple[ProviderCapabilityProfile, ...]:
    """Return every known provider's capability profile in a stable, sorted order."""

    return tuple(
        KNOWN_PROVIDER_CAPABILITY_PROFILES[provider_id]
        for provider_id in sorted(KNOWN_PROVIDER_CAPABILITY_PROFILES, key=lambda p: p.value)
    )


__all__ = [
    "BEDROCK_CAPABILITY_PROFILE",
    "KNOWN_PROVIDER_CAPABILITY_PROFILES",
    "OPENAI_CAPABILITY_PROFILE",
    "OPENROUTER_CAPABILITY_PROFILE",
    "all_known_capability_profiles",
    "capability_profile_for",
]
