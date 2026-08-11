"""Assessment analytics compatibility tests (Slice 10.4)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.assessment_analytics_compatibility import (
    AssessmentAnalyticsCompatibilityError,
    assert_assessment_analytics_schema_compatible,
    compatible_assessment_analytics_schema_versions,
    migrate_assessment_analytics_mapping,
)
from codestrata.telemetry.analytics.errors import AnalyticsError


def test_compatible_versions() -> None:
    assert compatible_assessment_analytics_schema_versions() == frozenset({"1.0"})


def test_assert_compatible() -> None:
    assert_assessment_analytics_schema_compatible("1.0")
    with pytest.raises(AssessmentAnalyticsCompatibilityError):
        assert_assessment_analytics_schema_compatible("1.1")


def test_migrate_noop() -> None:
    payload = {"schema_version": "1.0", "outcome": "success"}
    assert migrate_assessment_analytics_mapping(payload) == payload


def test_migrate_rejects_missing_version() -> None:
    with pytest.raises(AnalyticsError):
        migrate_assessment_analytics_mapping({"outcome": "success"})
