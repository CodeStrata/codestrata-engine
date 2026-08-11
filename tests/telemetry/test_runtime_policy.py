"""Runtime policy contract tests (Slice 9.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN,
    CommunityTelemetryRuntimePolicy,
    RuntimePolicyError,
    default_runtime_policy,
)


def test_default_policy_disabled_by_default() -> None:
    policy = default_runtime_policy()
    assert policy.disabled_by_default is True
    assert policy.consent_prompt_enabled is False
    assert policy.automatic_prior_consent_reuse is False
    assert policy.installation_id_allowed is False
    assert policy.transport_unavailable_by_default is True
    assert policy.policy_token == COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN
    assert policy.to_stable_dict()["disabled_by_default"] is True


def test_policy_rejects_enabled_by_default() -> None:
    with pytest.raises(RuntimePolicyError):
        CommunityTelemetryRuntimePolicy(disabled_by_default=False)


def test_policy_rejects_consent_prompt() -> None:
    with pytest.raises(RuntimePolicyError):
        CommunityTelemetryRuntimePolicy(consent_prompt_enabled=True)


def test_policy_rejects_prior_consent_reuse() -> None:
    with pytest.raises(RuntimePolicyError):
        CommunityTelemetryRuntimePolicy(automatic_prior_consent_reuse=True)


def test_policy_stable_dict_deterministic() -> None:
    a = default_runtime_policy().to_stable_dict()
    b = default_runtime_policy().to_stable_dict()
    assert a == b
    assert list(a.keys()) == sorted(a.keys())
