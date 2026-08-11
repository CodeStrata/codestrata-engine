"""Shared CLI product-experience helpers (branding, messages, terminals).

Human-friendly output only. Machine modes (``--quiet``, ``--json``,
``--json-summary``, ``NO_COLOR``, non-TTY, ``CI``) suppress banners and chrome.
Does not change assessment, Engineering Intelligence, report schemas, or AI.
"""

from __future__ import annotations

import os
import shutil
import sys
from enum import StrEnum
from pathlib import Path
from typing import TextIO

import typer

from codestrata.package_metadata import PRODUCT_NAME, get_package_version

DOCS_HOME = "https://docs.codestrata.ai"
DOCS_GETTING_STARTED = f"{DOCS_HOME}/getting-started/"
DOCS_TROUBLESHOOTING = f"{DOCS_HOME}/troubleshooting/"
DOCS_VSCODE = f"{DOCS_HOME}/extensions/vscode"
DOCS_CURSOR = f"{DOCS_HOME}/extensions/cursor"
DOCS_CLI = f"{DOCS_HOME}/reference/cli"
WEBSITE = "https://codestrata.ai"
GITHUB_ISSUES = "https://github.com/CodeStrata/codestrata-engine/issues"

# Local state (not telemetry). Lives under the Engine knowledge/workspace parent.
_CLI_STATE_DIRNAME = ".codestrata"
_CLI_STATE_FILE = "cli-state.toml"
_ONBOARDING_KEY = "onboarding_completed"


class MessageKind(StrEnum):
    """Consistent message prefixes (text + optional color)."""

    SUCCESS = "Success"
    WARNING = "Warning"
    ERROR = "Error"
    INFO = "Info"
    TIP = "Tip"


