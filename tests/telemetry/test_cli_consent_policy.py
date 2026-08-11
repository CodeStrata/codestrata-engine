"""CLI consent flag policy tests (Slice 9.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.cli_consent_policy import (
    COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_URN,
    CliConsentPolicyError,
    CommunityTelemetryCliConsentPolicy,
    default_cli_consent_policy,
)


def test_cli_consent_policy_defaults() -> None:
    policy = default_cli_consent_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_URN
    assert policy.persistence_allowed is False
    assert policy.queue_or_http_allowed is False
    assert policy.environment_variable_equivalent is False
    assert "assess" in policy.supported_commands


def test_policy_rejects_persistence() -> None:
    with pytest.raises(CliConsentPolicyError):
        CommunityTelemetryCliConsentPolicy(persistence_allowed=True)


def test_policy_rejects_env_equivalent() -> None:
    with pytest.raises(CliConsentPolicyError):
        CommunityTelemetryCliConsentPolicy(environment_variable_equivalent=True)
