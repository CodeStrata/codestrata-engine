"""CLI surface and assess integration for interactive consent (Slice 9.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.service import reset_telemetry_singletons


def test_W_cli_help_unchanged_no_flags() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    assert "--telemetry-allow" not in result.stdout
    assert "--telemetry-deny" not in result.stdout
    for name in ("status", "enable", "disable", "reset", "show"):
        assert name in result.stdout


def test_help_and_version_do_not_prompt() -> None:
    reset_telemetry_singletons()
    runner = CliRunner()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt"
    ) as prompt:
        assert runner.invoke(app, ["--help"]).exit_code == 0
        assert runner.invoke(app, ["version"]).exit_code == 0
        assert runner.invoke(app, ["telemetry", "status"]).exit_code == 0
        prompt.assert_not_called()


def test_assess_non_interactive_cli_runner_does_not_hang(tmp_path: Path) -> None:
    """CliRunner has non-TTY stdin — eligibility must skip prompt without blocking."""

    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
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
            ],
        )
    # Quiet mode is ineligible; should not hang waiting for input.
    assert result.exit_code in {0, 1}
    send.assert_not_called()


def test_assess_simulated_interactive_yes_no_network(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    from codestrata.telemetry.service import ensure_interactive_product_telemetry

    with patch(
        "codestrata.telemetry.product_transport.try_create_production_http_transport",
        return_value=None,
    ), patch("codestrata.telemetry.transport.send_payload") as send:
        telemetry = ensure_interactive_product_telemetry(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            input_func=lambda _p: "y",
            echo_func=lambda _m: None,
        )
        telemetry.record_assessment_completed(
            ai_enabled=False,
            ai_executed=False,
            success=True,
            duration_ms=1.0,
        )
        send.assert_not_called()
    leftover = {p.name for p in home.iterdir()}
    assert "telemetry.json" in leftover
    assert leftover <= {"telemetry.json", "installation_id"}
    assert telemetry.runtime.session.counters.transport_sent == 0
    assert telemetry.runtime.session.counters.transmission_attempts >= 1
    assert telemetry.runtime.session.consent.persisted is True
