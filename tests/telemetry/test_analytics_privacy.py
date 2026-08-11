"""Anonymous analytics privacy and determinism tests (Epic 10 Slice 10.1)."""

from __future__ import annotations

import json

import pytest

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    AnalyticsCategory,
    illustrative_analytics_event,
)
from codestrata.telemetry.analytics.policy import default_analytics_policy
from codestrata.telemetry.analytics.projection import project_analytics_from_mapping
from codestrata.telemetry.analytics.serialization import (
    analytics_policy_to_stable_json,
    analytics_projection_to_stable_json,
)
from codestrata.telemetry.analytics.validation import validate_analytics_event


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository_url", "https://example.invalid/acme"),
        ("path", "/tmp/file.py"),
        ("source_code", "def x():\n  return 1"),
        ("findings", [{"id": "f1"}]),
        ("evidence", [{"id": "e1"}]),
        ("recommendations", [{"id": "r1"}]),
        ("prompt", "system"),
        ("response", "model"),
        ("api_key", "key"),
        ("authorization", "Bearer x"),
        ("provider", "vendor"),
        ("exact_token_count", 12),
        ("installation_id", "install-1"),
        ("endpoint", "https://example.invalid/v1"),
        ("username", "alice"),
        ("email", "alice@example.invalid"),
    ],
)
def test_privacy_rejects_forbidden_analytics_fields(field: str, value: object) -> None:
    payload = illustrative_analytics_event().to_intake_dict()
    payload[field] = value
    with pytest.raises(AnalyticsError) as exc:
        project_analytics_from_mapping(payload)
    assert exc.value.code in {
        AnalyticsErrorCode.UNSAFE_FIELD,
        AnalyticsErrorCode.UNKNOWN_FIELD,
    }
    # Never echo rejected values.
    assert str(value) not in str(exc.value)


def test_unsafe_string_value_rejected() -> None:
    payload = illustrative_analytics_event().to_intake_dict()
    payload["event_type"] = "/Users/someone/secret"
    with pytest.raises(AnalyticsError) as exc:
        project_analytics_from_mapping(payload)
    assert exc.value.code is AnalyticsErrorCode.UNSAFE_VALUE
    assert "/Users/someone/secret" not in str(exc.value)


def test_determinism_across_categories() -> None:
    policy_json = analytics_policy_to_stable_json(default_analytics_policy())
    assert policy_json == analytics_policy_to_stable_json(default_analytics_policy())
    for category in AnalyticsCategory:
        event = illustrative_analytics_event(category)
        a = validate_analytics_event(event)
        b = validate_analytics_event(event)
        assert a.to_stable_dict() == b.to_stable_dict()
        assert analytics_projection_to_stable_json(a) == analytics_projection_to_stable_json(b)
        parsed = json.loads(a.to_stable_json())
        assert list(parsed.keys()) == sorted(parsed.keys())


def test_policy_reconciles_with_schema_tokens() -> None:
    policy = default_analytics_policy()
    assert policy.schema_version == "1.0"
    assert policy.policy_version == "1.0"
    assert policy.schema_token.endswith(":1.0")
    assert "installation_identity_not_in_base_analytics_events" in policy.limitations
    assert "runtime_analytics_local_envelope_may_include_installation_id" in policy.limitations
    assert "contract_only" in policy.limitations
