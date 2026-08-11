"""CodeStrata branded CLI landing page (presentation only).

Shown for bare ``codestrata`` and ``codestrata welcome`` in interactive
terminals. Never changes assessment behavior, schemas, or AI.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codestrata.cli.ux import (
    DOCS_HOME,
    WEBSITE,
    is_machine_mode,
    onboarding_completed,
)
from codestrata.package_metadata import get_package_version

# ---------------------------------------------------------------------------
# Terminal-compatible semantic palette (ANSI named styles only — never RGB).
#
# Web design-system teal must not be used as CLI chrome (low contrast on
# green/dark/saturated terminals). Foreground ANSI styles only — never
# bgcolor / reverse / screen fills.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LandingPalette:
    """Semantic CLI welcome styles for high contrast across common terminals."""

    brand_logo: str = "bold bright_cyan"
    brand_statement: str = "bold bright_white"
    product_category: str = "bold bright_white"
    edition: str = "bright_white"
    section_heading: str = "bold bright_yellow"
    command_label: str = "bold bright_yellow"
    command: str = "bold bright_cyan"
    primary_text: str = "bright_white"
    explanatory: str = "bright_white"
    footer: str = "bright_white"
    panel_border: str = "bright_cyan"
    panel_title: str = "bold bright_yellow"


LANDING_PALETTE = LandingPalette()

# Public aliases (historical importers). Map to high-contrast ANSI — not web teal.
ACCENT = LANDING_PALETTE.section_heading
ACCENT_BRIGHT = LANDING_PALETTE.brand_logo
ACCENT_DIM = LANDING_PALETTE.panel_border
AMBER = ACCENT
AMBER_BRIGHT = ACCENT_BRIGHT
AMBER_DIM = ACCENT_DIM
BRIGHT_WHITE = LANDING_PALETTE.brand_statement
WHITE = LANDING_PALETTE.primary_text
DIM = LANDING_PALETTE.explanatory  # no longer Rich "dim" — too low-contrast
CYAN = LANDING_PALETTE.command

# Forbidden in CLI welcome styling (web design-system teal, digits only).
_FORBIDDEN_CLI_HEX = frozenset({"0f5d54", "16756a"})

BRAND_STATEMENT = "CODE. UNDERSTOOD."
PRODUCT_CATEGORY = "Engineering Assessment"
EDITION = "Community Edition"


class WordmarkSize(StrEnum):
    LARGE = "large"
    MEDIUM = "medium"
    COMPACT = "compact"


# Clean CodeStrata wordmarks — original strata letterforms with consistent gaps.
# Width strategy (validated in tests):
#   LARGE  (≥120 cols): full 6-row banner, ~92 cols (≤ ~75% of 120)
#   MEDIUM (80–119):    compact 2-row banner with clear letter separation
#   COMPACT (<80):      plain "CODESTRATA" (no large ASCII art)


# Large: premium double-line glyphs with consistent one-column letter spacing.
# Width 90 → ≤75% of a 120-column terminal.
_WORDMARK_LARGE = """\
 ██████╗  ██████╗  ██████╗  ███████╗ ███████╗ ███████╗ ██████╗   █████╗  ███████╗  █████╗
