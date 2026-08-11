"""Analytics schema version compatibility framework (Epic 10 Slice 10.1)."""

from __future__ import annotations

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

# Forward-compatible reader matrix for the analytics schema (contract only).
# Slice 10.1 only recognizes schema 1.0.
_COMPATIBLE_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION}
)


class AnalyticsCompatibilityError(AnalyticsError):
    """Raised when an analytics schema version is unsupported."""

    def __init__(self) -> None:
        super().__init__(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)


def compatible_schema_versions() -> frozenset[str]:
    return _COMPATIBLE_SCHEMA_VERSIONS


def assert_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE_SCHEMA_VERSIONS:
        raise AnalyticsCompatibilityError()


__all__ = [
    "AnalyticsCompatibilityError",
    "assert_schema_compatible",
    "compatible_schema_versions",
]
