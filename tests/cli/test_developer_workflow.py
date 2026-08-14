"""Tests for Phase 6.4 developer workflow CLI commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.doctor import run_doctor_checks
from codestrata.cli.init_cmd import write_minimal_config
from codestrata.package_metadata import format_version_details, get_package_version
from codestrata.reporting.contract.constants import REPORT_HTML_VERSION

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _visible_help(result) -> str:
    """Normalize CLI help for flag assertions (strip ANSI; collapse whitespace)."""

    raw = f"{result.stdout or ''}{result.stderr or ''}"
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", raw))


def test_init_writes_minimal_config(tmp_path: Path) -> None:
    target = tmp_path / "codestrata.toml"
    written = write_minimal_config(target)
    assert written == target
    text = target.read_text(encoding="utf-8")
    assert 'path = "."' in text
    assert 'profile = "community"' in text

    result = runner.invoke(app, ["init", "--config", str(target)])
    assert result.exit_code == 1
    assert "already exists" in result.stdout + result.stderr

    result = runner.invoke(app, ["init", "--config", str(target), "--force"])
    assert result.exit_code == 0
    assert "Wrote" in result.stdout


def test_doctor_passes_with_valid_config(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    write_minimal_config(config)
    (tmp_path / "src").mkdir()
    # Point path at tmp_path itself
    config.write_text(
        config.read_text(encoding="utf-8").replace('path = "."', f'path = "{tmp_path}"'),
        encoding="utf-8",
    )
    checks = run_doctor_checks(config_path=config, output_directory=tmp_path / "reports")
    assert all(item.ok for item in checks)

    result = runner.invoke(
        app,
        ["doctor", "--config", str(config), "--output", str(tmp_path / "reports")],
    )
    assert result.exit_code == 0
    assert "All doctor checks passed" in result.stdout


def test_doctor_fails_when_config_missing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "doctor",
            "--config",
            str(tmp_path / "missing.toml"),
            "--output",
            str(tmp_path / "reports"),
        ],
    )
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "codestrata init" in result.stdout


def test_examples_command() -> None:
    result = runner.invoke(app, ["examples"])
    assert result.exit_code == 0
    assert "sample-js-app" in result.stdout
    assert "docs/quick-start.md" in result.stdout

    result = runner.invoke(app, ["examples", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert any(item["name"] == "sample-js-app" for item in payload["examples"])


def test_version_includes_report_and_ai() -> None:
    text = format_version_details()
    assert f"CodeStrata {get_package_version()}" in text
    assert "Engine:" in text
    assert f"Report HTML: {REPORT_HTML_VERSION}" in text
    assert "AI provider" in text

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Report HTML:" in result.stdout


def test_help_marks_assess_primary_and_scan_legacy() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "codestrata init" in result.stdout
    assert "Primary workflow: assess" in result.stdout
    assert "Legacy/advanced: scan" in result.stdout

    scan_help = runner.invoke(app, ["scan", "--help"])
    assert scan_help.exit_code == 0
    assert "Legacy" in scan_help.stdout or "prefer assess" in scan_help.stdout.lower()


def test_assess_help_includes_quiet_and_json_summary() -> None:
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    help_text = _visible_help(result)
    assert "--quiet" in help_text
    assert "--json-summary" in help_text
