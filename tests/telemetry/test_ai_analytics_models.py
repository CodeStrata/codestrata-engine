"""AI analytics model and input tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.ai_analytics_models import build_ai_analytics_event
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import AnalyticsCategory
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def _input(**overrides: object):
    base = {
        "capability": "modernization_advisor",
        "provider_family": "openai",
        "model_family": "gpt_family",
        "provider_ownership": "customer_managed",
        "outcome": "success",
        "ai_used": True,
    }
    base.update(overrides)
    return build_ai_analytics_input(**base)  # type: ignore[arg-type]


def test_build_event_and_base_analytics() -> None:
    identity = new_anonymous_installation_identity()
    event = build_ai_analytics_event(identity=identity, aggregate=_input())
    assert event.category == "ai_usage"
    assert event.installation_id == identity.installation_id
    base = event.to_analytics_event()
    assert base.category == AnalyticsCategory.AI_USAGE
    assert "installation_id" not in base.to_intake_dict()
    assert base.capability == "modernization_advisor"
    assert base.provider_family == "openai"
    assert base.model_family == "gpt_family"
    assert base.result == "success"


def test_skipped_rejects_failure_category() -> None:
    with pytest.raises(AnalyticsError) as exc:
        _input(outcome="skipped", failure_category="timeout")
    assert exc.value.code == AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH


def test_success_rejects_failure_category() -> None:
    with pytest.raises(AnalyticsError) as exc:
        _input(outcome="success", failure_category="timeout")
    assert exc.value.code == AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH


def test_failure_requires_failure_category() -> None:
    with pytest.raises(AnalyticsError) as exc:
        _input(outcome="failure")
    assert exc.value.code == AnalyticsErrorCode.OUTCOME_FAILURE_MISMATCH


def test_capability_alias_canonicalized() -> None:
    agg = _input(capability="ai_enrichment")
    assert agg.capability == "modernization_advisor"
