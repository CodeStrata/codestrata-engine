"""Transport policy tests (Slice 9.11)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.transport_policy import (
    COMMUNITY_TELEMETRY_TRANSPORT_POLICY_URN,
    CommunityTelemetryTransportPolicy,
    TransportPolicyError,
    default_transport_policy,
)


def test_default_policy_token() -> None:
    policy = default_transport_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_TRANSPORT_POLICY_URN
    assert policy.transport_disabled_by_default is True
    assert policy.maximum_attempts == 1
    assert policy.follow_redirects is False
    assert policy.use_environment_proxy is False
    assert policy.installation_id_allowed is False


def test_policy_rejects_unsafe_overrides() -> None:
    with pytest.raises(TransportPolicyError):
        CommunityTelemetryTransportPolicy(follow_redirects=True)
    with pytest.raises(TransportPolicyError):
        CommunityTelemetryTransportPolicy(installation_id_allowed=True)
    with pytest.raises(TransportPolicyError):
        CommunityTelemetryTransportPolicy(transport_disabled_by_default=False)


def test_policy_stable_dict_sorted() -> None:
    payload = default_transport_policy().to_stable_dict()
    assert list(payload.keys()) == sorted(payload.keys())
    assert "endpoint" not in payload
    assert "cscc_v1_" not in str(payload)
    assert "Authorization" not in str(payload)
