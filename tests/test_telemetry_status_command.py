"""CLI integration for ``codestrata telemetry status`` (Slice 9.7)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.service import reset_telemetry_singletons


def test_telemetry_status_exit_zero_and_sections() -> None:
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Anonymous Community telemetry" in result.stdout
    assert "Default: Disabled" in result.stdout
    assert "Preference:" in result.stdout


def test_status_does_not_use_legacy_service(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    with patch(
        "codestrata.cli.telemetry_cmd.get_legacy_telemetry_service",
        side_effect=AssertionError("legacy must not run for status"),
    ):
        result = CliRunner().invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert list(home.iterdir()) == []


def test_status_help_mentions_side_effects() -> None:
    result = CliRunner().invoke(app, ["telemetry", "status", "--help"])
    assert result.exit_code == 0
    text = (result.stdout + result.stderr).lower()
    assert "preference" in text or "enabled" in text or "disabled" in text or "anonymous" in text
