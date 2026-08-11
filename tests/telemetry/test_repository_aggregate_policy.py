"""Repository aggregate analytics policy tests (Slice 10.5)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.repository_aggregate_policy import (
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN,
    RepositoryAggregateAnalyticsPolicyError,
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)
from codestrata.telemetry.analytics.repository_aggregate_serialization import (
    repository_aggregate_policy_to_stable_json,
)


def test_default_policy() -> None:
    policy = default_repository_aggregate_analytics_policy()
    assert policy.transmission_enabled is False
    assert policy.persistence_enabled is False
    assert policy.bounded_exact_counts is True
    assert policy.max_language_file_count == 10_000
    assert "not_wired_into_cli_product_path" in policy.limitations
    assert "ai_analytics_owned_by_slice_10_6" in policy.limitations
    assert COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_URN.endswith(":1.0")


def test_policy_rejects_transmission() -> None:
    with pytest.raises(RepositoryAggregateAnalyticsPolicyError):
        CommunityRepositoryAggregateAnalyticsPolicy(transmission_enabled=True)


def test_policy_json_deterministic() -> None:
    a = repository_aggregate_policy_to_stable_json(
        default_repository_aggregate_analytics_policy()
    )
    b = repository_aggregate_policy_to_stable_json(
        CommunityRepositoryAggregateAnalyticsPolicy.default()
    )
    assert a == b
