"""Standalone validation helpers for provider capability profiles.

Every invariant here duplicates a check already performed by
``ProviderCapabilityProfile.__post_init__`` (see ``capability_models.py``);
these functions exist so that catalog data, test fixtures, and a future
adapter can validate a profile — or check provider/capability consistency —
without constructing (or being forced to discard) an instance.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.capability_policy import (
    CAPABILITY_ALLOWED_CAPABILITY_IDS,
    CAPABILITY_ALLOWED_PROVIDER_IDS,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId


def validate_capability_id_is_known(capability_id: CapabilityId) -> None:
    """Reject any ``capability_id`` outside the closed, policy-bounded set."""

    if not isinstance(capability_id, CapabilityId):
        raise ProviderContractValidationError("capability_id must be a CapabilityId")
    if capability_id.value not in CAPABILITY_ALLOWED_CAPABILITY_IDS:
        raise ProviderContractValidationError(
            f"unknown capability_id {capability_id.value!r}; allowed: "
            f"{CAPABILITY_ALLOWED_CAPABILITY_IDS}"
        )


def validate_provider_id_is_known(provider_id: ProviderId) -> None:
    """Reject any ``provider_id`` outside the closed, policy-bounded set."""

    if not isinstance(provider_id, ProviderId):
        raise ProviderContractValidationError("provider_id must be a ProviderId")
    if provider_id.value not in CAPABILITY_ALLOWED_PROVIDER_IDS:
        raise ProviderContractValidationError(
            f"unknown provider_id {provider_id.value!r}; allowed: {CAPABILITY_ALLOWED_PROVIDER_IDS}"
        )


def validate_capability_profile(profile: ProviderCapabilityProfile) -> None:
    """Re-validate a profile's provider/capability identifiers against current policy.

    ``ProviderCapabilityProfile.__post_init__`` already enforces every
    structural invariant (types, duplicates, bounded limitations, schema
    version); this adds the policy-level check that every identifier the
    profile carries is still a currently-allowed value — useful for catalog
    data that was constructed once and is being re-checked later (e.g. by
    verification).
    """

    if not isinstance(profile, ProviderCapabilityProfile):
        raise ProviderContractValidationError(
            "validate_capability_profile() requires a ProviderCapabilityProfile"
        )
    validate_provider_id_is_known(profile.provider_id)
    for capability_id in profile.supported_capability_ids:
        validate_capability_id_is_known(capability_id)


def validate_provider_declares_capability(
    profile: ProviderCapabilityProfile, capability_id: CapabilityId
) -> None:
    """Raise unless ``profile`` declares support for ``capability_id``."""

    validate_capability_profile(profile)
    validate_capability_id_is_known(capability_id)
    if not profile.declares_capability(capability_id):
        raise ProviderContractValidationError(
            f"provider {profile.provider_id.value!r} does not declare capability "
            f"{capability_id.value!r}"
        )


__all__ = [
    "validate_capability_id_is_known",
    "validate_capability_profile",
    "validate_provider_declares_capability",
    "validate_provider_id_is_known",
]
