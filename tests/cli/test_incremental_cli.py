"""CLI tests for codestrata incremental (Phase 2F.3)."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from codestrata.cli import app

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _visible_help(result) -> str:
    """Normalize CLI help for flag assertions (strip ANSI; collapse whitespace)."""

    raw = f"{result.stdout or ''}{result.stderr or ''}"
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", raw))


def test_incremental_help() -> None:
    result = runner.invoke(app, ["incremental", "--help"])
    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "assess" in result.stdout
    assert "explain" in result.stdout


def test_incremental_plan_help() -> None:
    result = runner.invoke(app, ["incremental", "plan", "--help"])
    assert result.exit_code == 0
    help_text = _visible_help(result)
    assert "--previous-run-id" in help_text
    assert "--json" in help_text


def test_incremental_assess_help() -> None:
    result = runner.invoke(app, ["incremental", "assess", "--help"])
    assert result.exit_code == 0
    help_text = _visible_help(result)
    assert "--with-ai" in help_text
    assert "--equivalence-check" in help_text


def test_incremental_explain_help() -> None:
    result = runner.invoke(app, ["incremental", "explain", "--help"])
    assert result.exit_code == 0
    assert "--kind" in result.stdout
    assert "--limit" in result.stdout


def test_incremental_plan_blocked_when_rollout_off(tmp_path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "test-fixtures/sample-js-app"
        [incremental]
        rollout_mode = "off"
        """,
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "incremental",
            "plan",
            "test-fixtures/sample-js-app",
            "--config",
            str(config),
        ],
    )
    assert result.exit_code != 0
