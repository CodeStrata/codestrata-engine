"""AI analytics serialization (Epic 10 Slice 10.6)."""

from __future__ import annotations

import json

from codestrata.telemetry.analytics.ai_analytics_models import AIAnalyticsEvent
from codestrata.telemetry.analytics.ai_analytics_policy import (
    CommunityAIAnalyticsPolicy,
)
from codestrata.telemetry.analytics.ai_analytics_projection import AIAnalyticsProjection


def ai_analytics_policy_to_stable_json(policy: CommunityAIAnalyticsPolicy) -> str:
    return json.dumps(
        policy.to_stable_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def ai_analytics_event_to_stable_json(event: AIAnalyticsEvent) -> str:
    return json.dumps(
        event.to_stable_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def ai_analytics_projection_to_stable_json(
    projection: AIAnalyticsProjection,
) -> str:
    return projection.to_stable_json()


__all__ = [
    "ai_analytics_event_to_stable_json",
    "ai_analytics_policy_to_stable_json",
    "ai_analytics_projection_to_stable_json",
]
