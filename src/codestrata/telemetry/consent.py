"""Immutable per-session telemetry consent model (Slice 19.4).

Consent is an affirmative, purpose-specific decision. Explicit Yes/No may be
persisted locally under CODESTRATA_HOME and reused on later sessions. Default
remains disabled/undecided. Never inferred from queues, endpoints, or identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.consent_policy import (
    COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION,
    CommunityTelemetrySessionConsentPolicy,
    default_session_consent_policy,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource


class SessionConsentError(ValueError):
    """Raised when consent decision/source combinations are inconsistent."""


@dataclass(frozen=True, slots=True)
class TelemetrySessionConsent:
    """Frozen session consent — no identity, paths, or timestamps."""

    decision: TelemetryDecision
    source: TelemetryDecisionSource
    scope: str = "session"
    explicit: bool = False
    persisted: bool = False
    prior_consent_reused: bool = False
    installation_identity_required: bool = False
    transmission_authorized: bool = False
    policy_version: str = COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        policy = default_session_consent_policy()
        codes = tuple(sorted(set(self.limitations) | set(policy.limitations)))
        object.__setattr__(self, "limitations", codes)
        self.validate()

    def validate(self) -> None:
        if self.scope != "session":
            raise SessionConsentError("consent scope must be session")
        if self.installation_identity_required:
            raise SessionConsentError("installation_identity_required must be false")
        if self.policy_version != COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION:
            raise SessionConsentError("unsupported consent policy_version")
        if self.persisted and self.source is not TelemetryDecisionSource.PERSISTED_PREFERENCE:
            if self.source is not TelemetryDecisionSource.INTERACTIVE_PROMPT:
                raise SessionConsentError(
                    "persisted requires persisted_preference or interactive_prompt"
                )
        if self.prior_consent_reused and self.source is not (
            TelemetryDecisionSource.PERSISTED_PREFERENCE
        ):
            raise SessionConsentError(
                "prior_consent_reused requires source=persisted_preference"
            )
        if self.prior_consent_reused and not self.persisted:
            raise SessionConsentError(
                "prior_consent_reused requires persisted=true"
            )

        decision = self.decision
        source = self.source

        if decision is TelemetryDecision.DISABLED_BY_DEFAULT:
            if source is not TelemetryDecisionSource.DEFAULT:
                raise SessionConsentError(
                    "disabled_by_default requires source=default"
                )
            if self.explicit:
                raise SessionConsentError(
                    "disabled_by_default requires explicit=false"
                )
            if self.transmission_authorized:
                raise SessionConsentError(
                    "disabled_by_default requires transmission_authorized=false"
                )
            if self.persisted or self.prior_consent_reused:
                raise SessionConsentError(
                    "disabled_by_default must not be persisted or reused"
                )
            return

        if decision is TelemetryDecision.ALLOWED_FOR_SESSION:
            if source not in {
                TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
                TelemetryDecisionSource.INTERACTIVE_PROMPT,
                TelemetryDecisionSource.CLI_FLAG,
                TelemetryDecisionSource.PERSISTED_PREFERENCE,
            }:
                raise SessionConsentError(
                    "allowed_for_session requires explicit_session_allow, "
                    "interactive_prompt, cli_flag, or persisted_preference"
                )
            if not self.explicit:
                raise SessionConsentError("allowed_for_session requires explicit=true")
            if not self.transmission_authorized:
                raise SessionConsentError(
                    "allowed_for_session requires transmission_authorized=true"
                )
            return

        if decision is TelemetryDecision.DENIED_FOR_SESSION:
            if source not in {
                TelemetryDecisionSource.EXPLICIT_SESSION_DENY,
                TelemetryDecisionSource.INTERACTIVE_PROMPT,
                TelemetryDecisionSource.CLI_FLAG,
                TelemetryDecisionSource.PERSISTED_PREFERENCE,
            }:
                raise SessionConsentError(
                    "denied_for_session requires explicit_session_deny, "
                    "interactive_prompt, cli_flag, or persisted_preference"
                )
            if not self.explicit:
                raise SessionConsentError("denied_for_session requires explicit=true")
            if self.transmission_authorized:
                raise SessionConsentError(
                    "denied_for_session requires transmission_authorized=false"
                )
            return

        if decision is TelemetryDecision.NON_INTERACTIVE_DISABLED:
            if source is not TelemetryDecisionSource.NON_INTERACTIVE_POLICY:
                raise SessionConsentError(
                    "non_interactive_disabled requires source=non_interactive_policy"
                )
            if self.explicit:
                raise SessionConsentError(
                    "non_interactive_disabled requires explicit=false"
                )
            if self.transmission_authorized:
                raise SessionConsentError(
                    "non_interactive_disabled requires transmission_authorized=false"
                )
            if self.persisted or self.prior_consent_reused:
                raise SessionConsentError(
                    "non_interactive_disabled must not be persisted or reused"
                )
            return

        raise SessionConsentError(f"unsupported consent decision: {decision.value}")

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "explicit": self.explicit,
            "installation_identity_required": self.installation_identity_required,
            "limitations": list(self.limitations),
            "persisted": self.persisted,
            "policy_version": self.policy_version,
            "prior_consent_reused": self.prior_consent_reused,
            "scope": self.scope,
            "source": self.source.value,
            "transmission_authorized": self.transmission_authorized,
        }


def default_session_consent(
    *,
    policy: CommunityTelemetrySessionConsentPolicy | None = None,
) -> TelemetrySessionConsent:
    """Default: no decision — telemetry disabled for this process."""

    _ = policy or default_session_consent_policy()
    return TelemetrySessionConsent(
        decision=TelemetryDecision.DISABLED_BY_DEFAULT,
        source=TelemetryDecisionSource.DEFAULT,
        explicit=False,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=False,
    )


def allow_session_consent() -> TelemetrySessionConsent:
    """Explicit allow for the current process only — does not imply transport."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.ALLOWED_FOR_SESSION,
        source=TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
        explicit=True,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=True,
    )


