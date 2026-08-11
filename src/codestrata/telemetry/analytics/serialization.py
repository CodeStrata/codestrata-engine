"""Stable serialization helpers for the analytics contract (Slice 10.1)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.analytics.events import AnalyticsEvent
from codestrata.telemetry.analytics.policy import CommunityAnonymousAnalyticsPolicy
from codestrata.telemetry.analytics.projection import AnalyticsProjection


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def analytics_policy_to_stable_json(policy: CommunityAnonymousAnalyticsPolicy) -> str:
    return _stable_json(policy.to_stable_dict())


def analytics_event_to_stable_json(event: AnalyticsEvent) -> str:
    return _stable_json(event.to_stable_dict())


def analytics_projection_to_stable_json(projection: AnalyticsProjection) -> str:
    return projection.to_stable_json()


__all__ = [
    "analytics_event_to_stable_json",
    "analytics_policy_to_stable_json",
    "analytics_projection_to_stable_json",
]
