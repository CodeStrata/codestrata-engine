"""Assess CLI integration for --telemetry-allow / --telemetry-deny (Slice 9.6)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.cli_consent_policy import TELEMETRY_FLAG_CONFLICT_MESSAGE
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    get_last_interactive_prompt_result,
    reset_telemetry_singletons,
)


def test_assess_allow_no_prompt_no_network(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("prompt must not run"),
    ):
        with patch("codestrata.telemetry.transport.send_payload") as send:
            result = runner.invoke(
                app,
                [
                    "assess",
                    "--repo",
                    str(repo),
                    "--output",
                    str(out),
                    "--no-ai",
                    "--quiet",
                    "--telemetry-allow",
                ],
            )
    assert result.exit_code in {0, 1}
    send.assert_not_called()
    assert "Telemetry enabled" not in (result.stdout + result.stderr)
    assert "Allow privacy-safe" not in (result.stdout + result.stderr)
    assert list(home.iterdir()) == []


def test_assess_deny_quiet_clean(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("prompt must not run"),
    ):
        result = runner.invoke(
            app,
            [
                "assess",
                "--repo",
                str(repo),
                "--output",
                str(out),
                "--no-ai",
                "--quiet",
                "--json-summary",
                "--telemetry-deny",
            ],
        )
    assert result.exit_code in {0, 1}
    combined = result.stdout + result.stderr
    assert "Allow privacy-safe" not in combined
    assert "y/N" not in combined
    assert list(home.iterdir()) == []


def test_conflict_message_and_exit() -> None:
    reset_telemetry_singletons()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["assess", "--repo", ".", "--telemetry-allow", "--telemetry-deny"],
    )
    assert result.exit_code == 2
    assert TELEMETRY_FLAG_CONFLICT_MESSAGE in (result.stdout + result.stderr)


def test_simulated_allow_via_ensure() -> None:
    reset_telemetry_singletons()
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        telemetry_allow=True,
        quiet=True,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert (
        telemetry.runtime.session.decision_source is TelemetryDecisionSource.CLI_FLAG
    )
    prompt = get_last_interactive_prompt_result()
    assert prompt is not None
    assert getattr(prompt, "prompted") is False
    assert getattr(prompt, "attempts") == 0


def test_duplicate_allow_flags_harmless(tmp_path: Path) -> None:
    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repo),
            "--output",
            str(out),
            "--no-ai",
            "--quiet",
            "--telemetry-deny",
            "--telemetry-deny",
        ],
    )
    assert result.exit_code in {0, 1}
