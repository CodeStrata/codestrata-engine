"""Repository aggregate analytics projection (Epic 10 Slice 10.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    FORBIDDEN_ANALYTICS_FIELD_NAMES,
    AnalyticsEvent,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.projection import project_analytics_event
from codestrata.telemetry.analytics.repository_aggregate import (
    RepositoryAggregateAnalyticsEvent,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)

APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "analytics_policy_version",
        "analytics_schema_version",
        "category",
        "client_name",
        "event_type",
        "installation_id",
        "language_mix",
        "lifecycle",
        "policy_version",
        "privacy_projection_applied",
        "rule_execution",
        "rule_execution_by_head",
        "schema_version",
    }
)

_FORBIDDEN: frozenset[str] = frozenset(
    {
        "repository_name",
        "repository_url",
        "project_name",
        "organization",
        "customer_id",
        "account_id",
        "branch",
        "commit",
        "remote",
        "file_name",
        "file_path",
        "directory",
        "extension",
        "package",
        "dependency",
        "framework",
        "class",
        "method",
        "symbol",
        "rule_id",
        "rule_name",
        "rule_description",
        "detector",
        "threshold",
        "finding",
        "finding_id",
        "evidence",
        "recommendation",
        "severity",
        "priority",
        "source_code",
        "source_snippet",
        "exception",
        "traceback",
        "credential",
        "secret",
        "authorization",
        "prompt",
        "response",
        "provider",
        "model",
        "token",
        "cost",
        "timestamp",
        "exact_duration",
    }
)


@dataclass(frozen=True, slots=True)
class RepositoryAggregateAnalyticsProjection:
    fields: dict[str, Any]

    def to_stable_dict(self) -> dict[str, Any]:
        return {key: self.fields[key] for key in sorted(self.fields)}

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def project_repository_aggregate_analytics_event(
    event: RepositoryAggregateAnalyticsEvent,
    *,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsProjection:
    active = policy or default_repository_aggregate_analytics_policy()
    active.validate()
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)

    payload = event.to_stable_dict()
    for key in payload:
        if key in FORBIDDEN_ANALYTICS_FIELD_NAMES and key != "installation_id":
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
        if key in _FORBIDDEN:
            raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REJECTED)
        if key not in APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)

    if not is_uuid_v4(str(payload["installation_id"])):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    if payload["category"] != "repository_aggregates":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)

    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)

    return RepositoryAggregateAnalyticsProjection(
        fields={key: payload[key] for key in sorted(payload)}
    )


def project_repository_aggregate_to_analytics_event(
    event: RepositoryAggregateAnalyticsEvent,
) -> AnalyticsEvent:
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)
    return analytics_event


__all__ = [
    "APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES",
    "RepositoryAggregateAnalyticsProjection",
    "project_repository_aggregate_analytics_event",
    "project_repository_aggregate_to_analytics_event",
]
