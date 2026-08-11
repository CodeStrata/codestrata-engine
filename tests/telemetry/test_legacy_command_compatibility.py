"""Legacy telemetry CLI command names remain; enable does not transmit."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.service import reset_telemetry_singletons


def test_Y_cli_command_names_unchanged() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    for name in ("status", "enable", "disable", "reset", "show"):
        assert name in result.stdout
    assert "--telemetry-allow" not in result.stdout
    assert "--telemetry-deny" not in result.stdout


def test_legacy_enable_cli_does_not_call_send_payload(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.delenv("CODESTRATA_TELEMETRY", raising=False)
    reset_telemetry_singletons()
    runner = CliRunner()
    with patch("codestrata.telemetry.service.send_payload") as send:
        result = runner.invoke(app, ["telemetry", "enable"])
        assert result.exit_code == 0
        assert "Anonymous telemetry preference: Enabled." in result.stdout
        assert "No source code" in result.stdout
        send.assert_not_called()
