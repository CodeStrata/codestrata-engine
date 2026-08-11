"""AI analytics compatibility tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_compatibility import (
    AIAnalyticsCompatibilityError,
    assert_ai_analytics_schema_compatible,
    compatible_ai_analytics_schema_versions,
    migrate_ai_analytics_mapping,
)
from codestrata.telemetry.analytics.events import (
    APPROVED_ANALYTICS_FIELD_NAMES,
    AnalyticsCategory,
    AnalyticsEvent,
)
from codestrata.telemetry.analytics.projection import project_analytics_event


def test_compatible_versions_only_1_0() -> None:
    assert compatible_ai_analytics_schema_versions() == frozenset({"1.0"})
    assert_ai_analytics_schema_compatible("1.0")


def test_future_version_rejected() -> None:
    with pytest.raises(AIAnalyticsCompatibilityError):
        assert_ai_analytics_schema_compatible("2.0")


def test_migrate_noop_1_0() -> None:
    payload = {"schema_version": "1.0", "capability": "modernization_advisor"}
    assert migrate_ai_analytics_mapping(payload) == payload


def test_base_event_additive_ai_fields_compatible() -> None:
    for name in (
        "capability",
        "provider_family",
        "model_family",
        "provider_ownership",
    ):
        assert name in APPROVED_ANALYTICS_FIELD_NAMES
    event = AnalyticsEvent(
        event_type="analytics_ai_usage_collected",
        category=AnalyticsCategory.AI_USAGE,
        privacy_projection_applied=True,
        result="success",
        capability="modernization_advisor",
        provider_family="openai",
        model_family="gpt_family",
        provider_ownership="customer_managed",
        operation_category="other",
        ai_used=True,
    )
    projected = project_analytics_event(event)
    assert projected.fields["capability"] == "modernization_advisor"
    assert "installation_id" not in projected.fields
