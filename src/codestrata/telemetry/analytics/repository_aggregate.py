"""Repository aggregate analytics event and local construction (Epic 10 Slice 10.5).

Construction-API only — not wired into assess. No transmission. No analytics
persistence. May ensure anonymous installation identity only when explicitly
invoked without a provided identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    ensure_anonymous_installation_identity,
    is_uuid_v4,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)
from codestrata.telemetry.analytics.repository_aggregate_input import (
    RepositoryAggregateAnalyticsInput,
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

REPOSITORY_AGGREGATE_ANALYTICS_EVENT_TYPE = "analytics_repository_aggregates_collected"


@dataclass(frozen=True, slots=True)
class RepositoryAggregateAnalyticsEvent:
    """Local repository aggregate analytics record."""

    installation_id: str
    language_mix: tuple[LanguageAggregate, ...]
    rule_execution: RuleExecutionAggregate
    rule_execution_by_head: tuple[RuleExecutionAggregate, ...] = ()
    event_type: str = REPOSITORY_AGGREGATE_ANALYTICS_EVENT_TYPE
    category: str = AnalyticsCategory.REPOSITORY_AGGREGATES.value
    client_name: str = "codestrata_cli"
    lifecycle: str = AnalyticsLifecycle.PROJECTED.value
    schema_version: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_SCHEMA_VERSION
    policy_version: str = COMMUNITY_REPOSITORY_AGGREGATE_ANALYTICS_POLICY_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    privacy_projection_applied: bool = True

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "category": self.category,
            "client_name": self.client_name,
            "event_type": self.event_type,
            "installation_id": self.installation_id,
            "language_mix": [item.to_stable_dict() for item in self.language_mix],
            "lifecycle": self.lifecycle,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "rule_execution": self.rule_execution.to_stable_dict(),
            "rule_execution_by_head": [
                item.to_stable_dict() for item in self.rule_execution_by_head
            ],
            "schema_version": self.schema_version,
        }

    def to_analytics_event(self) -> AnalyticsEvent:
        """Identity-free base AnalyticsEvent(category=repository_aggregates)."""

        return AnalyticsEvent(
            event_type=self.event_type,
            category=AnalyticsCategory.REPOSITORY_AGGREGATES,
            client_name=self.client_name,
            lifecycle=AnalyticsLifecycle(self.lifecycle),
            schema_version=self.analytics_schema_version,
            policy_version=self.analytics_policy_version,
            privacy_projection_applied=self.privacy_projection_applied,
            language_mix=tuple(
                {"language_group": item.language_group, "count": item.count}
                for item in self.language_mix
            ),
            rule_execution_summary=self.rule_execution.to_stable_dict(),
            rule_execution_by_head=tuple(
                item.to_stable_dict() for item in self.rule_execution_by_head
            )
            or None,
        )


def build_repository_aggregate_analytics_event(
    *,
    identity: AnonymousInstallationIdentity,
    aggregate_input: RepositoryAggregateAnalyticsInput,
    privacy_projection_applied: bool = True,
) -> RepositoryAggregateAnalyticsEvent:
    return RepositoryAggregateAnalyticsEvent(
        installation_id=identity.installation_id,
        language_mix=aggregate_input.language_mix,
        rule_execution=aggregate_input.rule_execution,
        rule_execution_by_head=aggregate_input.rule_execution_by_head,
        privacy_projection_applied=privacy_projection_applied,
    )


def collect_repository_aggregate_analytics(
    *,
    aggregate_input: RepositoryAggregateAnalyticsInput,
    home: Path | None = None,
    identity: AnonymousInstallationIdentity | None = None,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsEvent:
    """Locally construct repository aggregate analytics (no transmit / no persist)."""

    from codestrata.telemetry.analytics.repository_aggregate_projection import (
        project_repository_aggregate_analytics_event,
    )
    from codestrata.telemetry.analytics.repository_aggregate_validation import (
        validate_repository_aggregate_analytics_event,
    )

    active = policy or default_repository_aggregate_analytics_policy()
    active.validate()

    if identity is None:
        try:
            identity, _, _ = ensure_anonymous_installation_identity(home=home)
        except Exception as error:  # noqa: BLE001
            raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE) from error
    if not is_uuid_v4(identity.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)

    event = build_repository_aggregate_analytics_event(
        identity=identity,
        aggregate_input=aggregate_input,
        privacy_projection_applied=True,
    )
    projected = project_repository_aggregate_analytics_event(event, policy=active)
    validate_repository_aggregate_analytics_event(event, policy=active)
    _ = projected
    return event


__all__ = [
    "REPOSITORY_AGGREGATE_ANALYTICS_EVENT_TYPE",
    "RepositoryAggregateAnalyticsEvent",
    "build_repository_aggregate_analytics_event",
    "collect_repository_aggregate_analytics",
]
