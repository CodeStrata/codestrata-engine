"""AI analytics privacy negative matrix (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.ai_analytics_models import build_ai_analytics_event
from codestrata.telemetry.analytics.ai_analytics_projection import (
    APPROVED_AI_ANALYTICS_FIELD_NAMES,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import FORBIDDEN_ANALYTICS_FIELD_NAMES
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.policy import default_analytics_policy
from codestrata.telemetry.analytics.projection import project_analytics_event


def _sample():
    return build_ai_analytics_event(
        identity=new_anonymous_installation_identity(),
        aggregate=build_ai_analytics_input(
            capability="modernization_advisor",
            provider_family="openai",
            model_family="gpt_family",
            provider_ownership="customer_managed",
            outcome="success",
        ),
    )


_FORBIDDEN = (
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
    "deployment_name",
    "token_count",
    "exact_token_count",
    "latency_ms",
    "duration_ms",
    "cost",
    "exception",
    "traceback",
    "finding",
    "evidence",
    "recommendation",
    "token_usage_bucket",
    "tool_usage",
    "rag_usage",
    "graph_usage",
)


@pytest.mark.parametrize("field", _FORBIDDEN)
def test_forbidden_fields_not_approved(field: str) -> None:
    assert field not in APPROVED_AI_ANALYTICS_FIELD_NAMES


def test_installation_id_only_identifier() -> None:
    payload = _sample().to_stable_dict()
    ids = {
        k
        for k in payload
        if k.endswith("_id") or k in {"username", "email", "hostname"}
    }
    assert ids == {"installation_id"}


def test_base_event_forbids_installation_id() -> None:
    assert "installation_id" in FORBIDDEN_ANALYTICS_FIELD_NAMES
    assert default_analytics_policy().installation_id_allowed is False
    assert "installation_id" not in _sample().to_analytics_event().to_intake_dict()


def test_raw_provider_and_model_remain_forbidden_on_base() -> None:
    assert "provider" in FORBIDDEN_ANALYTICS_FIELD_NAMES
    assert "model_id" in FORBIDDEN_ANALYTICS_FIELD_NAMES


def test_path_shaped_value_rejected_on_base_projection() -> None:
    base = _sample().to_analytics_event()
    object.__setattr__(base, "event_type", "/Users/secret/path")
    with pytest.raises(AnalyticsError) as exc:
        project_analytics_event(base)
    assert exc.value.code == AnalyticsErrorCode.UNSAFE_VALUE
    assert "/Users/secret/path" not in str(exc.value)
