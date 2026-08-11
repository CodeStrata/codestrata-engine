"""Deterministic serialization for repository aggregate analytics (Slice 10.5)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.analytics.repository_aggregate import (
    RepositoryAggregateAnalyticsEvent,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    CommunityRepositoryAggregateAnalyticsPolicy,
)
from codestrata.telemetry.analytics.repository_aggregate_projection import (
    RepositoryAggregateAnalyticsProjection,
)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def repository_aggregate_event_to_stable_json(
    event: RepositoryAggregateAnalyticsEvent,
) -> str:
    return _stable_json(event.to_stable_dict())


def repository_aggregate_policy_to_stable_json(
    policy: CommunityRepositoryAggregateAnalyticsPolicy,
) -> str:
    return _stable_json(policy.to_stable_dict())


def repository_aggregate_projection_to_stable_json(
    projection: RepositoryAggregateAnalyticsProjection,
) -> str:
    return projection.to_stable_json()


__all__ = [
    "repository_aggregate_event_to_stable_json",
    "repository_aggregate_policy_to_stable_json",
    "repository_aggregate_projection_to_stable_json",
]
