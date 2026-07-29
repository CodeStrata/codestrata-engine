"""Tests for CLI product-experience helpers."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.report import open_html_report
from codestrata.cli.ux import (
    format_actionable_error,
    format_banner,
    format_onboarding_message,
    is_machine_mode,
    mark_onboarding_completed,
    onboarding_completed,
    update_check_enabled,
)

runner = CliRunner()


def test_banner_includes_branding() -> None:
    text = format_banner()
    assert "CodeStrata" in text
    assert "Community Edition" in text
    assert "docs.codestrata.ai" in text


def test_machine_mode_when_quiet_or_ci(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert is_machine_mode(quiet=True) is True
    assert is_machine_mode(json_output=True) is True
    monkeypatch.setenv("CI", "true")
    assert is_machine_mode() is True


def test_onboarding_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CODESTRATA_SKIP_ONBOARDING", raising=False)
    assert onboarding_completed() is False
    mark_onboarding_completed()
    assert onboarding_completed() is True
    message = format_onboarding_message()
    assert "Welcome to CodeStrata Community Edition" in message
    assert "codestrata assess" in message


def test_welcome_command_done(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CODESTRATA_SKIP_ONBOARDING", raising=False)
    result = runner.invoke(app, ["welcome", "--done"])
    assert result.exit_code == 0
    assert "Onboarding marked complete" in result.stdout
    assert onboarding_completed() is True


def test_actionable_error_shape() -> None:
    text = format_actionable_error(
        what="Something failed.",
        why="Because of X.",
        fix="Do Y.",
    )
    assert "Something failed." in text
    assert "Why:" in text
    assert "Fix:" in text
    assert "Learn more:" in text


def test_update_check_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CODESTRATA_CLI_UPDATE_CHECK", raising=False)
    assert update_check_enabled() is False


def test_open_finds_latest_html(tmp_path: Path) -> None:
    reports = tmp_path / "reports" / "run-a"
    reports.mkdir(parents=True)
    html = reports / "report.html"
    html.write_text("<html></html>", encoding="utf-8")
    found = open_html_report(output=tmp_path / "reports", no_browser=True)
    assert found == html.resolve()


def test_open_command_no_browser(tmp_path: Path) -> None:
    reports = tmp_path / "reports" / "run-b"
    reports.mkdir(parents=True)
    html = reports / "report.html"
    html.write_text("<html></html>", encoding="utf-8")
    result = runner.invoke(
        app,
        ["open", "--output", str(tmp_path / "reports"), "--no-browser"],
    )
    assert result.exit_code == 0
    assert "report.html" in result.stdout


def test_version_help_and_doctor_smoke(tmp_path: Path) -> None:
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "Common workflows" in help_result.stdout
    assert "open" in help_result.stdout

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
    assert "Edition: Community Edition" in version.stdout
    assert "Schema version:" in version.stdout
    assert "Operating System:" in version.stdout

    config = tmp_path / "codestrata.toml"
    config.write_text(
        '[repository]\npath = "."\nprofile = "community"\n',
        encoding="utf-8",
    )
    # Point repository path at tmp so doctor path check passes.
    config.write_text(
        f'[repository]\npath = "{tmp_path}"\nprofile = "community"\n',
        encoding="utf-8",
    )
    doctor = runner.invoke(
        app,
        [
            "doctor",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "reports"),
            "--quiet",
        ],
    )
    assert doctor.exit_code == 0
    assert "[OK] python:" in doctor.stdout
    assert "[OK] engine:" in doctor.stdout
    assert "All doctor checks passed" in doctor.stdout
