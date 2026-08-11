"""Independent CLI telemetry consent-flag policy (Slice 9.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_ID = "community-telemetry-cli-consent-policy"
COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION}"
)

_REVIEW_STATUS = "per_invocation_cli_flags_no_persistence"

_LIMITATIONS: tuple[str, ...] = (
    "per_invocation_only",
    "allow_deny_mutually_exclusive",
    "explicit_decision_precedes_prompt",
    "works_interactive_and_non_interactive",
    "no_persistence",
    "no_prior_consent_reuse",
    "no_installation_identity",
    "privacy_projection_mandatory",
    "transport_unavailable_by_default",
    "no_queue_or_http",
    "no_implicit_default_allow",
    "no_environment_variable_equivalent",
    "assess_command_scope_only",
    "preview_is_local_transparency_only",
)

SUPPORTED_COMMANDS: frozenset[str] = frozenset({"assess"})

TELEMETRY_FLAG_CONFLICT_MESSAGE = (
    "--telemetry-allow and --telemetry-deny cannot be used together."
)


class CliConsentPolicyError(ValueError):
    """Raised when CLI consent-flag policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryCliConsentPolicy:
    """Versioned CLI flag consent product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION
    flags_are_per_invocation: bool = True
    allow_deny_mutually_exclusive: bool = True
    explicit_precedes_prompt: bool = True
    works_in_non_interactive: bool = True
    persistence_allowed: bool = False
    prior_consent_reuse_allowed: bool = False
    installation_identity_required: bool = False
    privacy_projection_mandatory: bool = True
    transport_unavailable_by_default: bool = True
    queue_or_http_allowed: bool = False
    implicit_default_allow: bool = False
    environment_variable_equivalent: bool = False
    supported_commands: tuple[str, ...] = tuple(sorted(SUPPORTED_COMMANDS))
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "supported_commands", tuple(sorted(set(self.supported_commands)))
        )
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_ID:
            raise CliConsentPolicyError("unsupported CLI consent policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION:
            raise CliConsentPolicyError("unsupported CLI consent policy version")
        if not self.flags_are_per_invocation:
            raise CliConsentPolicyError("flags_are_per_invocation must be true")
        if not self.allow_deny_mutually_exclusive:
            raise CliConsentPolicyError("allow_deny_mutually_exclusive must be true")
        if self.persistence_allowed:
            raise CliConsentPolicyError("persistence_allowed must be false")
        if self.prior_consent_reuse_allowed:
            raise CliConsentPolicyError("prior_consent_reuse_allowed must be false")
        if self.installation_identity_required:
            raise CliConsentPolicyError("installation_identity_required must be false")
        if not self.privacy_projection_mandatory:
            raise CliConsentPolicyError("privacy_projection_mandatory must be true")
        if not self.transport_unavailable_by_default:
            raise CliConsentPolicyError("transport_unavailable_by_default must be true")
        if self.queue_or_http_allowed:
            raise CliConsentPolicyError("queue_or_http_allowed must be false")
        if self.implicit_default_allow:
            raise CliConsentPolicyError("implicit_default_allow must be false")
        if self.environment_variable_equivalent:
            raise CliConsentPolicyError("environment_variable_equivalent must be false")
        if "assess" not in self.supported_commands:
            raise CliConsentPolicyError("assess must remain supported")
        if self.review_status != _REVIEW_STATUS:
            raise CliConsentPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryCliConsentPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "allow_deny_mutually_exclusive": self.allow_deny_mutually_exclusive,
            "environment_variable_equivalent": self.environment_variable_equivalent,
            "explicit_precedes_prompt": self.explicit_precedes_prompt,
            "flags_are_per_invocation": self.flags_are_per_invocation,
            "implicit_default_allow": self.implicit_default_allow,
            "installation_identity_required": self.installation_identity_required,
            "limitations": list(self.limitations),
            "persistence_allowed": self.persistence_allowed,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prior_consent_reuse_allowed": self.prior_consent_reuse_allowed,
            "privacy_projection_mandatory": self.privacy_projection_mandatory,
            "queue_or_http_allowed": self.queue_or_http_allowed,
            "review_status": self.review_status,
            "supported_commands": list(self.supported_commands),
            "transport_unavailable_by_default": self.transport_unavailable_by_default,
            "works_in_non_interactive": self.works_in_non_interactive,
        }


def default_cli_consent_policy() -> CommunityTelemetryCliConsentPolicy:
    return CommunityTelemetryCliConsentPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_ID",
    "COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_URN",
    "COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION",
    "CliConsentPolicyError",
    "CommunityTelemetryCliConsentPolicy",
    "SUPPORTED_COMMANDS",
    "TELEMETRY_FLAG_CONFLICT_MESSAGE",
    "default_cli_consent_policy",
]
