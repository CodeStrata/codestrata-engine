"""AI analytics projection (Epic 10 Slice 10.6)."""

from __future__ import annotations

import json
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
from codestrata.telemetry.analytics.ai_analytics_models import AIAnalyticsEvent
from codestrata.telemetry.analytics.ai_analytics_policy import (
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    FORBIDDEN_ANALYTICS_FIELD_NAMES,
    AnalyticsEvent,
    _APPROVED_DURATION_BUCKETS,
)
from codestrata.telemetry.analytics.installation_identity import is_uuid_v4
from codestrata.telemetry.analytics.projection import project_analytics_event

APPROVED_AI_ANALYTICS_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "ai_used",
        "analytics_policy_version",
        "analytics_schema_version",
        "capability",
        "category",
        "client_name",
        "duration_bucket",
        "event_type",
        "failure_category",
        "installation_id",
        "lifecycle",
        "limitations",
        "model_family",
        "operation_category",
        "outcome",
        "policy_version",
        "privacy_projection_applied",
        "provider_family",
        "provider_ownership",
        "schema_version",
    }
)

_FORBIDDEN_AI_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "prompt",
        "system_prompt",
        "user_prompt",
        "response",
        "completion",
        "message",
        "source",
        "source_code",
        "source_snippet",
        "context",
        "retrieval_query",
        "retrieved_document",
        "document",
        "file",
        "path",
        "repository",
        "project",
        "organization",
        "customer",
        "account",
        "tenant",
        "endpoint",
        "url",
        "region",
        "arn",
        "api_key",
        "credential",
        "secret",
        "authorization",
        "provider",
        "model_id",
        "model",
        "deployment",
        "deployment_name",
        "token_count",
        "exact_token_count",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "duration_ms",
        "cost",
        "exception",
        "traceback",
        "http_status",
        "finding",
        "evidence",
        "recommendation",
        "token_usage_bucket",
        "tool_usage",
        "rag_usage",
        "graph_usage",
    }
)


@dataclass(frozen=True, slots=True)
class AIAnalyticsProjection:
    """Allowlisted AI analytics payload (local only)."""

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
        if key in _FORBIDDEN_AI_IDENTIFIERS:
            raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REJECTED)
        if key not in APPROVED_AI_ANALYTICS_FIELD_NAMES:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
    if payload.get("privacy_projection_applied") is not True:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)


def project_ai_analytics_event(
    event: AIAnalyticsEvent,
    *,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsProjection:
    active = policy or default_ai_analytics_policy()
    active.validate()
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if not is_uuid_v4(event.installation_id):
        raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)

    payload = event.to_stable_dict()
    _assert_privacy_envelope(payload)

    if payload["capability"] not in APPROVED_AI_CAPABILITIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_CAPABILITY)
    if payload["provider_family"] not in APPROVED_AI_PROVIDER_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_FAMILY)
    if payload["model_family"] not in APPROVED_AI_MODEL_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)
    if payload["provider_ownership"] not in APPROVED_AI_PROVIDER_OWNERSHIPS:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_OWNERSHIP)
    if payload["outcome"] not in APPROVED_AI_OUTCOMES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_OUTCOME)
    if "duration_bucket" in payload and payload["duration_bucket"] not in (
        _APPROVED_DURATION_BUCKETS
    ):
        raise AnalyticsError(AnalyticsErrorCode.INVALID_DURATION_BUCKET)
    if "failure_category" in payload:
        if payload["failure_category"] not in APPROVED_AI_FAILURE_CATEGORIES:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_FAILURE_CATEGORY)

    return AIAnalyticsProjection(
        fields={key: payload[key] for key in sorted(payload)}
    )


def project_ai_analytics_to_analytics_event(
    event: AIAnalyticsEvent,
    *,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AnalyticsEvent:
    """Project local envelope → identity-free base AnalyticsEvent."""

    project_ai_analytics_event(event, policy=policy)
    base = event.to_analytics_event()
    project_analytics_event(base)
    return base


def project_ai_analytics_from_mapping(
    payload: dict[str, Any],
) -> AIAnalyticsProjection:
    """Reject untrusted mappings — used by privacy verification negative tests."""

    _assert_privacy_envelope(payload)
    projected: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in APPROVED_AI_ANALYTICS_FIELD_NAMES:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
        projected[key] = value
    return AIAnalyticsProjection(
        fields={key: projected[key] for key in sorted(projected)}
    )


__all__ = [
    "APPROVED_AI_ANALYTICS_FIELD_NAMES",
    "AIAnalyticsProjection",
    "project_ai_analytics_event",
    "project_ai_analytics_from_mapping",
    "project_ai_analytics_to_analytics_event",
]