def color_enabled(*, stream: TextIO | None = None) -> bool:
    """Return whether ANSI colors should be used."""

    if os.environ.get("NO_COLOR", "").strip():
        return False
    if os.environ.get("CODESTRATA_FORCE_COLOR", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    target = stream or sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def is_machine_mode(
    *,
    quiet: bool = False,
    json_output: bool = False,
) -> bool:
    """Detect automation contexts where banners and chrome must not appear."""

    if quiet or json_output:
        return True
    if os.environ.get("CI", "").strip():
        return True
    if os.environ.get("CODESTRATA_CLI_MACHINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    term = os.environ.get("TERM", "").strip().lower()
    if term in {"", "dumb"}:
        return True
    return not sys.stdout.isatty()


def emit(
    kind: MessageKind,
    message: str,
    *,
    err: bool = False,
) -> None:
    """Print a labeled message with accessible text (color is optional)."""

    stream_err = err or kind == MessageKind.ERROR
    color_map = {
        MessageKind.SUCCESS: typer.colors.GREEN,
        MessageKind.WARNING: typer.colors.YELLOW,
        MessageKind.ERROR: typer.colors.RED,
        MessageKind.INFO: typer.colors.BLUE,
        MessageKind.TIP: typer.colors.CYAN,
    }
    prefix = f"{kind.value}:"
    line = f"{prefix} {message}"
    if color_enabled(stream=sys.stderr if stream_err else sys.stdout):
        typer.secho(line, fg=color_map[kind], err=stream_err)
    else:
        typer.echo(line, err=stream_err)


def success(message: str) -> None:
    emit(MessageKind.SUCCESS, message)


def warning(message: str, *, err: bool = True) -> None:
    emit(MessageKind.WARNING, message, err=err)


def error(message: str) -> None:
    emit(MessageKind.ERROR, message, err=True)


def info(message: str) -> None:
    emit(MessageKind.INFO, message)


def tip(message: str) -> None:
    emit(MessageKind.TIP, message)


def format_path_link(path: Path | str, *, label: str | None = None) -> str:
    """Return a path string, with OSC-8 hyperlink when the terminal supports it."""

    text = str(path)
    display = label or text
    if is_machine_mode() or not color_enabled():
        return display
    try:
        resolved = Path(path).expanduser().resolve()
        uri = resolved.as_uri()
    except OSError:
        return display
    # OSC 8 hyperlink (iTerm2, Windows Terminal, many Linux terminals).
    return f"\033]8;;{uri}\033\\{display}\033]8;;\033\\"


def format_url(url: str, *, label: str | None = None) -> str:
    """Return a URL, optionally as an OSC-8 hyperlink."""

    display = label or url
    if is_machine_mode() or not color_enabled():
        return f"{display} ({url})" if label else url
    return f"\033]8;;{url}\033\\{display}\033]8;;\033\\"


def cli_state_path() -> Path:
    """Path to local CLI state (onboarding flags). Never sent over the network."""

    return Path.cwd() / _CLI_STATE_DIRNAME / _CLI_STATE_FILE


def read_cli_state() -> dict[str, str]:
    path = cli_state_path()
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    data: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"')
    return data


def write_cli_state(updates: dict[str, str]) -> None:
    current = read_cli_state()
    current.update(updates)
    path = cli_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "# CodeStrata CLI local state (not telemetry)\n" + "".join(
            f'{key} = "{value}"\n' for key, value in sorted(current.items())
        )
        path.write_text(body, encoding="utf-8")
    except OSError:
        return


def onboarding_completed() -> bool:
    if os.environ.get("CODESTRATA_SKIP_ONBOARDING", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    value = read_cli_state().get(_ONBOARDING_KEY, "").lower()
    return value in {"1", "true", "yes"}


def mark_onboarding_completed() -> None:
    write_cli_state({_ONBOARDING_KEY: "true"})


def format_banner(*, edition: str = "Community Edition") -> str:
    """Compact startup banner (interactive human sessions only)."""

    version = get_package_version()
    return "\n".join(
        (
            f"{PRODUCT_NAME} Engine · {edition}",
            f"Version {version}",
            f"Docs  {DOCS_HOME}",
            f"Site  {WEBSITE}",
        )
    )


def maybe_print_banner(*, quiet: bool = False, json_output: bool = False) -> None:
    if is_machine_mode(quiet=quiet, json_output=json_output):
        return
    if os.environ.get("CODESTRATA_CLI_BANNER", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return
    typer.echo(format_banner())
    typer.echo("")


def format_onboarding_message() -> str:
    return "\n".join(
        (
            f"Welcome to {PRODUCT_NAME} Community Edition.",
            "",
            "Next steps:",
            "  1. Assess a repository (local by default)",
            "       codestrata assess --repo . --no-ai",
            "  2. View your report",
            "       codestrata open",
            "  3. Install the VS Code extension",
            f"       {DOCS_VSCODE}",
            "  4. Install the Cursor extension",
            f"       {DOCS_CURSOR}",
            "  5. Read the documentation",
            f"       {DOCS_GETTING_STARTED}",
            "",
            "Disable this message:",
            "  codestrata welcome --done",
            "  or set CODESTRATA_SKIP_ONBOARDING=1",
        )
    )


def maybe_print_onboarding(*, quiet: bool = False, json_output: bool = False) -> None:
    if is_machine_mode(quiet=quiet, json_output=json_output):
        return
    if onboarding_completed():
        return
    typer.echo(format_onboarding_message())
    typer.echo("")


def docs_footer() -> str:
    return "\n".join(
        (
            "Documentation:",
            f"  Docs            {DOCS_HOME}",
            f"  Getting started {DOCS_GETTING_STARTED}",
            f"  Troubleshooting {DOCS_TROUBLESHOOTING}",
            f"  VS Code         {DOCS_VSCODE}",
            f"  Cursor          {DOCS_CURSOR}",
            f"  Issues          {GITHUB_ISSUES}",
        )
    )


def format_actionable_error(
    *,
    what: str,
    why: str | None = None,
    fix: str | None = None,
    learn_more: str | None = DOCS_TROUBLESHOOTING,
) -> str:
    """Build an actionable user-facing error (no stack trace)."""

    lines = [what]
    if why:
        lines.append(f"Why: {why}")
    if fix:
        lines.append(f"Fix: {fix}")
    if learn_more:
        lines.append(f"Learn more: {learn_more}")
    return "\n".join(lines)


def which_or_none(name: str) -> str | None:
    return shutil.which(name)


def update_check_enabled() -> bool:
    """Optional update notices — off by default; never automatic."""

    return os.environ.get("CODESTRATA_CLI_UPDATE_CHECK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def maybe_notify_update(*, quiet: bool = False, json_output: bool = False) -> None:
    """Privacy-respecting optional PyPI version tip (explicit opt-in only).

    No background services. No telemetry. Failures are silent.
    """

    if not update_check_enabled():
        return
    if is_machine_mode(quiet=quiet, json_output=json_output):
        return
    try:
        from codestrata.telemetry.service import get_telemetry_service

        get_telemetry_service().record_version_check()
    except Exception:  # noqa: BLE001
        pass
    try:
        import json
        import urllib.request

        current = get_package_version()
        request = urllib.request.Request(
            "https://pypi.org/pypi/codestrata/json",
            headers={"Accept": "application/json", "User-Agent": "codestrata-cli"},
        )
        with urllib.request.urlopen(request, timeout=2.0) as response:  # noqa: S310
            payload = json.load(response)
        latest = str(payload.get("info", {}).get("version") or "")
        if latest and latest != current:
            tip(
                f"A newer Community release may be available ({latest}; "
                f"you have {current}). Update with your package manager — "
                "CodeStrata never auto-updates."
            )
    except Exception:  # noqa: BLE001 - never break the CLI for update tips
        return


__all__ = [
    "DOCS_CLI",
    "DOCS_CURSOR",
    "DOCS_GETTING_STARTED",
    "DOCS_HOME",
    "DOCS_TROUBLESHOOTING",
    "DOCS_VSCODE",
    "GITHUB_ISSUES",
    "MessageKind",
    "WEBSITE",
    "cli_state_path",
    "color_enabled",
    "docs_footer",
    "emit",
    "error",
    "format_actionable_error",
    "format_banner",
    "format_onboarding_message",
    "format_path_link",
    "format_url",
    "info",
    "is_machine_mode",
    "mark_onboarding_completed",
    "maybe_notify_update",
    "maybe_print_banner",
    "maybe_print_onboarding",
    "onboarding_completed",
    "read_cli_state",
    "success",
    "tip",
    "update_check_enabled",
    "warning",
    "which_or_none",
    "write_cli_state",
]
