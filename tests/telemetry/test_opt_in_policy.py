"""E13.1 opt-in policy contract."""

from __future__ import annotations

import pytest

from codestrata.telemetry.opt_in_policy import (
    ENGINE_OPT_IN_POLICY_ID,
    ENGINE_OPT_IN_POLICY_VERSION,
    EngineCollectionOptInPolicy,
    OptInPolicyError,
    default_opt_in_policy,
)


def test_default_policy_is_no_egress() -> None:
    policy = default_opt_in_policy()
    assert policy.policy_id == ENGINE_OPT_IN_POLICY_ID
    assert policy.policy_version == ENGINE_OPT_IN_POLICY_VERSION
    assert policy.disabled_by_default is True
    assert policy.environment_can_invent_consent is False
    assert policy.ci_can_invent_consent is False
    assert policy.evidence_transmission_available is False
    assert policy.graph_transmission_available is False
    assert policy.disable_cancels_pending is True
    assert policy.upload_failure_cannot_fail_analysis is True


def test_policy_rejects_egress_default() -> None:
    with pytest.raises(OptInPolicyError):
        EngineCollectionOptInPolicy(disabled_by_default=False)


def test_policy_rejects_ci_invented_consent() -> None:
    with pytest.raises(OptInPolicyError):
        EngineCollectionOptInPolicy(ci_can_invent_consent=True)


def test_policy_rejects_evidence_graph_availability() -> None:
    with pytest.raises(OptInPolicyError):
        EngineCollectionOptInPolicy(evidence_transmission_available=True)
    with pytest.raises(OptInPolicyError):
        EngineCollectionOptInPolicy(graph_transmission_available=True)


def test_stable_dict_is_sorted_and_versioned() -> None:
    payload = default_opt_in_policy().to_stable_dict()
    assert list(payload) == sorted(payload)
    assert payload["policy_token"] == (
        f"{ENGINE_OPT_IN_POLICY_ID}:{ENGINE_OPT_IN_POLICY_VERSION}"
    )
