"""Privacy filter field-name authority tests (Slice 9.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.errors import TelemetryRuntimeError
from codestrata.telemetry.privacy import (
    APPROVED_FIELD_NAMES,
    FORBIDDEN_FIELD_NAMES,
    assert_field_name_allowed,
)


def test_forbidden_field_names_rejected() -> None:
    for name in (
        "repository",
        "project",
        "organization",
        "source_code",
        "finding",
        "evidence",
        "recommendation",
        "path",
        "cwd",
        "argv",
        "exception",
        "traceback",
        "credential",
        "secret",
        "token",
        "password",
        "prompt",
        "response",
        "model_id",
        "cost",
        "email",
        "user",
        "customer",
        "installation_id",
    ):
        assert name in FORBIDDEN_FIELD_NAMES
        with pytest.raises(TelemetryRuntimeError):
            assert_field_name_allowed(name)


def test_approved_fields_allowed() -> None:
    for name in (
        "event_type",
        "client_name",
        "cli_version",
        "ai_used",
        "schema_version",
        "runtime_policy_version",
    ):
        assert name in APPROVED_FIELD_NAMES
        assert_field_name_allowed(name)


def test_unknown_field_rejected() -> None:
    with pytest.raises(TelemetryRuntimeError):
        assert_field_name_allowed("custom_metric")
