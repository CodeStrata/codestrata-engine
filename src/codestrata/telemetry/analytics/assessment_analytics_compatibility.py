"""Assessment analytics schema compatibility (Epic 10 Slice 10.4)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode

_COMPATIBLE_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION}
)


class AssessmentAnalyticsCompatibilityError(AnalyticsError):
    """Raised when an assessment analytics schema version is unsupported."""

    def __init__(self) -> None:
        super().__init__(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)


def compatible_assessment_analytics_schema_versions() -> frozenset[str]:
    return _COMPATIBLE_SCHEMA_VERSIONS


def assert_assessment_analytics_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE_SCHEMA_VERSIONS:
        raise AssessmentAnalyticsCompatibilityError()


def migrate_assessment_analytics_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Future-compatible migration hook — schema 1.0 is a no-op."""

    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    assert_assessment_analytics_schema_compatible(version)
    return dict(payload)


__all__ = [
    "AssessmentAnalyticsCompatibilityError",
    "assert_assessment_analytics_schema_compatible",
    "compatible_assessment_analytics_schema_versions",
    "migrate_assessment_analytics_mapping",
]
