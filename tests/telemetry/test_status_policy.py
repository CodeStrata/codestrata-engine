"""Status policy tests (Slice 9.7)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.status_policy import (
    COMMUNITY_TELEMETRY_STATUS_POLICY_URN,
    CommunityTelemetryStatusPolicy,
    TelemetryStatusPolicyError,
    default_status_policy,
)


def test_status_policy_defaults() -> None:
    policy = default_status_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_STATUS_POLICY_URN
    assert policy.telemetry_enabled_by_default is False
    assert policy.transmission_available is False
    assert policy.installation_identity_used is False
    assert policy.status_side_effect_free is True
    assert policy.inspect_legacy_filesystem is False
    assert "assess" in policy.prompt_command_scope


def test_policy_rejects_transmission() -> None:
    with pytest.raises(TelemetryStatusPolicyError):
        CommunityTelemetryStatusPolicy(transmission_available=True)


def test_policy_rejects_legacy_inspection() -> None:
    with pytest.raises(TelemetryStatusPolicyError):
        CommunityTelemetryStatusPolicy(inspect_legacy_filesystem=True)
