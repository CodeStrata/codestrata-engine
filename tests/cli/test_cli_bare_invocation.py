"""Entry-point regression tests for Phase 12.8.3 bare invocation & Community surface."""

from __future__ import annotations

import re
from pathlib import Path

import typer.main
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.landing import BRAND_STATEMENT, EDITION, PRODUCT_CATEGORY
from codestrata.package_metadata import format_version_line, get_package_version

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", text)


def test_bare_interactive_invocation_landing_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "codestrata.cli.landing.landing_suppressed",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "codestrata.cli.landing.onboarding_completed",
        lambda: True,
    )
    result = runner.invoke(app, [])
    out = _strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert BRAND_STATEMENT in out
    assert PRODUCT_CATEGORY in out
    assert EDITION in out
    assert out.count(BRAND_STATEMENT) == 1
    assert "Usage:" not in out
    assert "Options" not in out
    assert "╭─ Primary" not in out
    assert "╭─ Options" not in out
    assert "╭─ Advanced" not in out


def test_explicit_help_is_full_reference_without_landing() -> None:
    result = runner.invoke(app, ["--help"])
    out = _strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert "Usage:" in out
    assert "Options" in out
    assert "assess" in out
    assert "init" in out
    assert "doctor" in out
    assert BRAND_STATEMENT not in out
    assert "╭─ Platform" not in out
    assert "╭─ Maintainer" not in out


def test_welcome_landing_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "codestrata.cli.welcome.landing_suppressed",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "codestrata.cli.landing.onboarding_completed",
        lambda: True,
    )
    result = runner.invoke(app, ["welcome"])
    out = _strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert BRAND_STATEMENT in out
    assert out.count(BRAND_STATEMENT) == 1
    assert "Usage:" not in out


def test_version_command_no_landing() -> None:
    result = runner.invoke(app, ["version"])
    out = result.stdout
    assert result.exit_code == 0
    assert BRAND_STATEMENT not in out
    assert "Usage:" not in out
    assert f"Engine: {get_package_version()}" in out


def test_suppressed_non_tty_bare_fallback(monkeypatch) -> None:
    monkeypatch.setenv("CI", "true")
    result = runner.invoke(app, [])
    out = result.stdout
    assert result.exit_code == 0
    assert BRAND_STATEMENT not in out
    assert "Usage:" not in out
    assert "╭─ Primary" not in out
    assert "CodeStrata Community Edition" in out
    assert "Run `codestrata --help` for commands." in out
    assert get_package_version() in out


def test_community_command_registry_excludes_platform_and_maintainer() -> None:
    click_cmd = typer.main.get_command(app)
    names = set(click_cmd.list_commands(None))  # type: ignore[arg-type]
    # Community owns ``ai`` (assess provider discovery). Platform/maintainer only.
    for forbidden in ("enterprise", "repository", "acceptance", "release"):
        assert forbidden not in names, f"{forbidden} must not be on Community CLI"
    assert "ai" in names
    assert "assess" in names
    assert "doctor" in names


def test_help_lists_community_ai_command() -> None:
    result = runner.invoke(app, ["--help"])
    out = _strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert "ai" in out
    assert "╭─ Platform" not in out


def test_version_consistency_across_surfaces(monkeypatch, tmp_path: Path) -> None:
    canonical = get_package_version()
    assert format_version_line() == f"CodeStrata {canonical}"

    version_cmd = runner.invoke(app, ["version"])
    assert f"Engine: {canonical}" in version_cmd.stdout
    assert f"CLI: {canonical}" in version_cmd.stdout

    eager = runner.invoke(app, ["--version"])
    assert eager.stdout.strip() == f"CodeStrata {canonical}"

    monkeypatch.setattr(
        "codestrata.cli.landing.landing_suppressed",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "codestrata.cli.landing.onboarding_completed",
        lambda: True,
    )
    landing = runner.invoke(app, [])
    assert f"Engine {canonical}" in landing.stdout
