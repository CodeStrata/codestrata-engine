"""Deterministic serialization for assessment analytics (Slice 10.4)."""

from __future__ import annotations

import json
from typing import Any

from codestrata.telemetry.analytics.assessment_analytics import AssessmentAnalyticsEvent
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    CommunityAssessmentAnalyticsPolicy,
)
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    AssessmentAnalyticsProjection,
)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def assessment_analytics_event_to_stable_json(event: AssessmentAnalyticsEvent) -> str:
    return _stable_json(event.to_stable_dict())


def assessment_analytics_policy_to_stable_json(
    policy: CommunityAssessmentAnalyticsPolicy,
) -> str:
    return _stable_json(policy.to_stable_dict())


def assessment_analytics_projection_to_stable_json(
    projection: AssessmentAnalyticsProjection,
) -> str:
    return projection.to_stable_json()


__all__ = [
    "assessment_analytics_event_to_stable_json",
    "assessment_analytics_policy_to_stable_json",
    "assessment_analytics_projection_to_stable_json",
]
