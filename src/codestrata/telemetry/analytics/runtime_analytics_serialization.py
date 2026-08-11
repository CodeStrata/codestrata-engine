"""Deterministic serialization for runtime analytics (Slice 10.3)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.analytics.runtime_analytics import (
    CommunityRuntimeAnalyticsPolicy,
    RuntimeAnalyticsEvent,
)
from codestrata.telemetry.analytics.runtime_analytics_projection import (
    RuntimeAnalyticsProjection,
)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def runtime_analytics_event_to_stable_json(event: RuntimeAnalyticsEvent) -> str:
    return _stable_json(event.to_stable_dict())


def runtime_analytics_policy_to_stable_json(
    policy: CommunityRuntimeAnalyticsPolicy,
) -> str:
    return _stable_json(policy.to_stable_dict())


def runtime_analytics_projection_to_stable_json(
    projection: RuntimeAnalyticsProjection,
) -> str:
    return projection.to_stable_json()


__all__ = [
    "runtime_analytics_event_to_stable_json",
    "runtime_analytics_policy_to_stable_json",
    "runtime_analytics_projection_to_stable_json",
]
