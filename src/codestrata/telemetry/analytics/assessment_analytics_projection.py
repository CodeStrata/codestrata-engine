"""Assessment analytics projection (Epic 10 Slice 10.4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.assessment_analytics import (
    APPROVED_COMMAND_CATEGORIES,
    APPROVED_OUTCOMES,
    AssessmentAnalyticsEvent,
)
from codestrata.telemetry.analytics.assessment_analytics_policy import (
    CommunityAssessmentAnalyticsPolicy,
    default_assessment_analytics_policy,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    FORBIDDEN_ANALYTICS_FIELD_NAMES,
    AnalyticsEvent,
    _APPROVED_DURATION_BUCKETS,
    _APPROVED_FAILURE_CATEGORIES,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.projection import project_analytics_event
from codestrata.telemetry.privacy import looks_like_path_or_secret_value

APPROVED_ASSESSMENT_ANALYTICS_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "ai_requested",
        "ai_used",
        "analytics_policy_version",
        "analytics_schema_version",
        "category",
        "client_name",
        "command_category",
        "duration_bucket",
        "enabled_assessment_heads",
        "event_type",
        "failure_category",
        "installation_id",
        "lifecycle",
        "offline_mode",
        "operation_category",
        "outcome",
        "policy_version",
        "privacy_projection_applied",
        "schema_version",
    }
)

_FORBIDDEN_ASSESSMENT_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "username",
        "email",
        "hostname",
        "host",
        "ip",
        "ip_address",
        "machine_id",
        "mac",
        "mac_address",
        "customer_id",
        "account_id",
        "organization",
        "organization_id",
        "repository",
        "repository_name",
        "repository_url",
        "project",
        "project_name",
        "path",
        "cwd",
        "file_name",
        "report_path",
        "config_path",
        "output_path",
        "argv",
        "command_line",
        "environment",
        "env",
        "source_code",
        "finding",
        "evidence",
        "recommendation",
        "exception_message",
        "traceback",
        "credential",
        "secret",
        "api_key",
        "authorization",
        "prompt",
        "response",
        "provider",
        "model_id",
        "token_count",
        "cost",
        "exact_duration",
        "timestamp",
        "duration_ms",
    }
)


@dataclass(frozen=True, slots=True)
class AssessmentAnalyticsProjection:
    """Allowlisted assessment analytics payload (local only)."""

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

    @property
    def installation_id(self) -> str:
        value = self.fields["installation_id"]
        assert isinstance(value, str)
        return value


def _assert_privacy_envelope(payload: dict[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_ANALYTICS_FIELD_NAMES and key != "installation_id":
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
        if key in _FORBIDDEN_ASSESSMENT_IDENTIFIERS:
            raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REJECTED)
        if key not in APPROVED_ASSESSMENT_ANALYTICS_FIELD_NAMES:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
    if payload.get("privacy_projection_applied") is not True:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)


def project_assessment_analytics_event(
    event: AssessmentAnalyticsEvent,
    *,
    policy: CommunityAssessmentAnalyticsPolicy | None = None,
) -> AssessmentAnalyticsProjection:
    active = policy or default_assessment_analytics_policy()
    active.validate()
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)

    payload = event.to_stable_dict()
    _assert_privacy_envelope(payload)

    if not is_uuid_v4(str(payload["installation_id"])):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)
    if payload["category"] != "assessment":
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if payload["command_category"] not in APPROVED_COMMAND_CATEGORIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_COMMAND_CATEGORY)
    if payload["duration_bucket"] not in _APPROVED_DURATION_BUCKETS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)
    if payload["outcome"] not in APPROVED_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)

    outcome = str(payload["outcome"])
    failure = payload.get("failure_category")
    if outcome == "success":
        if failure is not None and active.failure_category_forbidden_on_success:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
    elif outcome in {"failure", "cancelled"}:
        if failure is None and active.failure_category_required_on_failure:
            raise AnalyticsError(AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH)
        if failure is not None and failure not in _APPROVED_FAILURE_CATEGORIES:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)

    heads = payload.get("enabled_assessment_heads", [])
    if not isinstance(heads, list):
        raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
    if len(heads) > active.max_enabled_heads:
        raise AnalyticsError(AnalyticsErrorCode.TOO_MANY_HEADS)
    if list(heads) != sorted(heads):
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    for key in ("event_type", "command_category", "outcome", "duration_bucket"):
        value = payload[key]
        if isinstance(value, str) and looks_like_path_or_secret_value(value):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)

    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)

    return AssessmentAnalyticsProjection(
        fields={key: payload[key] for key in sorted(payload)}
    )


def project_assessment_analytics_to_analytics_event(
    event: AssessmentAnalyticsEvent,
) -> AnalyticsEvent:
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    analytics_event = event.to_analytics_event()
    project_analytics_event(analytics_event)
    return analytics_event


__all__ = [
    "APPROVED_ASSESSMENT_ANALYTICS_FIELD_NAMES",
    "AssessmentAnalyticsProjection",
    "project_assessment_analytics_event",
    "project_assessment_analytics_to_analytics_event",
]
