"""Immutable provider capability descriptor/profile value objects.

``ProviderCapabilityProfile`` is a pure, declared-only summary of what a
provider *would* support if fully migrated onto this contract package.
Nothing in this package, and nothing in ``codestrata assess``, consults a
profile to change what a provider adapter actually does today — see
``capability_catalogs.py`` for the two static, unwired baseline profiles and
``engine/docs/ai-provider-capabilities.md`` for the full design writeup.

No SDK class names, no implementation class names, no credentials, and no
endpoints ever appear on these types.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.capability_policy import ALLOWED_CAPABILITY_LIMITATIONS
from codestrata.ai.provider_contracts.capability_schema import (
    CURRENT_CAPABILITY_SCHEMA_VERSION,
    validate_capability_schema_version,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId

_MAX_LIMITATIONS = 16

_BOOLEAN_FEATURE_FIELDS: tuple[str, ...] = (
    "supports_structured_json",
    "supports_streaming",
    "supports_timeout_policy",
    "supports_retry_policy",
    "reports_usage_metadata",
    "reports_token_accounting",
)


@dataclass(frozen=True, slots=True)
class ProviderCapabilityDescriptor:
    """A single capability entry inside a :class:`ProviderCapabilityProfile`.

    This is a lightweight, single-field wrapper (rather than a plain
    ``CapabilityId``) so that a future slice adding per-capability feature
    flags (e.g. "does this provider support streaming for *this specific*
    capability") has a natural place to add fields without breaking
    ``ProviderCapabilityProfile.supported_capability_ids``, which remains a
    flat tuple of ``CapabilityId`` for this slice.
    """

    capability_id: CapabilityId

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise ProviderContractValidationError(
                "ProviderCapabilityDescriptor.capability_id must be a CapabilityId"
            )


@dataclass(frozen=True, slots=True)
class ProviderCapabilityProfile:
    """An immutable, declared-only summary of what a provider supports.

    Every boolean field is a **capability declaration**, not a runtime
    measurement: nothing in this package invokes a real provider to confirm
    it. ``limitations`` records known caveats about how a declared
    capability differs from a naive reading of the boolean (for example,
    ``supports_structured_json=False`` with limitation
    ``"prompt_instruction_only"`` for a provider that only achieves
    structured output via prompt instructions, not a native JSON mode).
    """

    provider_id: ProviderId
    supported_capability_ids: tuple[CapabilityId, ...]
    supports_structured_json: bool
    supports_streaming: bool
    supports_timeout_policy: bool
    supports_retry_policy: bool
    reports_usage_metadata: bool
    reports_token_accounting: bool
    limitations: tuple[str, ...] = ()
    schema_version: str = CURRENT_CAPABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                "ProviderCapabilityProfile.provider_id must be a ProviderId"
            )
        if (
            not isinstance(self.supported_capability_ids, tuple)
            or not self.supported_capability_ids
        ):
            raise ProviderContractValidationError(
                "ProviderCapabilityProfile.supported_capability_ids must be a "
                "non-empty tuple of CapabilityId"
            )
        for capability_id in self.supported_capability_ids:
            if not isinstance(capability_id, CapabilityId):
                raise ProviderContractValidationError(
                    "every entry of supported_capability_ids must be a CapabilityId"
                )
        if len(set(self.supported_capability_ids)) != len(self.supported_capability_ids):
            raise ProviderContractValidationError(
                "supported_capability_ids must not contain duplicate entries"
            )
        for field_name in _BOOLEAN_FEATURE_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, bool):
                raise ProviderContractValidationError(f"{field_name} must be a bool")
        if self.supports_streaming is not False:
            raise ProviderContractValidationError(
                "supports_streaming must be False for the current baseline "
                "(no streaming implementation exists yet)"
            )
        if not isinstance(self.limitations, tuple):
            raise ProviderContractValidationError("limitations must be a tuple of strings")
        if len(self.limitations) > _MAX_LIMITATIONS:
            raise ProviderContractValidationError(
                f"limitations must have at most {_MAX_LIMITATIONS} entries"
            )
        if len(set(self.limitations)) != len(self.limitations):
            raise ProviderContractValidationError("limitations must not contain duplicate entries")
        for limitation in self.limitations:
            if not isinstance(limitation, str) or not limitation.strip():
                raise ProviderContractValidationError("each limitation must be a non-empty string")
            if limitation not in ALLOWED_CAPABILITY_LIMITATIONS:
                raise ProviderContractValidationError(
                    f"limitation {limitation!r} is not in the allowed limitations set "
                    f"{ALLOWED_CAPABILITY_LIMITATIONS}"
                )
        validate_capability_schema_version(self.schema_version)

    def declares_capability(self, capability_id: CapabilityId) -> bool:
        """Return whether this profile declares support for ``capability_id``."""

        return capability_id in self.supported_capability_ids

    def descriptors(self) -> tuple[ProviderCapabilityDescriptor, ...]:
        """Return each supported capability as a :class:`ProviderCapabilityDescriptor`."""

        return tuple(
            ProviderCapabilityDescriptor(capability_id=capability_id)
            for capability_id in self.supported_capability_ids
        )


__all__ = [
    "ProviderCapabilityDescriptor",
    "ProviderCapabilityProfile",
]
