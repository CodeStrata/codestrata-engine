"""Repository aggregate analytics validation (Epic 10 Slice 10.5)."""

from __future__ import annotations

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.repository_aggregate import (
    RepositoryAggregateAnalyticsEvent,
)
from codestrata.telemetry.analytics.repository_aggregate_compatibility import (
    assert_repository_aggregate_schema_compatible,
)
from codestrata.telemetry.analytics.repository_aggregate_input import (
    build_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION,
    COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION,
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)
from codestrata.telemetry.analytics.repository_aggregate_projection import (
    RepositoryAggregateAnalyticsProjection,
    project_repository_aggregate_analytics_event,
)
from codestrata.telemetry.analytics.validation import (
    assert_persistence_blocked,
    assert_transmission_blocked,
    validate_analytics_event,
)


def validate_repository_aggregate_analytics_event(
    event: RepositoryAggregateAnalyticsEvent,
    *,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsProjection:
    active = policy or default_repository_aggregate_analytics_policy()
    active.validate()
    assert_repository_aggregate_schema_compatible(event.schema_version)

    if event.policy_version != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if event.schema_version != COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION:
        raise AnalyticsError(AnalyticsErrorCode.INCOMPATIBLE_SCHEMA)
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if active.installation_id_required and not is_uuid_v4(event.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    if event.category != "repository_aggregates":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)

    # Re-normalize through input builder to enforce bounds/duplicates.
    build_repository_aggregate_input(
        language_mix=event.language_mix,
        rule_execution=event.rule_execution,
        rule_execution_by_head=event.rule_execution_by_head,
        policy=active,
    )

    projected = project_repository_aggregate_analytics_event(event, policy=active)
    validate_analytics_event(event.to_analytics_event())
    assert_persistence_blocked()
    assert_transmission_blocked()
    if active.persistence_enabled or active.transmission_enabled:
        raise AnalyticsError(AnalyticsErrorCode.TRANSMISSION_DISABLED)
    return projected


def validate_repository_aggregate_analytics_mapping(
    payload: dict,
    *,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsProjection:
    required = (
        "installation_id",
        "language_mix",
        "rule_execution",
        "event_type",
        "category",
        "privacy_projection_applied",
        "schema_version",
        "policy_version",
    )
    for key in required:
        if key not in payload:
            raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    languages = tuple(
        LanguageAggregate(
            language_group=str(item["language_group"]),
            count=int(item["count"]),
        )
        for item in payload["language_mix"]
    )
    rule = payload["rule_execution"]
    overall = RuleExecutionAggregate(
        attempted=int(rule["attempted"]),
        completed=int(rule["completed"]),
        skipped=int(rule["skipped"]),
        failed=int(rule["failed"]),
    )
    by_head = tuple(
        RuleExecutionAggregate(
            assessment_head=str(item["assessment_head"]),
            attempted=int(item["attempted"]),
            completed=int(item["completed"]),
            skipped=int(item["skipped"]),
            failed=int(item["failed"]),
        )
        for item in payload.get("rule_execution_by_head", [])
    )
    event = RepositoryAggregateAnalyticsEvent(
        installation_id=str(payload["installation_id"]),
        language_mix=languages,
        rule_execution=overall,
        rule_execution_by_head=by_head,
        event_type=str(payload.get("event_type", "analytics_repository_aggregates_collected")),
        category=str(payload.get("category", "repository_aggregates")),
        schema_version=str(
            payload.get(
                "schema_version", COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION
            )
        ),
        policy_version=str(
            payload.get(
                "policy_version", COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION
            )
        ),
        privacy_projection_applied=bool(payload["privacy_projection_applied"]),
    )
    return validate_repository_aggregate_analytics_event(event, policy=policy)


__all__ = [
    "validate_repository_aggregate_analytics_event",
    "validate_repository_aggregate_analytics_mapping",
]
