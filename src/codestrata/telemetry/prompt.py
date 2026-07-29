"""First-run telemetry opt-in prompt (default No; ask once)."""

from __future__ import annotations

import os

import typer

from codestrata.cli.ux import is_machine_mode
from codestrata.telemetry.constants import SKIP_PROMPT_ENV
from codestrata.telemetry.service import TelemetryService, get_telemetry_service


def maybe_prompt_telemetry_opt_in(
    *,
    service: TelemetryService | None = None,
    quiet: bool = False,
    json_output: bool = False,
) -> None:
    """Explain anonymous telemetry and prompt once. Default answer is No."""

    svc = service or get_telemetry_service()
    svc.ensure_identity()
    if svc.decision_made() or svc.force_disabled_by_env():
        return
    if os.environ.get(SKIP_PROMPT_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    if is_machine_mode(quiet=quiet, json_output=json_output):
        return
    if not sys_stdin_is_tty():
        return

    typer.echo("")
    typer.echo("Anonymous telemetry (optional)")
    typer.echo("------------------------------")
    typer.echo(
        "CodeStrata can send anonymous product usage events to help improve "
        "the Community Edition."
    )
    typer.echo("")
    typer.echo("We may collect:")
    typer.echo("  • random installation id, CodeStrata version, OS, Python version")
    typer.echo("  • command name, success/failure, duration band, size band")
    typer.echo("  • language categories and enabled assessment domains")
    typer.echo("  • whether optional AI was used (not prompts or responses)")
    typer.echo("")
    typer.echo("We never collect:")
    typer.echo("  • source code, repository names/URLs, file names or paths")
    typer.echo("  • findings, recommendations, reports, prompts, AI responses")
    typer.echo("  • credentials, secrets, hostname, username, or email")
    typer.echo("")
    typer.echo("Docs: https://docs.codestrata.ai/security/privacy")
    typer.echo("Manage later: codestrata telemetry status|enable|disable|reset|show")
    typer.echo("")

    try:
        enabled = typer.confirm("Enable anonymous telemetry?", default=False)
    except (typer.Abort, EOFError, KeyboardInterrupt):
        svc.disable()
        return

    if enabled:
        svc.enable()
        typer.echo("Telemetry enabled. Thank you.")
    else:
        svc.disable()
        typer.echo("Telemetry remains disabled.")


def sys_stdin_is_tty() -> bool:
    import sys

    return bool(getattr(sys.stdin, "isatty", lambda: False)())
