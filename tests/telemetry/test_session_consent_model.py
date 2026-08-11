"""Per-session consent model and policy tests (Slice 9.3)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.consent import (
    SessionConsentError,
    TelemetrySessionConsent,
    allow_session_consent,
    default_session_consent,
    deny_session_consent,
)
from codestrata.telemetry.consent_policy import (
    COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_URN,
    CommunityTelemetrySessionConsentPolicy,
    SessionConsentPolicyError,
    default_session_consent_policy,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource


def test_default_consent_disabled() -> None:
    consent = default_session_consent()
    assert consent.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert consent.source is TelemetryDecisionSource.DEFAULT
    assert consent.explicit is False
    assert consent.persisted is False
    assert consent.prior_consent_reused is False
    assert consent.installation_identity_required is False
    assert consent.transmission_authorized is False
    assert consent.scope == "session"


def test_allow_and_deny_distinct() -> None:
    allow = allow_session_consent()
    deny = deny_session_consent()
    assert allow.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert allow.source is TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW
    assert allow.transmission_authorized is True
    assert deny.decision is TelemetryDecision.DENIED_FOR_SESSION
    assert deny.source is TelemetryDecisionSource.EXPLICIT_SESSION_DENY
    assert deny.transmission_authorized is False
    assert allow.to_stable_dict() != deny.to_stable_dict()


def test_consent_policy_defaults() -> None:
    policy = default_session_consent_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_URN
    assert policy.policy_version == "2.0"
    assert policy.persistence_allowed is True
    assert policy.prior_consent_reuse_allowed is True
    assert policy.consent_implies_transport is False


def test_O_P_Q_R_inconsistent_combinations_rejected() -> None:
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.DEFAULT,
            explicit=True,
            transmission_authorized=True,
        )
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.DENIED_FOR_SESSION,
            source=TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
            explicit=True,
            transmission_authorized=False,
        )
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.DISABLED_BY_DEFAULT,
            source=TelemetryDecisionSource.DEFAULT,
            explicit=True,
            transmission_authorized=False,
        )
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
            explicit=True,
            transmission_authorized=True,
            persisted=True,
        )
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
            explicit=True,
            transmission_authorized=True,
            prior_consent_reused=True,
        )
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.EXPLICIT_SESSION_ALLOW,
            explicit=True,
            transmission_authorized=True,
            installation_identity_required=True,
        )


def test_N_malformed_cli_flag_combinations_rejected() -> None:
    # disabled_by_default + cli_flag is invalid
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.DISABLED_BY_DEFAULT,
            source=TelemetryDecisionSource.CLI_FLAG,
            explicit=False,
            transmission_authorized=False,
        )
    # cli_flag allow with transmission_authorized=false
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.CLI_FLAG,
            explicit=True,
            transmission_authorized=False,
        )
    # cli_flag deny with transmission_authorized=true
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.DENIED_FOR_SESSION,
            source=TelemetryDecisionSource.CLI_FLAG,
            explicit=True,
            transmission_authorized=True,
        )
    # cli_flag with explicit=false
    with pytest.raises(SessionConsentError):
        TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.CLI_FLAG,
            explicit=False,
            transmission_authorized=True,
        )


def test_policy_rejects_disabled_persistence() -> None:
    with pytest.raises(SessionConsentPolicyError):
        CommunityTelemetrySessionConsentPolicy(persistence_allowed=False)
    with pytest.raises(SessionConsentPolicyError):
        CommunityTelemetrySessionConsentPolicy(prior_consent_reuse_allowed=False)
