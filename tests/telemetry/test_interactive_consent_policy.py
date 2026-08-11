"""Interactive consent prompt policy tests (Slice 9.4)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.prompt_policy import (
    COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_URN,
    CommunityTelemetryInteractiveConsentPolicy,
    InteractiveConsentPolicyError,
    default_interactive_consent_policy,
)


def test_interactive_policy_defaults() -> None:
    policy = default_interactive_consent_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_URN
    assert policy.policy_version == "2.0"
    assert policy.default_answer_deny is True
    assert policy.persistence_allowed is True
    assert policy.prior_consent_reuse_allowed is True
    assert policy.max_prompt_attempts == 1
    assert "assess" in policy.eligible_commands


def test_A_policy_rejects_default_allow() -> None:
    with pytest.raises(InteractiveConsentPolicyError):
        CommunityTelemetryInteractiveConsentPolicy(default_answer_deny=False)


def test_policy_rejects_disabled_persistence() -> None:
    with pytest.raises(InteractiveConsentPolicyError):
        CommunityTelemetryInteractiveConsentPolicy(persistence_allowed=False)
