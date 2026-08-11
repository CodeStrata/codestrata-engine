"""Identity-free AI analytics input (Epic 10 Slice 10.6).

Accepts only already-bounded catalog categories. Never carries provider clients,
prompts, responses, credentials, or exact model IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    APPROVED_AI_CAPABILITIES,
    APPROVED_AI_FAILURE_CATEGORIES,
    APPROVED_AI_MODEL_FAMILIES,
    APPROVED_AI_OUTCOMES,
    APPROVED_AI_PROVIDER_FAMILIES,
    APPROVED_AI_PROVIDER_OWNERSHIPS,
)
from codestrata.telemetry.analytics.ai_analytics_mapping import canonicalize_capability
from codestrata.telemetry.analytics.ai_analytics_policy import (
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import _APPROVED_DURATION_BUCKETS


@dataclass(frozen=True, slots=True)
class AIAnalyticsInput:
    """Privacy-safe aggregate source for AI analytics projection."""

    capability: str
    provider_family: str
    model_family: str
    provider_ownership: str
    outcome: str
    failure_category: str | None = None
    duration_bucket: str | None = None
    ai_used: bool | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "capability": self.capability,
            "model_family": self.model_family,
            "outcome": self.outcome,
            "provider_family": self.provider_family,
            "provider_ownership": self.provider_ownership,
        }
        if self.ai_used is not None:
            payload["ai_used"] = self.ai_used
        if self.duration_bucket is not None:
            payload["duration_bucket"] = self.duration_bucket
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        return {key: payload[key] for key in sorted(payload)}


def build_ai_analytics_input(
    *,
    capability: str,
    provider_family: str,
    model_family: str,
    provider_ownership: str,
    outcome: str,
    failure_category: str | None = None,
    duration_bucket: str | None = None,
    ai_used: bool | None = None,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsInput:
    """Build typed input from bounded catalog values only."""

    active = policy or default_ai_analytics_policy()
    active.validate()

    cap = canonicalize_capability(capability)
    if provider_family not in APPROVED_AI_PROVIDER_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_FAMILY)
    if model_family not in APPROVED_AI_MODEL_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)
    if provider_ownership not in APPROVED_AI_PROVIDER_OWNERSHIPS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_OWNERSHIP)
    if outcome not in APPROVED_AI_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)
    if duration_bucket is not None and duration_bucket not in _APPROVED_DURATION_BUCKETS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)

    if outcome == "success":
        if failure_category is not None and active.failure_category_forbidden_on_success:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
    elif outcome in {"failure", "unavailable"}:
        if failure_category is None and active.failure_category_required_on_failure:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        if (
            failure_category is not None
            and failure_category not in APPROVED_AI_FAILURE_CATEGORIES
        ):
            raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)
    else:
        # skipped: failure_category must be absent (not a provider failure).
        if failure_category is not None:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)

    if cap not in APPROVED_AI_CAPABILITIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_CAPABILITY)

    return AIAnalyticsInput(
        capability=cap,
        provider_family=provider_family,
        model_family=model_family,
        provider_ownership=provider_ownership,
        outcome=outcome,
        failure_category=failure_category,
        duration_bucket=duration_bucket,
        ai_used=ai_used,
    )


__all__ = [
    "AIAnalyticsInput",
    "build_ai_analytics_input",
]
