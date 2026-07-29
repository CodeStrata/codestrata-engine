"""Tests for the CodeStrata branded CLI landing experience."""

from __future__ import annotations

import re
from io import StringIO
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.landing import (
    BRAND_STATEMENT,
    EDITION,
    PRODUCT_CATEGORY,
    WordmarkSize,
    detect_start_here_context,
    landing_suppressed,
    max_banner_width_for_terminal,
    render_landing,
    select_wordmark_size,
    show_landing_or_help,
    start_here_content,
    terminal_columns,
    wordmark_art,
    wordmark_width,
)

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _render(
    columns: int,
    *,
    cwd: Path | None = None,
    first_run: bool = False,
    force_mono: bool = True,
    no_color: bool = True,
) -> str:
    buf = StringIO()
    console = Console(
        file=buf,
        force_terminal=True,
        no_color=no_color,
        emoji=False,
        soft_wrap=False,
        legacy_windows=False,
    )
    console.size = (columns, 40)
    render_landing(
        console=console,
        columns=columns,
        cwd=cwd,
        include_first_run=first_run,
        force_mono=force_mono,
    )
    return buf.getvalue()


def _visible_len(line: str) -> int:
    return len(_ANSI_RE.sub("", line).rstrip("\n"))


def test_wordmark_sizes_and_widths() -> None:
    assert select_wordmark_size(160) is WordmarkSize.LARGE
    assert select_wordmark_size(120) is WordmarkSize.LARGE
    assert select_wordmark_size(119) is WordmarkSize.MEDIUM
    assert select_wordmark_size(100) is WordmarkSize.MEDIUM
    assert select_wordmark_size(80) is WordmarkSize.MEDIUM
    assert select_wordmark_size(79) is WordmarkSize.COMPACT
    assert select_wordmark_size(60) is WordmarkSize.COMPACT
    assert select_wordmark_size(40) is WordmarkSize.COMPACT

    large = wordmark_art(WordmarkSize.LARGE)
    medium = wordmark_art(WordmarkSize.MEDIUM)
    compact = wordmark_art(WordmarkSize.COMPACT)

    assert wordmark_width(large) <= max_banner_width_for_terminal(120)
    assert wordmark_width(medium) <= 78
    assert wordmark_width(compact) <= 20
    assert large != medium != compact

    # Wide: full multi-line ASCII. Standard: compact 2-line. Narrow: plain text.
    assert len(large.splitlines()) >= 5
    assert len(medium.splitlines()) == 2
    assert compact.strip() == "CODESTRATA"
    assert "╔" not in compact
    assert "█" not in compact


def test_responsive_layouts_no_overflow(tmp_path: Path) -> None:
    for cols in (40, 60, 79, 80, 100, 119, 120, 160):
        out = _render(cols, cwd=tmp_path)
        overs = [line for line in out.splitlines() if _visible_len(line) > cols]
        assert not overs, f"overflow at {cols}: {overs[:1]!r}"
        assert BRAND_STATEMENT in out
        assert PRODUCT_CATEGORY in out
        assert EDITION in out
        assert "Start Here" in out
        assert "Next Steps" in out
        assert "codestrata --help" in out
        assert "docs.codestrata.ai" in out
        assert "codestrata.ai" in out
        assert "╭─ Platform" not in out
        if cols < 80:
            # Narrow plain heading appears once; no second subtitle.
            assert out.count("CODESTRATA") == 1
            assert "█" not in out
            assert "╔" not in out
        else:
            # ASCII banners spell the brand; do not also print plain CODESTRATA.
            assert out.count("CODESTRATA") == 0
        if cols >= 50:
            assert "Assess + AI" in out
            assert "codestrata assess --repo . --with-ai" in out
            assert "AI Setup" in out
            assert "codestrata ai" in out
        else:
            assert "assess --repo . --with-ai" in out
            assert "codestrata ai" in out
        i_brand = out.index(BRAND_STATEMENT)
        i_cat = out.index(PRODUCT_CATEGORY)
        i_ed = out.index(EDITION)
        assert i_brand < i_cat < i_ed


def test_banner_tier_selection_in_render(tmp_path: Path) -> None:
    narrow = _render(60, cwd=tmp_path)
    assert "CODESTRATA" in narrow
    assert "█▀▀" not in narrow
    assert "██████" not in narrow

    standard = _render(80, cwd=tmp_path)
    assert "█▀▀" in standard
    assert "██████╗" not in standard

    wide = _render(120, cwd=tmp_path)
    assert "██████╗" in wide
    assert wide.count("CODESTRATA") == 0


