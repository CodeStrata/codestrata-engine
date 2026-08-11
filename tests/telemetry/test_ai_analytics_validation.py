"""AI analytics validation tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.ai_analytics_models import (
    AIAnalyticsEvent,
    build_ai_analytics_event,
)
from codestrata.telemetry.analytics.ai_analytics_validation import (
    validate_ai_analytics_event,
    validate_ai_analytics_mapping,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def _ok_event(**overrides: object) -> AIAnalyticsEvent:
    base = {
        "capability": "modernization_advisor",
        "provider_family": "openai",
        "model_family": "gpt_family",
        "provider_ownership": "customer_managed",
        "outcome": "success",
    }
    base.update(overrides)
    return build_ai_analytics_event(
        identity=new_anonymous_installation_identity(),
        aggregate=build_ai_analytics_input(**base),  # type: ignore[arg-type]
    )


def test_validate_success() -> None:
    projected = validate_ai_analytics_event(_ok_event())
    assert projected.fields["outcome"] == "success"


def test_validate_unavailable_with_failure() -> None:
    event = _ok_event(
        outcome="unavailable",
        failure_category="provider_unavailable",
        provider_family="unavailable",
        model_family="unavailable",
        provider_ownership="unavailable",
        ai_used=False,
    )
    projected = validate_ai_analytics_event(event)
    assert projected.fields["outcome"] == "unavailable"


def test_unknown_capability_rejected() -> None:
    event = _ok_event()
    object.__setattr__(event, "capability", "report_narrative")
    with pytest.raises(AnalyticsError) as exc:
        validate_ai_analytics_event(event)
    assert exc.value.code == AnalyticsErrorCode.INVALID_CAPABILITY


def test_mapping_missing_required() -> None:
    with pytest.raises(AnalyticsError) as exc:
        validate_ai_analytics_mapping({"outcome": "success"})
    assert exc.value.code == AnalyticsErrorCode.VALIDATION_FAILED
