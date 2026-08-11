"""Independent Community telemetry runtime policy (Slice 9.1).

Engine-local product-policy contract. Independent from the legacy Phase 14.3
``TelemetryService`` schema ``1.0.0``, Community Cloud telemetry schema ``1.0``,
CLI event schema, Data Lake envelopes, and installation-ID policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_RUNTIME_POLICY_ID = "community-telemetry-runtime-policy"
COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_RUNTIME_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION}"
)

PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_ID = "community-telemetry-runtime-event"
PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION = "1.0"
PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_URN = (
    f"{PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_ID}:"
    f"{PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION}"
)

DEFAULT_MAX_EVENT_SIZE_BYTES = 4096
DEFAULT_MAX_PROPERTY_COUNT = 24
DEFAULT_MAX_STRING_LENGTH = 64

_REVIEW_STATUS = "disabled_by_default_no_transmission_foundation"

_LIMITATIONS: tuple[str, ...] = (
    "disabled_by_default",
    "no_transmission_in_slice_9_1",
    "no_consent_prompt_in_slice_9_1",
    "no_persisted_consent_reuse",
    "no_installation_id_in_runtime",
    "transport_unavailable_by_default",
    "legacy_telemetry_service_isolated",
    "community_cloud_mapping_deferred",
    "cli_flags_and_commands_deferred",
    "fail_silent_required",
)


class RuntimePolicyError(ValueError):
    """Raised when runtime-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryRuntimePolicy:
    """Deterministic, versioned telemetry runtime product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_RUNTIME_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION
    disabled_by_default: bool = True
    session_scoped_decision_only: bool = True
    automatic_prior_consent_reuse: bool = False
    transmission_requires_explicit_allow: bool = True
    consent_prompt_enabled: bool = False
    preview_allowed_while_disabled: bool = True
    fail_silent: bool = True
    telemetry_failure_cannot_alter_command_result: bool = True
    transport_unavailable_by_default: bool = True
    installation_id_allowed: bool = False
    max_event_size_bytes: int = DEFAULT_MAX_EVENT_SIZE_BYTES
    max_property_count: int = DEFAULT_MAX_PROPERTY_COUNT
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH
    event_schema_version: str = PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_RUNTIME_POLICY_ID:
            raise RuntimePolicyError("unsupported runtime policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION:
            raise RuntimePolicyError("unsupported runtime policy version")
        if self.review_status != _REVIEW_STATUS:
            raise RuntimePolicyError("unsupported runtime review_status")
        if not self.disabled_by_default:
            raise RuntimePolicyError("disabled_by_default must be true")
        if not self.session_scoped_decision_only:
            raise RuntimePolicyError("session_scoped_decision_only must be true")
        if self.automatic_prior_consent_reuse:
            raise RuntimePolicyError("automatic_prior_consent_reuse must be false")
        if not self.transmission_requires_explicit_allow:
            raise RuntimePolicyError("transmission_requires_explicit_allow must be true")
        if self.consent_prompt_enabled:
            raise RuntimePolicyError("consent_prompt_enabled must be false in Slice 9.1")
        if not self.preview_allowed_while_disabled:
            raise RuntimePolicyError("preview_allowed_while_disabled must be true")
        if not self.fail_silent:
            raise RuntimePolicyError("fail_silent must be true")
        if not self.telemetry_failure_cannot_alter_command_result:
            raise RuntimePolicyError(
                "telemetry_failure_cannot_alter_command_result must be true"
            )
        if not self.transport_unavailable_by_default:
            raise RuntimePolicyError("transport_unavailable_by_default must be true")
        if self.installation_id_allowed:
            raise RuntimePolicyError("installation_id_allowed must be false in Slice 9.1")
        if self.max_event_size_bytes < 256 or self.max_event_size_bytes > 65536:
            raise RuntimePolicyError("max_event_size_bytes out of bounds")
        if self.max_property_count < 1 or self.max_property_count > 64:
            raise RuntimePolicyError("max_property_count out of bounds")
        if self.max_string_length < 8 or self.max_string_length > 256:
            raise RuntimePolicyError("max_string_length out of bounds")
        if self.event_schema_version != PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION:
            raise RuntimePolicyError("unsupported event_schema_version")

    @classmethod
    def default(cls) -> CommunityTelemetryRuntimePolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "automatic_prior_consent_reuse": self.automatic_prior_consent_reuse,
            "consent_prompt_enabled": self.consent_prompt_enabled,
            "disabled_by_default": self.disabled_by_default,
            "event_schema_version": self.event_schema_version,
            "fail_silent": self.fail_silent,
            "installation_id_allowed": self.installation_id_allowed,
            "limitations": list(self.limitations),
            "max_event_size_bytes": self.max_event_size_bytes,
            "max_property_count": self.max_property_count,
            "max_string_length": self.max_string_length,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "preview_allowed_while_disabled": self.preview_allowed_while_disabled,
            "review_status": self.review_status,
            "session_scoped_decision_only": self.session_scoped_decision_only,
            "telemetry_failure_cannot_alter_command_result": (
                self.telemetry_failure_cannot_alter_command_result
            ),
            "transmission_requires_explicit_allow": self.transmission_requires_explicit_allow,
            "transport_unavailable_by_default": self.transport_unavailable_by_default,
        }


def default_runtime_policy() -> CommunityTelemetryRuntimePolicy:
    return CommunityTelemetryRuntimePolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_RUNTIME_POLICY_ID",
    "COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN",
    "COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION",
    "CommunityTelemetryRuntimePolicy",
    "PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_ID",
    "PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_URN",
    "PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION",
    "RuntimePolicyError",
    "default_runtime_policy",
]
