"""Tests for the CodeStrata command-line interface."""

from __future__ import annotations

import platform
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.package_metadata import get_about_info, get_package_version

runner = CliRunner()


def test_root_version_option() -> None:
    """``codestrata --version`` prints the installed package version."""

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"CodeStrata {get_package_version()}"
    assert "aimf" not in result.stdout.lower()


def test_version_command() -> None:
    """The version command should display version, report, AI, Python, and platform."""

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert f"CodeStrata {get_package_version()}" in result.stdout
    assert "Report HTML:" in result.stdout
    assert "AI provider" in result.stdout
    assert f"Python: {platform.python_version()}" in result.stdout
    assert f"Operating System: {platform.system()}" in result.stdout
    assert f"Platform: {platform.platform()}" in result.stdout
    assert "aimf" not in result.stdout.lower()


def test_about_command() -> None:
    """The about command should display verified product metadata."""

    info = get_about_info()
    result = runner.invoke(app, ["about"])

    assert result.exit_code == 0
    assert f"CodeStrata {info.version}" in result.stdout
    assert info.summary in result.stdout
    assert f"Website: {info.website}" in result.stdout
    assert f"GitHub: {info.github}" in result.stdout
    assert "https://github.com/CodeStrata/codestrata-engine" in result.stdout
    assert "aimf" not in result.stdout.lower()


def test_metadata_commands_need_no_repo_or_credentials(tmp_path: Path, monkeypatch) -> None:
    """Metadata commands work without repo args, cloud creds, or runtime dirs."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    for args in (["--version"], ["version"], ["about"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.stdout

    assert not (tmp_path / ".codestrata").exists()
    assert not any(tmp_path.iterdir())


def test_cli_help() -> None:
    """The CLI help should display the application description."""

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Engineering Assessment" in result.stdout
    assert "CodeStrata Engine" in result.stdout
    assert "https://docs.codestrata.ai" in result.stdout
    assert "getting-started" in result.stdout
    assert "version" in result.stdout
    assert "about" in result.stdout
    assert "--version" in result.stdout
    assert "assess" in result.stdout
    assert "aimf" not in result.stdout.lower()


def test_scan_help_shows_output_option() -> None:
    result = runner.invoke(app, ["scan", "--help"])

    assert result.exit_code == 0
    assert "--output" in result.stdout
    assert "text" in result.stdout
    assert "json" in result.stdout