def test_ansi_does_not_inflate_width(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODESTRATA_FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("codestrata.cli.landing._color_allowed", lambda: True)
    for cols in (80, 120):
        out = _render(cols, cwd=tmp_path, force_mono=False, no_color=False)
        # Rich may emit ANSI; width checks must ignore escapes either way.
        overs = [line for line in out.splitlines() if _visible_len(line) > cols]
        assert not overs, f"ANSI overflow at {cols}: {overs[:1]!r}"
        assert BRAND_STATEMENT in _ANSI_RE.sub("", out)


def test_terminal_columns_fallback_when_size_unavailable(monkeypatch) -> None:
    def _boom(*_args, **_kwargs) -> tuple[int, int]:
        raise OSError("no tty")

    monkeypatch.setattr("codestrata.cli.landing.shutil.get_terminal_size", _boom)
    assert terminal_columns() == 80


def test_landing_survives_unknown_terminal_size(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_args, **_kwargs) -> tuple[int, int]:
        raise OSError("no tty")

    monkeypatch.setattr("codestrata.cli.landing.shutil.get_terminal_size", _boom)
    out = _render(80, cwd=tmp_path)
    assert BRAND_STATEMENT in out
    assert "Start Here" in out


def test_start_here_context_aware(tmp_path: Path) -> None:
    ctx = detect_start_here_context(cwd=tmp_path)
    assert ctx.has_config is False
    content = start_here_content(ctx, columns=100)
    assert "Initialize" in content.headline
    assert content.command == "codestrata init"

    (tmp_path / "codestrata.toml").write_text("[repository]\npath = \".\"\n", encoding="utf-8")
    ctx = detect_start_here_context(cwd=tmp_path)
    content = start_here_content(ctx, columns=100)
    assert "Engineering Assessment" in content.headline
    assert "codestrata assess" in content.command

    report = tmp_path / "reports" / "run" / "report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<html></html>", encoding="utf-8")
    ctx = detect_start_here_context(cwd=tmp_path)
    content = start_here_content(ctx, columns=100)
    assert "Open" in content.headline
    assert content.command == "codestrata open"


def test_landing_suppression_rules(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("CODESTRATA_CLI_BANNER", raising=False)
    monkeypatch.delenv("CODESTRATA_CLI_MACHINE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    assert landing_suppressed(quiet=True) is True
    assert landing_suppressed(json_output=True) is True

    monkeypatch.setenv("CI", "true")
    assert landing_suppressed() is True
    monkeypatch.delenv("CI", raising=False)

    monkeypatch.setenv("CODESTRATA_CLI_BANNER", "0")
    assert landing_suppressed() is True
    monkeypatch.delenv("CODESTRATA_CLI_BANNER", raising=False)

    monkeypatch.setenv("TERM", "dumb")
    assert landing_suppressed() is True
    monkeypatch.setenv("TERM", "xterm-256color")

    monkeypatch.setenv("_CODESTRATA_COMPLETE", "source_bash")
    assert landing_suppressed() is True
    monkeypatch.delenv("_CODESTRATA_COMPLETE", raising=False)


def test_show_landing_or_help_falls_back_when_suppressed(capsys) -> None:
    show_landing_or_help(help_text="HELP_OUTPUT", quiet=True)
    captured = capsys.readouterr()
    assert "HELP_OUTPUT" not in captured.out
    assert BRAND_STATEMENT not in captured.out
    assert "Run `codestrata --help` for commands." in captured.out
    assert "CodeStrata Community Edition" in captured.out


def test_show_landing_renders_when_allowed(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "codestrata.cli.landing.landing_suppressed",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "codestrata.cli.landing.onboarding_completed",
        lambda: True,
    )
    show_landing_or_help(help_text="HELP_OUTPUT", cwd=tmp_path)
    captured = capsys.readouterr()
    assert BRAND_STATEMENT in captured.out
    assert "HELP_OUTPUT" not in captured.out
    assert "Platform" not in captured.out


def test_codestrata_help_is_full_reference() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Primary workflow: assess" in result.stdout
    assert "Usage:" in result.stdout
    assert "assess" in result.stdout


def test_bare_codestrata_in_ci_shows_help_not_landing(monkeypatch) -> None:
    monkeypatch.setenv("CI", "true")
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage:" not in result.stdout
    assert "CODE. UNDERSTOOD." not in result.stdout
    assert "Run `codestrata --help` for commands." in result.stdout


def test_welcome_uses_landing_when_forced(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "codestrata.cli.welcome.landing_suppressed",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "codestrata.cli.landing.onboarding_completed",
        lambda: True,
    )
    result = runner.invoke(app, ["welcome"])
    assert result.exit_code == 0
    assert BRAND_STATEMENT in result.stdout
    assert PRODUCT_CATEGORY in result.stdout
    assert EDITION in result.stdout


def test_no_color_monochrome_readable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    out = _render(100, cwd=tmp_path)
    assert BRAND_STATEMENT in out
    assert "Start Here" in out
    assert "\x1b[" not in out
