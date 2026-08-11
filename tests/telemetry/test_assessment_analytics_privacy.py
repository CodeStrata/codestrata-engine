"""Assessment analytics privacy and negative matrix (Slice 10.4)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.assessment_analytics import AssessmentAnalyticsEvent
from codestrata.telemetry.analytics.assessment_analytics_projection import (
    APPROVED_ASSESSMENT_ANALYTICS_FIELD_NAMES,
    project_assessment_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import FORBIDDEN_ANALYTICS_FIELD_NAMES
from codestrata.telemetry.analytics.policy import default_analytics_policy


def _sample(**overrides: object) -> AssessmentAnalyticsEvent:
    base = {
        "installation_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "command_category": "assess",
        "duration_bucket": "s_1_10",
        "outcome": "success",
        "enabled_assessment_heads": ("security_intelligence",),
        "privacy_projection_applied": True,
    }
    base.update(overrides)
    return AssessmentAnalyticsEvent(**base)  # type: ignore[arg-type]


_FORBIDDEN = (
    "repository_name",
    "repository_url",
    "project_name",
    "organization",
    "customer_id",
    "account_id",
    "username",
    "email",
    "hostname",
    "ip_address",
    "cwd",
    "path",
    "file_name",
    "report_path",
    "config_path",
    "output_path",
    "argv",
    "command_line",
    "source_code",
    "finding",
    "evidence",
    "recommendation",
    "exception_message",
    "traceback",
    "environment",
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
)


@pytest.mark.parametrize("field", _FORBIDDEN)
def test_forbidden_fields_not_approved(field: str) -> None:
    assert field not in APPROVED_ASSESSMENT_ANALYTICS_FIELD_NAMES


def test_installation_id_only_identifier() -> None:
    payload = _sample().to_stable_dict()
    ids = {k for k in payload if k.endswith("_id") or k in {"username", "email", "hostname"}}
    assert ids == {"installation_id"}


def test_base_event_forbids_installation_id() -> None:
    assert "installation_id" in FORBIDDEN_ANALYTICS_FIELD_NAMES
    assert default_analytics_policy().installation_id_allowed is False
    assert "installation_id" not in _sample().to_analytics_event().to_intake_dict()


def test_path_shaped_value_rejected() -> None:
    event = _sample(event_type="/Users/secret/path")
    with pytest.raises(AnalyticsError) as exc:
        project_assessment_analytics_event(event)
    assert exc.value.code in {
        AnalyticsErrorCode.UNSAFE_VALUE,
        AnalyticsErrorCode.PRIVACY_REJECTED,
    }
    assert "/Users/secret/path" not in str(exc.value)
