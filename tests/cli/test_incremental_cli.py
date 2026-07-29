"""CLI tests for codestrata incremental (Phase 2F.3)."""

from __future__ import annotations

from typer.testing import CliRunner

from codestrata.cli import app

runner = CliRunner()


def test_incremental_help() -> None:
    result = runner.invoke(app, ["incremental", "--help"])
    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "assess" in result.stdout
    assert "explain" in result.stdout


def test_incremental_plan_help() -> None:
    result = runner.invoke(app, ["incremental", "plan", "--help"])
    assert result.exit_code == 0
    assert "--previous-run-id" in result.stdout
    assert "--json" in result.stdout


def test_incremental_assess_help() -> None:
    result = runner.invoke(app, ["incremental", "assess", "--help"])
    assert result.exit_code == 0
    assert "--with-ai" in result.stdout
    assert "--equivalence-check" in result.stdout


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
