"""Runtime analytics schema compatibility (Epic 10 Slice 10.3)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.runtime_analytics import (
    COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION,
)

_COMPATIBLE_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {COMMUNITY_RUNTIME_ANALYTICS_SCHEMA_VERSION}
)


class RuntimeAnalyticsCompatibilityError(AnalyticsError):
    """Raised when a runtime analytics schema version is unsupported."""

    def __init__(self) -> None:
        super().__init__(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)


def compatible_runtime_analytics_schema_versions() -> frozenset[str]:
    return _COMPATIBLE_SCHEMA_VERSIONS


def assert_runtime_analytics_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE_SCHEMA_VERSIONS:
        raise RuntimeAnalyticsCompatibilityError()


def migrate_runtime_analytics_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Future-compatible migration hook — schema 1.0 is a no-op."""

    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    assert_runtime_analytics_schema_compatible(version)
    return dict(payload)


__all__ = [
    "RuntimeAnalyticsCompatibilityError",
    "assert_runtime_analytics_schema_compatible",
    "compatible_runtime_analytics_schema_versions",
    "migrate_runtime_analytics_mapping",
]
