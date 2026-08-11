"""Assessment analytics validation (Epic 10 Slice 10.4)."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.assessment_analytics import (
    APPROVED_COMMAND_CATEGORIES,
    APPROVED_OUTCOMES,
    AssessmentAnalyticsEvent,
    normalize_enabled_assessment_heads,
)
from codestrata.telemetry.analytics.assessment_analytics_compatibility import (
    assert_assessment_analytics_schema_compatible,
)
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION,
    CommunityAssessmentAnalyticsPolicy,
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    AssessmentAnalyticsProjection,
    project_assessment_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    _APPROVED_DURATION_BUCKETS,
    _APPROVED_FAILURE_CATEGORIES,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.validation import (
    assert_persistence_blocked,
    assert_transmission_blocked,
    validate_analytics_event,
)


def validate_assessment_analytics_event(
    event: AssessmentAnalyticsEvent,
    *,
    policy: CommunityAssessmentAnalyticsPolicy | None = None,
) -> AssessmentAnalyticsProjection:
    active = policy or default_assessment_analytics_policy()
    active.validate()
    assert_assessment_analytics_schema_compatible(event.schema_version)

    if event.policy_version != COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if event.schema_version != COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if active.installation_id_required and not is_uuid_v4(event.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    if event.category != "assessment":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if event.command_category not in APPROVED_COMMAND_CATEGORIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_COMMAND_CATEGORY)
    if event.duration_bucket not in _APPROVED_DURATION_BUCKETS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)
    if event.outcome not in APPROVED_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)

    if event.outcome == "success":
        if (
            event.failure_category is not None
            and active.failure_category_forbidden_on_success
        ):
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
    else:
        if (
            event.failure_category is None
            and active.failure_category_required_on_failure
        ):
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        if (
            event.failure_category is not None
            and event.failure_category not in _APPROVED_FAILURE_CATEGORIES
        ):
            raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)

    normalize_enabled_assessment_heads(
        event.enabled_assessment_heads, max_heads=active.max_enabled_heads
    )
    if tuple(event.enabled_assessment_heads) != tuple(
        sorted(event.enabled_assessment_heads)
    ):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    projected = project_assessment_analytics_event(event, policy=active)
    validate_analytics_event(event.to_analytics_event())
    assert_persistence_blocked()
    assert_transmission_blocked()
    if active.persistence_enabled or active.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    return projected


def validate_assessment_analytics_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityAssessmentAnalyticsPolicy | None = None,
) -> AssessmentAnalyticsProjection:
    required = (
        "installation_id",
        "command_category",
        "duration_bucket",
        "outcome",
        "enabled_assessment_heads",
        "event_type",
        "category",
        "privacy_projection_applied",
        "schema_version",
        "policy_version",
    )
    for key in required:
        if key not in payload:
            raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    heads_raw = payload["enabled_assessment_heads"]
    if not isinstance(heads_raw, (list, tuple)):
        raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)

    active = policy or default_assessment_analytics_policy()
    heads = normalize_enabled_assessment_heads(
        list(heads_raw), max_heads=active.max_enabled_heads
    )

    event = AssessmentAnalyticsEvent(
        installation_id=str(payload["installation_id"]),
        command_category=str(payload["command_category"]),
        duration_bucket=str(payload["duration_bucket"]),
        outcome=str(payload["outcome"]),
        enabled_assessment_heads=heads,
        offline_mode=bool(payload.get("offline_mode", True)),
        ai_requested=bool(payload.get("ai_requested", False)),
        ai_used=bool(payload.get("ai_used", False)),
        failure_category=(
            str(payload["failure_category"])
            if payload.get("failure_category") is not None
            else None
        ),
        event_type=str(payload.get("event_type", "analytics_assessment_collected")),
        category=str(payload.get("category", "assessment")),
        client_name=str(payload.get("client_name", "codestrata_cli")),
        lifecycle=str(payload.get("lifecycle", "projected")),
        schema_version=str(
            payload.get("schema_version", COMMUNITY_ASSESSMENT_ANALYTICS_SCHEMA_VERSION)
        ),
        policy_version=str(
            payload.get("policy_version", COMMUNITY_ASSESSMENT_ANALYTICS_POLICY_VERSION)
        ),
        analytics_schema_version=str(payload.get("analytics_schema_version", "1.0")),
        analytics_policy_version=str(payload.get("analytics_policy_version", "1.0")),
        privacy_projection_applied=bool(payload["privacy_projection_applied"]),
        operation_category=str(payload.get("operation_category", "assess")),
    )
    return validate_assessment_analytics_event(event, policy=policy)


__all__ = [
    "validate_assessment_analytics_event",
    "validate_assessment_analytics_mapping",
]
