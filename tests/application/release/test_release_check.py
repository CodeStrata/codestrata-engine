"""Tests for release readiness (Phase 5.14)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.application.release import run_release_check
from codestrata.application.release.checks import (
    check_cli_registration,
    check_default_configuration,
    check_deterministic_provider_health,
    check_prompt_availability,
    check_required_resources,
    check_schema_availability,
)
from codestrata.cli import app
from codestrata.cli.release import release_app
from codestrata.resources import read_default_config_text

runner = CliRunner()


def test_packaged_default_config_and_schemas() -> None:
    text = read_default_config_text()
    assert "[repository]" in text
    assert "deterministic" in text
    assert check_required_resources().ok
    assert check_schema_availability().ok
    assert check_prompt_availability().ok
    assert check_default_configuration().ok
    assert check_deterministic_provider_health().ok


def test_cli_version_and_release_help() -> None:
    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
    assert "CodeStrata" in version.stdout
    from codestrata.cli.release import release_app

    help_result = runner.invoke(release_app, ["--help"])
    assert help_result.exit_code == 0
    assert check_cli_registration().ok


def test_release_check_skip_build_and_smoke(tmp_path: Path) -> None:
    result = run_release_check(
        output_directory=tmp_path,
        require_smoke=False,
        require_build_artifacts=False,
    )
    assert result.ok
    summary = tmp_path / "summary.json"
    assert summary.is_file()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["ok"] is True

    cli = runner.invoke(
        release_app,
        [
            "--output",
            str(tmp_path / "cli"),
            "--skip-smoke",
            "--skip-build",
        ],
    )
    assert cli.exit_code == 0
    assert "PASS" in cli.stdout
