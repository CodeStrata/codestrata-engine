"""Independent non-interactive telemetry prompt-suppression policy (Slice 9.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_ID = (
    "community-telemetry-non-interactive-policy"
)
COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION}"
)

_REVIEW_STATUS = "suppress_prompt_fail_closed_non_interactive"

_LIMITATIONS: tuple[str, ...] = (
    "uncertainty_suppresses_prompt",
    "suppression_is_not_user_consent",
    "no_stdin_consumption",
    "no_persistence",
    "no_installation_identity",
    "no_transmission",
    "no_public_bypass_variable",
    "stdin_interactive_override_cannot_bypass_automation",
    "assess_only_interactive_eligibility",
    "cli_flags_provide_explicit_automation_consent",
)


class NonInteractivePolicyError(ValueError):
    """Raised when non-interactive policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryNonInteractivePolicy:
    """Versioned non-interactive prompt-suppression product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION
    prompt_suppressed_in_non_interactive: bool = True
    default_decision_when_suppressed: str = "non_interactive_disabled"
    stdin_tty_required: bool = True
    machine_readable_suppressed: bool = True
    quiet_mode_suppressed: bool = True
    ci_suppressed: bool = True
    automation_suppressed: bool = True
    piped_input_suppressed: bool = True
    missing_closed_stdin_suppressed: bool = True
    shell_completion_suppressed: bool = True
    help_version_suppressed: bool = True
    explicit_decision_bypasses_prompt: bool = True
    persistence_allowed: bool = False
    installation_identity_required: bool = False
    transmission_allowed: bool = False
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_ID:
            raise NonInteractivePolicyError("unsupported non-interactive policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION:
            raise NonInteractivePolicyError("unsupported non-interactive policy version")
        if not self.prompt_suppressed_in_non_interactive:
            raise NonInteractivePolicyError(
                "prompt_suppressed_in_non_interactive must be true"
            )
        if self.default_decision_when_suppressed != "non_interactive_disabled":
            raise NonInteractivePolicyError(
                "default_decision_when_suppressed must be non_interactive_disabled"
            )
        if self.persistence_allowed:
            raise NonInteractivePolicyError("persistence_allowed must be false")
        if self.installation_identity_required:
            raise NonInteractivePolicyError(
                "installation_identity_required must be false"
            )
        if self.transmission_allowed:
            raise NonInteractivePolicyError("transmission_allowed must be false")
        if self.review_status != _REVIEW_STATUS:
            raise NonInteractivePolicyError("unsupported review_status")
        for required in (
            "stdin_tty_required",
            "machine_readable_suppressed",
            "quiet_mode_suppressed",
            "ci_suppressed",
            "automation_suppressed",
            "piped_input_suppressed",
            "missing_closed_stdin_suppressed",
            "shell_completion_suppressed",
            "help_version_suppressed",
            "explicit_decision_bypasses_prompt",
        ):
            if not getattr(self, required):
                raise NonInteractivePolicyError(f"{required} must be true")

    @classmethod
    def default(cls) -> CommunityTelemetryNonInteractivePolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "automation_suppressed": self.automation_suppressed,
            "ci_suppressed": self.ci_suppressed,
            "default_decision_when_suppressed": self.default_decision_when_suppressed,
            "explicit_decision_bypasses_prompt": self.explicit_decision_bypasses_prompt,
            "help_version_suppressed": self.help_version_suppressed,
            "installation_identity_required": self.installation_identity_required,
            "limitations": list(self.limitations),
            "machine_readable_suppressed": self.machine_readable_suppressed,
            "missing_closed_stdin_suppressed": self.missing_closed_stdin_suppressed,
            "persistence_allowed": self.persistence_allowed,
            "piped_input_suppressed": self.piped_input_suppressed,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prompt_suppressed_in_non_interactive": (
                self.prompt_suppressed_in_non_interactive
            ),
            "quiet_mode_suppressed": self.quiet_mode_suppressed,
            "review_status": self.review_status,
            "shell_completion_suppressed": self.shell_completion_suppressed,
            "stdin_tty_required": self.stdin_tty_required,
            "transmission_allowed": self.transmission_allowed,
        }


def default_non_interactive_policy() -> CommunityTelemetryNonInteractivePolicy:
    return CommunityTelemetryNonInteractivePolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_ID",
    "COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_URN",
    "COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION",
    "CommunityTelemetryNonInteractivePolicy",
    "NonInteractivePolicyError",
    "default_non_interactive_policy",
]
