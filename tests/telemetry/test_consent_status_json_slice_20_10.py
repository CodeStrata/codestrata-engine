"""Slice 20.10 — Engine telemetry status --json and decline-upgrade for VS Code."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.persisted_consent import (
    consent_status_payload,
    persist_disabled,
    persist_v1_yes,
    persist_v2_yes,
)
from codestrata.telemetry.service import reset_telemetry_singletons


def test_status_json_stable_contract(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runner = CliRunner()

    undecided = runner.invoke(app, ["telemetry", "status", "--json"])
    assert undecided.exit_code == 0
    payload = json.loads(undecided.stdout)
    assert payload["state"] == "undecided"
    assert payload["lifecycle_allowed"] is False
    assert payload["assessment_metadata_allowed"] is False
    assert "installation_id" not in payload
    assert set(payload.keys()) == {
        "assessment_metadata_allowed",
        "lifecycle_allowed",
        "schema_version",
        "should_prompt_v2_upgrade",
        "state",
        "v2_upgrade_declined",
    }

    persist_v1_yes(path=home / "telemetry.json")
    v1 = json.loads(runner.invoke(app, ["telemetry", "status", "--json"]).stdout)
    assert v1["state"] == "v1_yes"
    assert v1["lifecycle_allowed"] is True
    assert v1["assessment_metadata_allowed"] is False
    assert v1["should_prompt_v2_upgrade"] is True

    persist_v2_yes(path=home / "telemetry.json")
    v2 = json.loads(runner.invoke(app, ["telemetry", "status", "--json"]).stdout)
    assert v2["state"] == "v2_yes"
    assert v2["assessment_metadata_allowed"] is True

    persist_disabled(path=home / "telemetry.json")
    disabled = json.loads(
        runner.invoke(app, ["telemetry", "status", "--json"]).stdout
    )
    assert disabled["state"] == "disabled"


def test_decline_upgrade_keeps_v1(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    persist_v1_yes(path=home / "telemetry.json")
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "decline-upgrade"])
    assert result.exit_code == 0
    payload = consent_status_payload(path=home / "telemetry.json")
    assert payload["state"] == "v1_yes"
    assert payload["should_prompt_v2_upgrade"] is False
    assert payload["lifecycle_allowed"] is True
    assert payload["assessment_metadata_allowed"] is False
