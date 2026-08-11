"""Independent privacy-first telemetry status policy (Slice 9.7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_STATUS_POLICY_ID = "community-telemetry-status-policy"
COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_STATUS_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_STATUS_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION}"
)

PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME = "privacy-first-telemetry-status"
PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION = "1.0.0"

_REVIEW_STATUS = "side_effect_free_privacy_first_status"

_LIMITATIONS: tuple[str, ...] = (
    "status_is_not_a_consent_decision",
    "does_not_inspect_legacy_filesystem_by_default",
    "does_not_evaluate_live_tty_eligibility",
    "http_transport_requires_explicit_configuration",
    "operational_transport_not_configured_by_default",
    "assessment_isolation_primary_authoritative",
    "vscode_cursor_integration_not_implemented",
)


class TelemetryStatusPolicyError(ValueError):
    """Raised when status-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryStatusPolicy:
    """Versioned status reporting contract for privacy-first telemetry."""

    policy_id: str = COMMUNITY_TELEMETRY_STATUS_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION
    status_schema_name: str = PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME
    status_schema_version: str = PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION
    default_runtime_decision: str = "disabled_by_default"
    telemetry_enabled_by_default: bool = False
    consent_scope: str = "session"
    consent_persisted: bool = False
    prior_consent_reused: bool = False
    prompt_command_scope: tuple[str, ...] = ("assess",)
    cli_flag_command_scope: tuple[str, ...] = ("assess",)
    transport_category: str = "unavailable"
    transmission_available: bool = False
    installation_identity_used: bool = False
    privacy_filtering_required: bool = True
    legacy_compatibility_state_available: bool = True
    status_side_effect_free: bool = True
    inspect_legacy_filesystem: bool = False
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "prompt_command_scope", tuple(sorted(set(self.prompt_command_scope)))
        )
        object.__setattr__(
            self,
            "cli_flag_command_scope",
            tuple(sorted(set(self.cli_flag_command_scope))),
        )
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_STATUS_POLICY_ID:
            raise TelemetryStatusPolicyError("unsupported status policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION:
            raise TelemetryStatusPolicyError("unsupported status policy version")
        if self.status_schema_name != PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME:
            raise TelemetryStatusPolicyError("unsupported status schema name")
        if self.status_schema_version != PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION:
            raise TelemetryStatusPolicyError("unsupported status schema version")
        if self.telemetry_enabled_by_default:
            raise TelemetryStatusPolicyError("telemetry_enabled_by_default must be false")
        if self.consent_persisted:
            raise TelemetryStatusPolicyError("consent_persisted must be false")
        if self.prior_consent_reused:
            raise TelemetryStatusPolicyError("prior_consent_reused must be false")
        if self.transmission_available:
            raise TelemetryStatusPolicyError("transmission_available must be false")
        if self.installation_identity_used:
            raise TelemetryStatusPolicyError("installation_identity_used must be false")
        if not self.privacy_filtering_required:
            raise TelemetryStatusPolicyError("privacy_filtering_required must be true")
        if not self.status_side_effect_free:
            raise TelemetryStatusPolicyError("status_side_effect_free must be true")
        if self.inspect_legacy_filesystem:
            raise TelemetryStatusPolicyError("inspect_legacy_filesystem must be false")
        if self.transport_category != "unavailable":
            raise TelemetryStatusPolicyError("transport_category must be unavailable")
        if self.consent_scope != "session":
            raise TelemetryStatusPolicyError("consent_scope must be session")
        if "assess" not in self.prompt_command_scope:
            raise TelemetryStatusPolicyError("assess must remain in prompt scope")
        if "assess" not in self.cli_flag_command_scope:
            raise TelemetryStatusPolicyError("assess must remain in flag scope")
        if self.review_status != _REVIEW_STATUS:
            raise TelemetryStatusPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryStatusPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "cli_flag_command_scope": list(self.cli_flag_command_scope),
            "consent_persisted": self.consent_persisted,
            "consent_scope": self.consent_scope,
            "default_runtime_decision": self.default_runtime_decision,
            "inspect_legacy_filesystem": self.inspect_legacy_filesystem,
            "installation_identity_used": self.installation_identity_used,
            "legacy_compatibility_state_available": (
                self.legacy_compatibility_state_available
            ),
            "limitations": list(self.limitations),
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prior_consent_reused": self.prior_consent_reused,
            "privacy_filtering_required": self.privacy_filtering_required,
            "prompt_command_scope": list(self.prompt_command_scope),
            "review_status": self.review_status,
            "status_schema_name": self.status_schema_name,
            "status_schema_version": self.status_schema_version,
            "status_side_effect_free": self.status_side_effect_free,
            "telemetry_enabled_by_default": self.telemetry_enabled_by_default,
            "transmission_available": self.transmission_available,
            "transport_category": self.transport_category,
        }


def default_status_policy() -> CommunityTelemetryStatusPolicy:
    return CommunityTelemetryStatusPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_STATUS_POLICY_ID",
    "COMMUNITY_TELEMETRY_STATUS_POLICY_URN",
    "COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION",
    "CommunityTelemetryStatusPolicy",
    "PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME",
    "PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION",
    "TelemetryStatusPolicyError",
    "default_status_policy",
]
