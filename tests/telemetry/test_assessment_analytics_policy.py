"""Assessment analytics policy tests (Epic 10 Slice 10.4)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN,
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN,
    AssessmentAnalyticsPolicyError,
    CommunityAssessmentAnalyticsPolicy,
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.assessment_analytics_serialization import (
    assessment_analytics_policy_to_stable_json,
)


def test_default_policy_invariants() -> None:
    policy = default_assessment_analytics_policy()
    assert policy.transmission_enabled is False
    assert policy.persistence_enabled is False
    assert policy.installation_id_required is True
    assert policy.command_category_assess_only is True
    assert policy.exact_duration_forbidden is True
    assert policy.fail_silent_optional_integration is True
    assert policy.max_enabled_heads == 9
    assert COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_URN.endswith(":1.0")
    assert COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_URN.endswith(":1.0")
    assert "not_wired_into_cli_product_path" in policy.limitations
    assert "repository_aggregates_deferred_to_slice_10_5" in policy.limitations


def test_policy_rejects_transmission() -> None:
    with pytest.raises(AssessmentAnalyticsPolicyError):
        CommunityAssessmentAnalyticsPolicy(transmission_enabled=True)
    with pytest.raises(AssessmentAnalyticsPolicyError):
        CommunityAssessmentAnalyticsPolicy(persistence_enabled=True)


def test_policy_serialization_deterministic() -> None:
    a = assessment_analytics_policy_to_stable_json(default_assessment_analytics_policy())
    b = assessment_analytics_policy_to_stable_json(
        CommunityAssessmentAnalyticsPolicy.default()
    )
    assert a == b
