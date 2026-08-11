"""AI analytics policy tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_URN,
    COMMUNITY_AI_ANALYTICS_SCHEMA_URN,
    AIAnalyticsPolicyError,
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)


def test_default_policy_tokens() -> None:
    policy = default_ai_analytics_policy()
    assert policy.policy_token == COMMUNITY_AI_ANALYTICS_POLICY_URN
    assert policy.schema_token == COMMUNITY_AI_ANALYTICS_SCHEMA_URN
    assert policy.persistence_enabled is False
    assert policy.transmission_enabled is False
    assert policy.token_usage_bucket_allowed is False
    assert policy.tool_rag_graph_allowed is False
    assert "openrouter_family_only_no_endpoints_or_keys" in policy.limitations
    assert "ai_provider_platform_redesign_deferred" in policy.limitations
    assert "vscode_analytics_deferred_to_slice_10_7" in policy.limitations


def test_policy_rejects_persistence() -> None:
    with pytest.raises(AIAnalyticsPolicyError):
        CommunityAIAnalyticsPolicy(persistence_enabled=True)


def test_policy_rejects_transmission() -> None:
    with pytest.raises(AIAnalyticsPolicyError):
        CommunityAIAnalyticsPolicy(transmission_enabled=True)


def test_policy_rejects_token_buckets() -> None:
    with pytest.raises(AIAnalyticsPolicyError):
        CommunityAIAnalyticsPolicy(token_usage_bucket_allowed=True)


def test_stable_dict_deterministic() -> None:
    a = default_ai_analytics_policy().to_stable_dict()
    b = default_ai_analytics_policy().to_stable_dict()
    assert a == b
    assert list(a) == sorted(a)