██╔════╝ ██╔═══██╗ ██╔══██╗ ██╔════╝ ██╔════╝ ╚══██╔═╝ ██╔══██╗ ██╔══██╗ ╚══██╔═╝ ██╔══██╗
██║      ██║   ██║ ██║  ██║ █████╗   ███████╗    ██║   ██████╔╝ ███████║    ██║   ███████║
██║      ██║   ██║ ██║  ██║ ██╔══╝   ╚════██║    ██║   ██╔══██╗ ██╔══██║    ██║   ██╔══██║
╚██████╗ ╚██████╔╝ ██████╔╝ ███████╗ ███████║    ██║   ██║  ██║ ██║  ██║    ██║   ██║  ██║
 ╚═════╝  ╚═════╝  ╚═════╝  ╚══════╝ ╚══════╝    ╚═╝   ╚═╝  ╚═╝ ╚═╝  ╚═╝    ╚═╝   ╚═╝  ╚═╝"""

# Medium: compact half-block glyphs; double spaces keep letters distinct at 80 cols.
_WORDMARK_MEDIUM = """\
█▀▀  █▀█  █▀▄  █▀▀  █▀▀  ▀█▀  █▀█  ▄▀█  ▀█▀  ▄▀█
█▄▄  █▄█  █▄▀  ██▄  ▄▄█   █   █▀▄  █▀█   █   █▀█"""

# Narrow: plain heading — never large ASCII art below 80 columns.
_WORDMARK_COMPACT = "CODESTRATA"


@dataclass(frozen=True, slots=True)
class StartHereContext:
    """Local-only cues for the Start Here panel (no repository scanning)."""

    has_config: bool
    has_report: bool
    config_path: Path
    reports_dir: Path


@dataclass(frozen=True, slots=True)
class StartHereContent:
    headline: str
    command: str


def terminal_columns(console: Console | None = None) -> int:
    """Best-effort terminal width for responsive layout."""

    if console is not None:
        return max(40, int(console.width or 80))
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return max(40, int(size.columns))
    except OSError:
        return 80


def select_wordmark_size(columns: int) -> WordmarkSize:
    """Choose banner layout from terminal width.

    - ≥120: full branded ASCII (large)
    - 80–119: compact ASCII (medium)
    - <80: plain ``CODESTRATA`` heading (compact)
    """

    if columns >= 120:
        return WordmarkSize.LARGE
    if columns >= 80:
        return WordmarkSize.MEDIUM
    return WordmarkSize.COMPACT


def wordmark_art(size: WordmarkSize | None = None, *, columns: int | None = None) -> str:
    """Return the CodeStrata wordmark for the given layout size."""

    resolved = size
    if resolved is None:
        resolved = select_wordmark_size(columns if columns is not None else terminal_columns())
    if resolved is WordmarkSize.LARGE:
        art = _WORDMARK_LARGE
    elif resolved is WordmarkSize.MEDIUM:
        art = _WORDMARK_MEDIUM
    else:
        art = _WORDMARK_COMPACT
    return _equalize_wordmark_width(art)


def _equalize_wordmark_width(art: str) -> str:
    """Pad wordmark rows to a common width so centering stays visually aligned."""

    lines = art.splitlines()
    width = max((len(line) for line in lines), default=0)
    return "\n".join(line.ljust(width) for line in lines)


def wordmark_width(art: str) -> int:
    lines = [line.rstrip("\n") for line in art.splitlines() if line.strip()]
    return max((len(line) for line in lines), default=0)


def max_banner_width_for_terminal(columns: int) -> int:
    """Approximate max banner width (~75% of terminal, with a small margin)."""

    return max(10, int(columns * 0.75))


def is_shell_completion_context() -> bool:
    """Detect Click/Typer shell-completion invocations."""

    for key in os.environ:
        upper = key.upper()
        if upper.endswith("_COMPLETE") or upper.startswith("_TYPER_COMPLETE"):
            return True
    return False


def landing_suppressed(
    *,
    quiet: bool = False,
    json_output: bool = False,
) -> bool:
    """Return True when the branded landing must not render."""

    if quiet or json_output:
        return True
    if is_shell_completion_context():
        return True
    if os.environ.get("CODESTRATA_CLI_BANNER", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return True
    if is_machine_mode(quiet=quiet, json_output=json_output):
        return True
    return False


def detect_start_here_context(
    *,
    cwd: Path | None = None,
    config_name: str = "codestrata.toml",
    reports_dirname: str = ".codestrata-artifacts/assessments",
) -> StartHereContext:
    """Inspect local files only — never scan repository contents."""

    root = cwd or Path.cwd()
    config_path = root / config_name
    reports_dir = root / reports_dirname
    has_report = False
    if reports_dir.is_dir():
        try:
            has_report = any(reports_dir.rglob("assessment.html"))
        except OSError:
            has_report = False
    return StartHereContext(
        has_config=config_path.is_file(),
        has_report=has_report,
        config_path=config_path,
        reports_dir=reports_dir,
    )


def start_here_content(
    context: StartHereContext,
    *,
    columns: int = 80,
) -> StartHereContent:
    if not context.has_config:
        return StartHereContent(
            headline="Initialize your workspace.",
            command="codestrata init",
        )
    if context.has_report:
        return StartHereContent(
            headline="Open your latest report.",
            command="codestrata open",
        )
    # Keep the assess command copyable without wrapping on narrow terminals.
    if columns < 80:
        assess_cmd = "codestrata assess --repo ."
        headline = "Generate your first assessment."
    else:
        assess_cmd = "codestrata assess --repo ."
        headline = "Generate your first Engineering Assessment."
    return StartHereContent(
        headline=headline,
        command=assess_cmd,
    )


def _center_plain(text: str, width: int) -> str:
    """Legacy helper retained for tests / callers that center plain strings."""

    lines = text.splitlines()
    return "\n".join(line.center(width) if line.strip() else line for line in lines)


def _styled_console(*, force_mono: bool = False, width: int | None = None) -> Console:
    no_color = force_mono or not _color_allowed()
    # No Console-level style/theme: never paint a terminal-wide background.
    console = Console(
        force_terminal=True,
        no_color=no_color,
        highlight=False,
        soft_wrap=False,
        emoji=False,
        style=None,
    )
    if width is not None:
        console.size = (width, console.size.height or 24)
    return console


def _color_allowed() -> bool:
    if os.environ.get("NO_COLOR", "").strip():
        return False
    if os.environ.get("CODESTRATA_FORCE_COLOR", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _fg(text: str, style: str, *, enabled: bool) -> Text:
    """Foreground-only styled text (never bgcolor / reverse)."""

    return Text(text, style=style if enabled else "")


def _center_styled(content: str, style: str, width: int, *, enabled: bool) -> Text:
    """Center content without coloring padding spaces (avoids full-line washes)."""

    stripped = content.rstrip("\n")
    lines = stripped.splitlines() or [""]
    result = Text()
    for index, line in enumerate(lines):
        if index:
            result.append("\n")
        pad = max(0, (width - len(line)) // 2)
        if pad:
            result.append(" " * pad)
        result.append(line, style=style if enabled else "")
        trail = width - pad - len(line)
        if trail > 0:
            result.append(" " * trail)
    return result


def render_landing(
    *,
    console: Console | None = None,
    columns: int | None = None,
    cwd: Path | None = None,
    include_first_run: bool = True,
    force_mono: bool = False,
) -> None:
    """Render the branded CodeStrata landing page to the console."""

    active = console or _styled_console(force_mono=force_mono)
    width = columns if columns is not None else terminal_columns(active)
    # Rich only honors Console.width when height is also set (size property).
    height = getattr(active.size, "height", 24) or 24
    active.size = (width, height)
    size = select_wordmark_size(width)
    art = wordmark_art(size)
    banner_budget = max_banner_width_for_terminal(width)

    # Step down when art exceeds the terminal or the ~75% banner budget.
    while size is not WordmarkSize.COMPACT and (
        wordmark_width(art) > width - 2 or wordmark_width(art) > banner_budget
    ):
        size = WordmarkSize.MEDIUM if size is WordmarkSize.LARGE else WordmarkSize.COMPACT
        art = wordmark_art(size)
    if wordmark_width(art) > width - 2:
        art = _WORDMARK_COMPACT

    use_color = not active.no_color and _color_allowed() and not force_mono
    palette = LANDING_PALETTE

    wordmark = _center_styled(art, palette.brand_logo, width, enabled=use_color)
    brand = _center_styled(BRAND_STATEMENT, palette.brand_statement, width, enabled=use_color)
    category = _center_styled(PRODUCT_CATEGORY, palette.product_category, width, enabled=use_color)
    edition = _center_styled(EDITION, palette.edition, width, enabled=use_color)

    start = start_here_content(
        detect_start_here_context(cwd=cwd),
        columns=width,
    )
    start_body = Text(justify="center")
    start_body.append(
        start.headline,
        style=palette.primary_text if use_color else "",
    )
    start_body.append("\n")
    start_body.append(
        start.command,
        style=palette.command if use_color else "bold",
    )
    # Panel: focal point — transparent content area (preserve terminal background).
    h_pad = 2 if width < 80 else 3
    needed = max(
        len(start.command) + (h_pad * 2) + 2,
        min(len(start.headline) + (h_pad * 2) + 2, width - 4),
        28 if width >= 60 else 24,
    )
    panel_w = max(24, min(needed, width - 2, 72 if width >= 80 else width - 2))
    start_panel = Panel(
        Align.center(start_body),
        title=_fg("Start Here", palette.panel_title, enabled=use_color),
        border_style=palette.panel_border if use_color else "bold",
        width=panel_w,
        padding=(1, h_pad),
        style="",
    )

    # Next Steps: fixed-width right-aligned labels for a flush command column.
    label_width = 5 if width < 50 else 11
    steps = Table.grid(padding=(0, 2 if width >= 60 else 1), expand=False)
    steps.add_column(
        justify="right",
        width=label_width,
        style=palette.command_label if use_color else "bold",
        no_wrap=True,
    )
    steps.add_column(style=palette.command if use_color else "bold", no_wrap=True)
    if width < 50:
        steps.add_row("Init", "codestrata init")
        steps.add_row("Assess", "assess --repo .")
        steps.add_row("AI", "assess --repo . --with-ai")
        steps.add_row("Open", "codestrata open")
    else:
        steps.add_row("Initialize", "codestrata init")
        steps.add_row("Assess", "codestrata assess --repo .")
        steps.add_row("Assess + AI", "codestrata assess --repo . --with-ai")
        steps.add_row("Open Report", "codestrata open")

    # Telemetry discovery — disabled by default; not required for assessment.
    telemetry = Table.grid(padding=(0, 2 if width >= 60 else 1), expand=False)
    telemetry.add_column(
        justify="right",
        width=label_width,
        style=palette.command_label if use_color else "bold",
        no_wrap=True,
    )
    telemetry.add_column(
        style=palette.explanatory if use_color else "",
        no_wrap=True,
    )
    if width < 50:
        telemetry.add_row("Status", "Disabled by default")
        telemetry.add_row("Opt in", "assess --telemetry-allow")
        telemetry.add_row("Deny", "assess --telemetry-deny")
        telemetry.add_row("Docs", "docs…/reference/telemetry")
    elif width < 80:
        telemetry.add_row("Status", "Disabled by default")
        telemetry.add_row("Opt in", "assess --repo . --telemetry-allow")
        telemetry.add_row("Deny", "assess --repo . --telemetry-deny")
        telemetry.add_row("Docs", "docs.codestrata.ai/reference/telemetry")
    else:
        telemetry.add_row("Status", "Disabled by default")
        telemetry.add_row("Opt in", "codestrata assess --repo . --telemetry-allow")
        telemetry.add_row("Deny", "codestrata assess --repo . --telemetry-deny")
        telemetry.add_row("Docs", "docs.codestrata.ai/reference/telemetry")

    # Share Report — local by default; publish is a separate explicit action.
    share = Table.grid(padding=(0, 2 if width >= 60 else 1), expand=False)
    share.add_column(
        justify="right",
        width=label_width,
        style=palette.command_label if use_color else "bold",
        no_wrap=True,
    )
    share.add_column(
        style=palette.explanatory if use_color else "",
        no_wrap=True,
    )
    if width < 50:
        share_note = "Reports are local by default."
        share.add_row("Publish", "report publish --help")
        share.add_row("URL", "reports…/r/<opaque-id>")
    elif width < 80:
        share_note = "Reports are local by default."
        share.add_row("Publish", "codestrata report publish")
        share.add_row("URL", "reports.codestrata.ai/r/<opaque-id>")
    else:
        share_note = "Reports are local by default."
        share.add_row("Publish", "codestrata report publish")
        share.add_row("Public URL", "https://reports.codestrata.ai/r/<opaque-id>")

    version = get_package_version()
    meta = f"Engine {version} • {EDITION}"
    if len(meta) > width:
        meta = f"Engine {version}"
    docs_host = DOCS_HOME.replace("https://", "").replace("http://", "")
    site_host = WEBSITE.replace("https://", "").replace("http://", "")
    links = f"{docs_host} • {site_host} • codestrata --help"
    if len(links) > width:
        links = f"{docs_host} • codestrata --help"
    if len(links) > width:
        links = "codestrata --help"

    blocks: list[RenderableType] = []
    if include_first_run and not onboarding_completed():
        welcome = (
            "Welcome to CodeStrata Community Edition." if width >= 42 else "Welcome to CodeStrata."
        )
        blocks.append(
            _center_styled(welcome, palette.brand_statement, width, enabled=use_color)
        )
        blocks.append(Text(""))

    blocks.extend(
        [
            wordmark,
            Text(""),
            brand,
            category,
            edition,
            Text(""),
            Align.center(start_panel, width=width),
            Text(""),
            _center_styled("Next Steps", palette.section_heading, width, enabled=use_color),
            Align.center(steps, width=width),
            Text(""),
            _center_styled("Telemetry", palette.section_heading, width, enabled=use_color),
            Align.center(telemetry, width=width),
            Text(""),
            _center_styled("Share Report", palette.section_heading, width, enabled=use_color),
            _center_styled(share_note, palette.explanatory, width, enabled=use_color),
            Align.center(share, width=width),
            Text(""),
            _center_styled(meta, palette.footer, width, enabled=use_color),
            _center_styled(links, palette.footer, width, enabled=use_color),
        ]
    )

    active.print(Group(*blocks), soft_wrap=False)


def render_automation_fallback() -> None:
    """Concise bare-invocation output when the landing page is suppressed.

    Deterministic, non-Rich, no full command inventory. Exit code is owned by
    the caller (normally 0).
    """

    version = get_package_version()
    sys.stdout.write(
        f"CodeStrata Community Edition {version}\n"
        "Engineering Assessment (single repository).\n"
        "Assess locally: codestrata assess --repo .\n"
        "Telemetry: disabled by default; "
        "codestrata assess --repo . --telemetry-allow\n"
        "Reports are local by default; "
        "codestrata report publish --help\n"
        "Public URL shape: https://reports.codestrata.ai/r/<opaque-id>\n"
        "Docs: https://docs.codestrata.ai\n"
        "Run `codestrata --help` for commands.\n"
    )


def show_bare_invocation(*, cwd: Path | None = None) -> None:
    """Single owner of bare ``codestrata`` output (landing or concise fallback).

    Never call ``ctx.get_help()`` here: with Rich markup mode, Click's
    ``get_help()`` prints the full help inventory to stdout as a side effect.
    """

    if landing_suppressed():
        render_automation_fallback()
        return
    render_landing(cwd=cwd)
    try:
        from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in

        maybe_prompt_telemetry_opt_in()
    except Exception:  # noqa: BLE001 - never break landing
        return


# Back-compat alias used by older call sites / tests.
def show_landing_or_help(
    *,
    help_text: str = "",
    quiet: bool = False,
    json_output: bool = False,
    cwd: Path | None = None,
) -> None:
    """Deprecated wrapper — prefer ``show_bare_invocation``."""

    del help_text
    if landing_suppressed(quiet=quiet, json_output=json_output):
        render_automation_fallback()
        return
    render_landing(cwd=cwd)


__all__ = [
    "ACCENT",
    "ACCENT_BRIGHT",
    "AMBER",
    "AMBER_BRIGHT",
    "BRAND_STATEMENT",
    "EDITION",
    "LANDING_PALETTE",
    "LandingPalette",
    "PRODUCT_CATEGORY",
    "StartHereContent",
    "StartHereContext",
    "WordmarkSize",
    "detect_start_here_context",
    "is_shell_completion_context",
    "landing_suppressed",
    "max_banner_width_for_terminal",
    "render_automation_fallback",
    "render_landing",
    "select_wordmark_size",
    "show_bare_invocation",
    "show_landing_or_help",
    "start_here_content",
    "terminal_columns",
    "wordmark_art",
    "wordmark_width",
]
