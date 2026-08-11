"""AI analytics validation (Epic 10 Slice 10.6)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    APPROVED_AI_CAPABILITIES,
    APPROVED_AI_FAILURE_CATEGORIES,
    APPROVED_AI_MODEL_FAMILIES,
    APPROVED_AI_OUTCOMES,
    APPROVED_AI_PROVIDER_FAMILIES,
    APPROVED_AI_PROVIDER_OWNERSHIPS,
)
from codestrata.telemetry.analytics.ai_analytics_compatibility import (
    assert_ai_analytics_schema_compatible,
)
from codestrata.telemetry.analytics.ai_analytics_models import AIAnalyticsEvent
from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_VERSION,
    COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION,
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.ai_analytics_projection import (
    AIAnalyticsProjection,
    project_ai_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import _APPROVED_DURATION_BUCKETS
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.validation import (
    assert_persistence_blocked,
    assert_transmission_blocked,
    validate_analytics_event,
)


def _validate_outcome_failure(
    outcome: str,
    failure_category: str | None,
    *,
    policy: CommunityAIAnalyticsPolicy,
) -> None:
    if outcome == "success":
        if failure_category is not None and policy.failure_category_forbidden_on_success:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        return
    if outcome == "skipped":
        if failure_category is not None:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        return
    if outcome in {"failure", "unavailable"}:
        if failure_category is None and policy.failure_category_required_on_failure:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        if (
            failure_category is not None
            and failure_category not in APPROVED_AI_FAILURE_CATEGORIES
        ):
            raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)
        return
    raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)


def validate_ai_analytics_event(
    event: AIAnalyticsEvent,
    *,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsProjection:
    active = policy or default_ai_analytics_policy()
    active.validate()
    assert_ai_analytics_schema_compatible(event.schema_version)

    if event.policy_version != COMMUNITY_AI_ANALYTICS_POLICY_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if event.schema_version != COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if active.installation_id_required and not is_uuid_v4(event.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    if event.category != "ai_usage":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if event.capability not in APPROVED_AI_CAPABILITIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_CAPABILITY)
    if event.provider_family not in APPROVED_AI_PROVIDER_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_FAMILY)
    if event.model_family not in APPROVED_AI_MODEL_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)
    if event.provider_ownership not in APPROVED_AI_PROVIDER_OWNERSHIPS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_OWNERSHIP)
    if event.outcome not in APPROVED_AI_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)
    if (
        event.duration_bucket is not None
        and event.duration_bucket not in _APPROVED_DURATION_BUCKETS
    ):
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)

    _validate_outcome_failure(
        event.outcome, event.failure_category, policy=active
    )

    projected = project_ai_analytics_event(event, policy=active)
    validate_analytics_event(event.to_analytics_event())
    assert_persistence_blocked()
    assert_transmission_blocked()
    if active.persistence_enabled or active.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    return projected


def validate_ai_analytics_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsProjection:
    required = (
        "installation_id",
        "capability",
        "provider_family",
        "model_family",
        "provider_ownership",
        "outcome",
        "event_type",
        "category",
        "privacy_projection_applied",
        "schema_version",
        "policy_version",
    )
    for key in required:
        if key not in payload:
            raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    event = AIAnalyticsEvent(
        installation_id=str(payload["installation_id"]),
        capability=str(payload["capability"]),
        provider_family=str(payload["provider_family"]),
        model_family=str(payload["model_family"]),
        provider_ownership=str(payload["provider_ownership"]),
        outcome=str(payload["outcome"]),
        failure_category=(
            str(payload["failure_category"])
            if payload.get("failure_category") is not None
            else None
        ),
        duration_bucket=(
            str(payload["duration_bucket"])
            if payload.get("duration_bucket") is not None
            else None
        ),
        ai_used=(
            bool(payload["ai_used"]) if payload.get("ai_used") is not None else None
        ),
        event_type=str(payload.get("event_type", "analytics_ai_usage_collected")),
        category=str(payload.get("category", "ai_usage")),
        client_name=str(payload.get("client_name", "codestrata_cli")),
        lifecycle=str(payload.get("lifecycle", "projected")),
        schema_version=str(
            payload.get("schema_version", COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION)
        ),
        policy_version=str(
            payload.get("policy_version", COMMUNITY_AI_ANALYTICS_POLICY_VERSION)
        ),
        analytics_schema_version=str(payload.get("analytics_schema_version", "1.0")),
        analytics_policy_version=str(payload.get("analytics_policy_version", "1.0")),
        privacy_projection_applied=bool(payload["privacy_projection_applied"]),
        operation_category=str(payload.get("operation_category", "other")),
    )
    return validate_ai_analytics_event(event, policy=policy)


__all__ = [
    "validate_ai_analytics_event",
    "validate_ai_analytics_mapping",
]
