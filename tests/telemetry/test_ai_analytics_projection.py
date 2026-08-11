"""AI analytics projection tests (Slice 10.6)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.ai_analytics_input import build_ai_analytics_input
from codestrata.telemetry.analytics.ai_analytics_models import build_ai_analytics_event
from codestrata.telemetry.analytics.ai_analytics_projection import (
    project_ai_analytics_event,
    project_ai_analytics_to_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.installation_identity import (
    new_anonymous_installation_identity,
)


def _event(**overrides: object):
    base = {
        "capability": "modernization_advisor",
        "provider_family": "aws_bedrock",
        "model_family": "amazon_nova_family",
        "provider_ownership": "customer_managed",
        "outcome": "success",
        "duration_bucket": "s_1_10",
        "ai_used": True,
    }
    base.update(overrides)
    aggregate = build_ai_analytics_input(**base)  # type: ignore[arg-type]
    return build_ai_analytics_event(
        identity=new_anonymous_installation_identity(),
        aggregate=aggregate,
    )


def test_projection_sorted_and_identity_local() -> None:
    event = _event()
    projected = project_ai_analytics_event(event)
    assert projected.installation_id == event.installation_id
    assert list(projected.to_stable_dict()) == sorted(projected.to_stable_dict())
    base = project_ai_analytics_to_analytics_event(event)
    assert "installation_id" not in base.to_intake_dict()


def test_privacy_required() -> None:
    event = _event()
    object.__setattr__(event, "privacy_projection_applied", False)
    with pytest.raises(AnalyticsError) as exc:
        project_ai_analytics_event(event)
    assert exc.value.code == AnalyticsErrorCode.PRIVACY_REQUIRED
