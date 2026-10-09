"""E13.1 CLI inspect / enable / disable and pending cancellation."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.consent_scope import CommunityConsentState, resolve_consent_capabilities
from codestrata.telemetry.queue import queue_depth
from codestrata.telemetry.service import reset_telemetry_singletons


def test_inspect_matches_status_and_is_side_effect_free(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runner = CliRunner()
    status = runner.invoke(app, ["telemetry", "status", "--json"])
    inspect = runner.invoke(app, ["telemetry", "inspect", "--json"])
    assert status.exit_code == 0
    assert inspect.exit_code == 0
    assert json.loads(status.stdout) == json.loads(inspect.stdout)
    assert json.loads(inspect.stdout)["state"] == "undecided"
    assert list(home.iterdir()) == []


def test_enable_then_disable_cancels_queue_and_survives_restart(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    queue = home / "telemetry-queue.jsonl"
    queue.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "event": "assessment_started",
                "installation_id": "11111111-1111-4111-8111-111111111111",
                "codestrata_version": "0.0.0",
                "os": "Windows",
                "python_version": "3.12.0",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    enabled = runner.invoke(app, ["telemetry", "enable"])
    assert enabled.exit_code == 0
    pref = home / "telemetry.json"
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    assert queue_depth(path=queue) == 1

    disabled = runner.invoke(app, ["telemetry", "disable"])
    assert disabled.exit_code == 0
    assert "Disabled" in disabled.stdout
    assert "Pending collection cancelled" in disabled.stdout
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.DISABLED
    assert queue_depth(path=queue) == 0

    reset_telemetry_singletons()
    again = runner.invoke(app, ["telemetry", "inspect", "--json"])
    assert again.exit_code == 0
    assert json.loads(again.stdout)["state"] == "disabled"
    assert json.loads(again.stdout)["lifecycle_allowed"] is False
    assert queue_depth(path=queue) == 0
