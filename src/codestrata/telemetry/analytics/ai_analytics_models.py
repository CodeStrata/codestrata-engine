"""AI analytics event model (Epic 10 Slice 10.6).

Local identity-bearing envelope. Base AnalyticsEvent remains identity-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.ai_analytics_input import (
    AIAnalyticsInput,
    build_ai_analytics_input,
)
from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_VERSION,
    COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION,
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    is_uuid_v4,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)

AI_ANALYTICS_EVENT_TYPE = "analytics_ai_usage_collected"


@dataclass(frozen=True, slots=True)
class AIAnalyticsEvent:
    """Local AI analytics record (category=ai_usage).

    ``installation_id`` is the only identifier and is omitted from the base
    AnalyticsEvent produced by ``to_analytics_event``.
    """

    installation_id: str
    capability: str
    provider_family: str
    model_family: str
    provider_ownership: str
    outcome: str
    failure_category: str | None = None
    duration_bucket: str | None = None
    ai_used: bool | None = None
    event_type: str = AI_ANALYTICS_EVENT_TYPE
    category: str = AnalyticsCategory.AI_USAGE.value
    client_name: str = "codestrata_cli"
    lifecycle: str = AnalyticsLifecycle.PROJECTED.value
    schema_version: str = COMMUNITY_AI_ANALYTICS_SCHEMA_VERSION
    policy_version: str = COMMUNITY_AI_ANALYTICS_POLICY_VERSION
    analytics_schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    analytics_policy_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_VERSION
    privacy_projection_applied: bool = True
    operation_category: str = "other"
    limitations: tuple[str, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "analytics_policy_version": self.analytics_policy_version,
            "analytics_schema_version": self.analytics_schema_version,
            "capability": self.capability,
            "category": self.category,
            "client_name": self.client_name,
            "event_type": self.event_type,
            "installation_id": self.installation_id,
            "lifecycle": self.lifecycle,
            "model_family": self.model_family,
            "operation_category": self.operation_category,
            "outcome": self.outcome,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "provider_family": self.provider_family,
            "provider_ownership": self.provider_ownership,
            "schema_version": self.schema_version,
        }
        if self.ai_used is not None:
            payload["ai_used"] = self.ai_used
        if self.duration_bucket is not None:
            payload["duration_bucket"] = self.duration_bucket
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        if self.limitations:
            payload["limitations"] = list(self.limitations)
        return {key: payload[key] for key in sorted(payload)}

    def to_analytics_event(self) -> AnalyticsEvent:
        """Produce Slice 10.1 AnalyticsEvent (no installation_id)."""

        return AnalyticsEvent(
            event_type=self.event_type,
            category=AnalyticsCategory.AI_USAGE,
            client_name=self.client_name,
            lifecycle=AnalyticsLifecycle(self.lifecycle),
            schema_version=self.analytics_schema_version,
            policy_version=self.analytics_policy_version,
            privacy_projection_applied=self.privacy_projection_applied,
            ai_used=self.ai_used,
            operation_category=self.operation_category,
            result=self.outcome,
            duration_bucket=self.duration_bucket,
            failure_category=self.failure_category,
            capability=self.capability,
            provider_family=self.provider_family,
            model_family=self.model_family,
            provider_ownership=self.provider_ownership,
        )


def build_ai_analytics_event(
    *,
    identity: AnonymousInstallationIdentity,
    aggregate: AIAnalyticsInput,
    privacy_projection_applied: bool = True,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsEvent:
    active = policy or default_ai_analytics_policy()
    active.validate()
    if not is_uuid_v4(identity.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    # Re-validate aggregate against policy (typed input only).
    validated = build_ai_analytics_input(
        capability=aggregate.capability,
        provider_family=aggregate.provider_family,
        model_family=aggregate.model_family,
        provider_ownership=aggregate.provider_ownership,
        outcome=aggregate.outcome,
        failure_category=aggregate.failure_category,
        duration_bucket=aggregate.duration_bucket,
        ai_used=aggregate.ai_used,
        policy=active,
    )
    return AIAnalyticsEvent(
        installation_id=identity.installation_id,
        capability=validated.capability,
        provider_family=validated.provider_family,
        model_family=validated.model_family,
        provider_ownership=validated.provider_ownership,
        outcome=validated.outcome,
        failure_category=validated.failure_category,
        duration_bucket=validated.duration_bucket,
        ai_used=validated.ai_used,
        privacy_projection_applied=privacy_projection_applied,
        limitations=tuple(sorted(active.limitations)),
    )


__all__ = [
    "AI_ANALYTICS_EVENT_TYPE",
    "AIAnalyticsEvent",
    "build_ai_analytics_event",
]
