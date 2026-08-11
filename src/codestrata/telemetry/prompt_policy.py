"""Independent interactive telemetry consent prompt policy (Slice 19.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_ID = (
    "community-telemetry-interactive-consent-policy"
)
COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION = "2.0"
COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION}"
)

_REVIEW_STATUS = "interactive_prompt_persist_explicit_local_preference"

_LIMITATIONS: tuple[str, ...] = (
    "one_prompt_maximum_per_process",
    "skip_when_preference_decided",
    "default_answer_deny",
    "empty_answer_denied",
    "invalid_answer_denied",
    "interruption_denied",
    "eof_denied",
    "local_preference_persistence",
    "no_installation_identity",
    "no_transmission_guarantee",
    "help_version_excluded",
    "telemetry_inspection_excluded",
    "non_interactive_policy_enforced",
    "no_source_code_or_repository_identity",
)

ELIGIBLE_COMMANDS: frozenset[str] = frozenset({"assess"})
EXCLUDED_COMMANDS: frozenset[str] = frozenset(
    {
        "help",
        "version",
        "about",
        "welcome",
        "telemetry",
        "telemetry status",
        "telemetry enable",
        "telemetry disable",
        "telemetry reset",
        "telemetry show",
        "completion",
        "install-completion",
        "show-completion",
    }
)

MAX_PROMPT_ATTEMPTS = 1


class InteractiveConsentPolicyError(ValueError):
    """Raised when interactive-consent prompt policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryInteractiveConsentPolicy:
    """Versioned interactive prompt product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION
    prompt_enabled_for_eligible_interactive_session: bool = True
    one_prompt_maximum_per_process: bool = True
    current_session_scope: bool = True
    default_answer_deny: bool = True
    empty_answer_denied: bool = True
    invalid_answer_denied: bool = True
    interruption_denied: bool = True
    eof_denied: bool = True
    persistence_allowed: bool = True
    prior_consent_reuse_allowed: bool = True
    installation_identity_required: bool = False
    transmission_guaranteed: bool = False
    max_prompt_attempts: int = MAX_PROMPT_ATTEMPTS
    eligible_commands: tuple[str, ...] = tuple(sorted(ELIGIBLE_COMMANDS))
    excluded_commands: tuple[str, ...] = tuple(sorted(EXCLUDED_COMMANDS))
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "eligible_commands", tuple(sorted(set(self.eligible_commands))))
        object.__setattr__(self, "excluded_commands", tuple(sorted(set(self.excluded_commands))))
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_ID:
            raise InteractiveConsentPolicyError("unsupported interactive prompt policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION:
            raise InteractiveConsentPolicyError(
                "unsupported interactive prompt policy version"
            )
        if not self.default_answer_deny:
            raise InteractiveConsentPolicyError("default_answer_deny must be true")
        if not self.persistence_allowed:
            raise InteractiveConsentPolicyError("persistence_allowed must be true")
        if not self.prior_consent_reuse_allowed:
            raise InteractiveConsentPolicyError(
                "prior_consent_reuse_allowed must be true"
            )
        if self.installation_identity_required:
            raise InteractiveConsentPolicyError(
                "installation_identity_required must be false"
            )
        if self.transmission_guaranteed:
            raise InteractiveConsentPolicyError("transmission_guaranteed must be false")
        if self.max_prompt_attempts != 1:
            raise InteractiveConsentPolicyError("max_prompt_attempts must be 1")
        if self.review_status != _REVIEW_STATUS:
            raise InteractiveConsentPolicyError("unsupported review_status")
        if "assess" not in self.eligible_commands:
            raise InteractiveConsentPolicyError("assess must remain eligible")

    @classmethod
    def default(cls) -> CommunityTelemetryInteractiveConsentPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "current_session_scope": self.current_session_scope,
            "default_answer_deny": self.default_answer_deny,
            "eligible_commands": list(self.eligible_commands),
            "empty_answer_denied": self.empty_answer_denied,
            "eof_denied": self.eof_denied,
            "excluded_commands": list(self.excluded_commands),
            "installation_identity_required": self.installation_identity_required,
            "interruption_denied": self.interruption_denied,
            "invalid_answer_denied": self.invalid_answer_denied,
            "limitations": list(self.limitations),
            "max_prompt_attempts": self.max_prompt_attempts,
            "one_prompt_maximum_per_process": self.one_prompt_maximum_per_process,
            "persistence_allowed": self.persistence_allowed,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prior_consent_reuse_allowed": self.prior_consent_reuse_allowed,
            "prompt_enabled_for_eligible_interactive_session": (
                self.prompt_enabled_for_eligible_interactive_session
            ),
            "review_status": self.review_status,
            "transmission_guaranteed": self.transmission_guaranteed,
        }


def default_interactive_consent_policy() -> CommunityTelemetryInteractiveConsentPolicy:
    return CommunityTelemetryInteractiveConsentPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_ID",
    "COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_URN",
    "COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION",
    "CommunityTelemetryInteractiveConsentPolicy",
    "ELIGIBLE_COMMANDS",
    "EXCLUDED_COMMANDS",
    "InteractiveConsentPolicyError",
    "MAX_PROMPT_ATTEMPTS",
    "default_interactive_consent_policy",
]
