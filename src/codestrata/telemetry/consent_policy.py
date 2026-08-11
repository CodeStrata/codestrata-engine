"""Independent per-session telemetry consent policy (Slice 19.4).

Engine-local product-policy contract. Explicit Yes/No may be persisted locally
under CODESTRATA_HOME; default remains disabled/undecided. Independent from
Community Cloud / Data Lake contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_ID = (
    "community-telemetry-session-consent-policy"
)
COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION = "2.0"
COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION}"
)

_REVIEW_STATUS = "explicit_local_preference_with_session_runtime"

_LIMITATIONS: tuple[str, ...] = (
    "default_disabled",
    "explicit_opt_in_required",
    "local_preference_persistence",
    "no_default_yes",
    "no_installation_identity_required",
    "consent_does_not_imply_transport",
    "no_source_code_or_repository_identity",
)


class SessionConsentPolicyError(ValueError):
    """Raised when session-consent policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetrySessionConsentPolicy:
    """Deterministic, versioned per-session consent product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION
    scope: str = "session"
    process_local: bool = True
    persistence_allowed: bool = True
    prior_consent_reuse_allowed: bool = True
    installation_identity_required: bool = False
    interactive_prompt_enabled: bool = True
    cli_flag_enabled: bool = True
    consent_implies_transport: bool = False
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_ID:
            raise SessionConsentPolicyError("unsupported session consent policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION:
            raise SessionConsentPolicyError("unsupported session consent policy version")
        if self.scope != "session":
            raise SessionConsentPolicyError("consent scope must be session")
        if not self.process_local:
            raise SessionConsentPolicyError("process_local must be true")
        if not self.persistence_allowed:
            raise SessionConsentPolicyError("persistence_allowed must be true")
        if not self.prior_consent_reuse_allowed:
            raise SessionConsentPolicyError("prior_consent_reuse_allowed must be true")
        if self.installation_identity_required:
            raise SessionConsentPolicyError(
                "installation_identity_required must be false"
            )
        if self.consent_implies_transport:
            raise SessionConsentPolicyError("consent_implies_transport must be false")
        if self.review_status != _REVIEW_STATUS:
            raise SessionConsentPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetrySessionConsentPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "cli_flag_enabled": self.cli_flag_enabled,
            "consent_implies_transport": self.consent_implies_transport,
            "installation_identity_required": self.installation_identity_required,
            "interactive_prompt_enabled": self.interactive_prompt_enabled,
            "limitations": list(self.limitations),
            "persistence_allowed": self.persistence_allowed,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "prior_consent_reuse_allowed": self.prior_consent_reuse_allowed,
            "process_local": self.process_local,
            "review_status": self.review_status,
            "scope": self.scope,
        }


def default_session_consent_policy() -> CommunityTelemetrySessionConsentPolicy:
    return CommunityTelemetrySessionConsentPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_ID",
    "COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_URN",
    "COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION",
    "CommunityTelemetrySessionConsentPolicy",
    "SessionConsentPolicyError",
    "default_session_consent_policy",
]
