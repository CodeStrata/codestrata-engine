"""Anonymous analytics contract tests (Epic 10 Slice 10.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.compatibility import (
    AnalyticsCompatibilityError,
    assert_schema_compatible,
    compatible_schema_versions,
)
from codestrata.telemetry.analytics.diagnostics import empty_analytics_diagnostics
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    APPROVED_ANALYTICS_CATEGORIES,
    AnalyticsCategory,
    AnalyticsEvent,
    AnalyticsLifecycle,
    illustrative_analytics_event,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN,
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN,
    AnalyticsPolicyError,
    CommunityAnonymousAnalyticsPolicy,
    default_analytics_policy,
)
from codestrata.telemetry.analytics.projection import (
    project_analytics_event,
    project_analytics_from_mapping,
)
from codestrata.telemetry.analytics.serialization import (
    analytics_event_to_stable_json,
    analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.validation import (
    assert_collection_blocked,
    assert_persistence_blocked,
    assert_transmission_blocked,
    validate_analytics_event,
    validate_analytics_mapping,
)
from codestrata.telemetry.runtime_policy import COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN


def test_default_policy_contract_only() -> None:
    policy = default_analytics_policy()
    assert policy.collection_enabled is False
    assert policy.persistence_enabled is False
    assert policy.transmission_enabled is False
    assert policy.installation_id_allowed is False
    assert policy.requires_prior_privacy_projection is True
    assert policy.policy_token == COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN
    assert policy.schema_token == COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_URN
    assert policy.independent_from_telemetry_runtime_policy is True
    assert policy.independent_from_telemetry_event_schema is True


def test_policy_independent_from_telemetry_runtime() -> None:
    assert COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN != COMMUNITY_TELEMETRY_RUNTIME_POLICY_URN
    assert "anonymous-analytics" in COMMUNITY_ANONYMOUS_ANALYTICS_POLICY_URN


@pytest.mark.parametrize(
    "kwargs",
    [
        {"collection_enabled": True},
        {"persistence_enabled": True},
        {"transmission_enabled": True},
        {"installation_id_allowed": True},
        {"requires_prior_privacy_projection": False},
        {"fail_silent": False},
        {"independent_from_telemetry_runtime_policy": False},
    ],
)
def test_policy_rejects_invalid_invariants(kwargs: dict) -> None:
    with pytest.raises(AnalyticsPolicyError):
        CommunityAnonymousAnalyticsPolicy(**kwargs)


def test_policy_stable_dict_deterministic() -> None:
    a = default_analytics_policy().to_stable_dict()
    b = default_analytics_policy().to_stable_dict()
    assert a == b
    assert list(a.keys()) == sorted(a.keys())
    assert analytics_policy_to_stable_json(default_analytics_policy()) == (
        analytics_policy_to_stable_json(default_analytics_policy())
    )


def test_categories_cover_required_domains() -> None:
    expected = {
        "runtime",
        "assessment",
        "repository_aggregates",
        "ai_usage",
        "vscode_usage",
    }
    assert APPROVED_ANALYTICS_CATEGORIES == expected
    assert {item.value for item in AnalyticsCategory} == expected


def test_illustrative_events_for_each_category() -> None:
    for category in AnalyticsCategory:
        event = illustrative_analytics_event(category)
        assert event.category is category
        assert event.privacy_projection_applied is True
        projected = validate_analytics_event(event)
        assert projected.fields["category"] == category.value
        assert projected.fields["privacy_projection_applied"] is True


def test_projection_rejects_forbidden_fields() -> None:
    base = illustrative_analytics_event().to_intake_dict()
    for field in (
        "installation_id",
        "repository_name",
        "workspace_uri",
        "findings",
        "prompt",
        "credential",
        "model_id",
        "cost",
        "argv",
    ):
        payload = dict(base)
        payload[field] = "x"
        with pytest.raises(AnalyticsError) as exc:
            project_analytics_from_mapping(payload)
        assert exc.value.code in {
            AnalyticsErrorCode.UNSAFE_FIELD,
            AnalyticsErrorCode.UNKNOWN_FIELD,
        }
        assert "x" not in str(exc.value)


def test_projection_requires_privacy_flag() -> None:
    event = AnalyticsEvent(
        event_type="analytics_runtime_defined",
        category=AnalyticsCategory.RUNTIME,
        privacy_projection_applied=False,
    )
    with pytest.raises(AnalyticsError) as exc:
        project_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.PRIVACY_REQUIRED


def test_projection_rejects_unknown_category() -> None:
    payload = illustrative_analytics_event().to_intake_dict()
    payload["category"] = "marketing"
    with pytest.raises(AnalyticsError) as exc:
        project_analytics_from_mapping(payload)
    assert exc.value.code in {
        AnalyticsErrorCode.UNSAFE_VALUE,
        AnalyticsErrorCode.UNKNOWN_CATEGORY,
    }


def test_validation_and_blocked_boundaries() -> None:
    event = illustrative_analytics_event(AnalyticsCategory.ASSESSMENT)
    projected = validate_analytics_event(event)
    assert projected.to_stable_json() == projected.to_stable_json()
    assert_collection_blocked()
    assert_persistence_blocked()
    assert_transmission_blocked()


def test_validation_mapping_path() -> None:
    payload = illustrative_analytics_event(AnalyticsCategory.AI_USAGE).to_intake_dict()
    projected = validate_analytics_mapping(payload)
    assert projected.fields["category"] == "ai_usage"


def test_schema_compatibility() -> None:
    assert "1.0" in compatible_schema_versions()
    assert_schema_compatible("1.0")
    with pytest.raises(AnalyticsCompatibilityError):
        assert_schema_compatible("2.0")


def test_diagnostics_no_payload_leakage() -> None:
    diag = empty_analytics_diagnostics(
        limitation_codes=default_analytics_policy().limitations
    )
    blob = diag.to_stable_json()
    assert diag.collection_enabled is False
    assert diag.installation_id_allowed is False
    assert "payload" not in diag.to_stable_dict()
    assert "/Users/" not in blob
    assert list(diag.to_stable_dict().keys()) == sorted(diag.to_stable_dict().keys())


def test_event_serialization_deterministic() -> None:
    event = illustrative_analytics_event(AnalyticsCategory.VSCODE_USAGE)
    assert analytics_event_to_stable_json(event) == analytics_event_to_stable_json(event)
    assert event.lifecycle is AnalyticsLifecycle.DEFINED


def test_error_taxonomy_codes_are_bounded() -> None:
    codes = {item.value for item in AnalyticsErrorCode}
    assert "validation_failed" in codes
    assert "privacy_required" in codes
    assert "incompatible_schema" in codes
    # No free-form exception text on the error type.
    err = AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
    assert str(err) == "unknown_field"


def test_no_platform_or_cloud_imports() -> None:
    import codestrata.telemetry.analytics as pkg
    import pathlib

    root = pathlib.Path(pkg.__file__).resolve().parent
    forbidden = ("codestrata_platform", "boto3", "botocore", "fastapi", "community_data_lake")
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith(("import ", "from ")):
                for token in forbidden:
                    assert token not in stripped, f"{path.name}: {stripped}"


def test_does_not_modify_telemetry_runtime_policy() -> None:
    from codestrata.telemetry.runtime_policy import default_runtime_policy

    policy = default_runtime_policy()
    assert policy.disabled_by_default is True
    assert policy.installation_id_allowed is False
    assert policy.transport_unavailable_by_default is True
