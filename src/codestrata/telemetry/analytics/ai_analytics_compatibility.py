"""AI analytics schema compatibility (Epic 10 Slice 10.6)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode

_COMPATIBLE: frozenset[str] = frozenset({COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION})


class AIAnalyticsCompatibilityError(AnalyticsError):
    """Raised when an unsupported AI analytics schema version is requested."""

    def __init__(self) -> None:
        super().__init__(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)


def compatible_ai_analytics_schema_versions() -> frozenset[str]:
    return _COMPATIBLE


def assert_ai_analytics_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE:
        raise AIAnalyticsCompatibilityError()


def migrate_ai_analytics_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """No-op migration hook for schema 1.0 only."""

    version = payload.get("schema_version", COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION)
    if not isinstance(version, str):
        raise AIAnalyticsCompatibilityError()
    assert_ai_analytics_schema_compatible(version)
    return dict(payload)


__all__ = [
    "AIAnalyticsCompatibilityError",
    "assert_ai_analytics_schema_compatible",
    "compatible_ai_analytics_schema_versions",
    "migrate_ai_analytics_mapping",
]