def deny_session_consent() -> TelemetrySessionConsent:
    """Explicit deny for the current process — distinct from default."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.DENIED_FOR_SESSION,
        source=TelemetryDecisionSource.EXPLICIT_SESSION_DENY,
        explicit=True,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=False,
    )


def allow_session_consent_from_interactive_prompt(
    *,
    persisted: bool = True,
) -> TelemetrySessionConsent:
    """Allow from interactive prompt — persisted locally when policy allows."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.ALLOWED_FOR_SESSION,
        source=TelemetryDecisionSource.INTERACTIVE_PROMPT,
        explicit=True,
        persisted=persisted,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=True,
    )


def deny_session_consent_from_interactive_prompt(
    *,
    persisted: bool = True,
) -> TelemetrySessionConsent:
    """Deny from interactive prompt — persisted locally when policy allows."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.DENIED_FOR_SESSION,
        source=TelemetryDecisionSource.INTERACTIVE_PROMPT,
        explicit=True,
        persisted=persisted,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=False,
    )


def non_interactive_session_consent() -> TelemetrySessionConsent:
    """Suppressed non-interactive session — not user consent."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.NON_INTERACTIVE_DISABLED,
        source=TelemetryDecisionSource.NON_INTERACTIVE_POLICY,
        explicit=False,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=False,
    )


def allow_session_consent_from_cli_flag() -> TelemetrySessionConsent:
    """Allow from ``--telemetry-allow`` — current process only; not saved."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.ALLOWED_FOR_SESSION,
        source=TelemetryDecisionSource.CLI_FLAG,
        explicit=True,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=True,
    )


def deny_session_consent_from_cli_flag() -> TelemetrySessionConsent:
    """Deny from ``--telemetry-deny`` — current process only; not saved."""

    return TelemetrySessionConsent(
        decision=TelemetryDecision.DENIED_FOR_SESSION,
        source=TelemetryDecisionSource.CLI_FLAG,
        explicit=True,
        persisted=False,
        prior_consent_reused=False,
        installation_identity_required=False,
        transmission_authorized=False,
    )


__all__ = [
    "SessionConsentError",
    "TelemetrySessionConsent",
    "allow_session_consent",
    "allow_session_consent_from_cli_flag",
    "allow_session_consent_from_interactive_prompt",
    "default_session_consent",
    "deny_session_consent",
    "deny_session_consent_from_cli_flag",
    "deny_session_consent_from_interactive_prompt",
    "non_interactive_session_consent",
]
