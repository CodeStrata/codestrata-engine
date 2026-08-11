"""Runtime analytics privacy contract tests (Epic 10 Slice 10.3)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import FORBIDDEN_ANALYTICS_FIELD_NAMES
from codestrata.telemetry.analytics.policy import default_analytics_policy
from codestrata.telemetry.analytics.runtime_analytics import (
    RuntimeAnalyticsEvent,
    default_runtime_analytics_policy,
)
from codestrata.telemetry.analytics.runtime_analytics_projection import (
    APPROVED_RUNTIME_ANALYTICS_FIELD_NAMES,
    project_runtime_analytics_event,
)
from codestrata.telemetry.analytics.runtime_analytics_validation import (
    validate_runtime_analytics_event,
)


def _sample(**overrides: object) -> RuntimeAnalyticsEvent:
    base = {
        "installation_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "cli_version": "0.2.0",
        "os_family": "linux",
        "architecture": "x86_64",
        "runtime_version": "3.12",
        "release_adoption": "0.2",
        "privacy_projection_applied": True,
    }
    base.update(overrides)
    return RuntimeAnalyticsEvent(**base)  # type: ignore[arg-type]


_FORBIDDEN_KEYS = (
    "username",
    "email",
    "hostname",
    "repository_name",
    "project_name",
    "path",
    "argv",
    "machine_id",
    "mac_address",
    "customer_id",
    "organization_id",
    "source_code",
    "findings",
    "evidence",
    "credentials",
)


def test_installation_id_is_only_identifier_in_envelope() -> None:
    payload = _sample().to_stable_dict()
    identifier_keys = {
        key
        for key in payload
        if key.endswith("_id") or key in {"username", "email", "hostname"}
    }
    assert identifier_keys == {"installation_id"}


def test_base_analytics_event_still_forbids_installation_id() -> None:
    assert "installation_id" in FORBIDDEN_ANALYTICS_FIELD_NAMES
    assert default_analytics_policy().installation_id_allowed is False
    analytics = _sample().to_analytics_event().to_intake_dict()
    assert "installation_id" not in analytics


@pytest.mark.parametrize("field", _FORBIDDEN_KEYS)
def test_forbidden_fields_not_in_approved_runtime_envelope(field: str) -> None:
    assert field not in APPROVED_RUNTIME_ANALYTICS_FIELD_NAMES


def test_path_shaped_cli_version_rejected() -> None:
    event = _sample(cli_version="/Users/secret/bin")
    with pytest.raises(AnalyticsError) as exc:
        project_runtime_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.UNSAFE_VALUE
    assert "/Users/secret/bin" not in str(exc.value)


def test_invalid_architecture_rejected() -> None:
    event = _sample(architecture="powerpc")
    with pytest.raises(AnalyticsError) as exc:
        validate_runtime_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.UNSAFE_VALUE


def test_runtime_policy_keeps_transmission_off() -> None:
    policy = default_runtime_analytics_policy()
    assert policy.transmission_enabled is False
    assert policy.persistence_enabled is False
    assert "installation_identity_only_identifier" in policy.limitations
    assert "no_transmission" in policy.limitations
