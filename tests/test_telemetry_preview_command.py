"""CLI integration for ``codestrata telemetry preview`` (Slice 9.9)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.service import reset_telemetry_singletons


def test_preview_exit_zero_and_wrapper() -> None:
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "preview"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_name"] == "privacy-first-telemetry-preview"
    assert payload["schema_version"] == "1.0.0"
    assert payload["preview_type"] == "illustrative"
    assert payload["event_name"] == "feature_invoked"
    assert payload["transmission_performed"] is False
    assert "omitted_optional_fields" in payload


def test_preview_all_events() -> None:
    for name in (
        "application_started",
        "application_completed",
        "feature_invoked",
        "feature_completed",
        "operation_failed",
    ):
        result = CliRunner().invoke(app, ["telemetry", "preview", "--event", name])
        assert result.exit_code == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["event_name"] == name


def test_preview_rejects_unknown_event() -> None:
    result = CliRunner().invoke(app, ["telemetry", "preview", "--event", "ai_used"])
    assert result.exit_code == 2
