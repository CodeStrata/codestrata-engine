"""Repository aggregate analytics schema compatibility (Epic 10 Slice 10.5)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION,
)

_COMPATIBLE: frozenset[str] = frozenset(
    {COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION}
)


class RepositoryAggregateAnalyticsCompatibilityError(AnalyticsError):
    def __init__(self) -> None:
        super().__init__(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)


def compatible_repository_aggregate_schema_versions() -> frozenset[str]:
    return _COMPATIBLE


def assert_repository_aggregate_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE:
        raise RepositoryAggregateAnalyticsCompatibilityError()


def migrate_repository_aggregate_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    assert_repository_aggregate_schema_compatible(version)
    return dict(payload)


__all__ = [
    "RepositoryAggregateAnalyticsCompatibilityError",
    "assert_repository_aggregate_schema_compatible",
    "compatible_repository_aggregate_schema_versions",
    "migrate_repository_aggregate_mapping",
]
