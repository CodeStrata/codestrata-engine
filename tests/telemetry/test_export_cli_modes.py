"""E13.3 headless telemetry export CLI: full/restricted/no-export."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.telemetry.service import reset_telemetry_singletons


def test_cli_export_no_export_is_local_only(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "export", "--mode", "no-export"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "none"
    assert payload["transmission_performed"] is False
    assert payload["local_utility_retained"] is True
    assert payload["allowed_categories"] == []
    assert payload["withheld_categories"] == ["evidence", "graph"]
    original = payload["original"]
    projection = payload["projection"]
    assert projection["transmission_performed"] is False
    assert projection["body"]["original_digest"] == original["package_digest"]
    assert projection["body"]["original_digest"] == digest_canonical(original["body"])
    assert projection["package_digest"] == digest_canonical(projection["body"])
    profile = projection["signature"]["verification_profile"]
    assert profile.startswith("codestrata.export-projection")
    assert "findings" not in projection["body"]
    assert list(home.iterdir()) == []
    assert result.stderr == ""


def test_cli_export_restricted_and_full() -> None:
    restricted = CliRunner().invoke(
        app,
        ["telemetry", "export", "--mode", "restricted", "--withhold", "graph"],
    )
    assert restricted.exit_code == 0
    payload = json.loads(restricted.stdout)
    assert payload["mode"] == "restricted"
    assert payload["withheld_categories"] == ["graph"]
    assert payload["allowed_categories"] == ["evidence"]
    assert payload["projection"]["body"]["export_policy_version"] == "1.0"

    full = CliRunner().invoke(app, ["telemetry", "export", "--mode", "full"])
    assert full.exit_code == 0
    full_payload = json.loads(full.stdout)
    assert full_payload["withheld_categories"] == []
    assert full_payload["allowed_categories"] == ["evidence", "graph"]
    assert full_payload["transmission_performed"] is False


def test_cli_export_rejects_invalid_mode_and_restricted_without_withhold() -> None:
    bad = CliRunner().invoke(app, ["telemetry", "export", "--mode", "lake"])
    assert bad.exit_code == 2
    assert "unsupported mode" in (bad.stderr or bad.stdout).lower()

    empty = CliRunner().invoke(app, ["telemetry", "export", "--mode", "restricted"])
    assert empty.exit_code == 2
    assert "Invalid export" in (empty.stderr or empty.stdout)

    purpose = CliRunner().invoke(
        app,
        ["telemetry", "export", "--mode", "full", "--purpose", "candidate_validation"],
    )
    assert purpose.exit_code == 2
