"""CLI for anonymous, opt-in Community telemetry."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from codestrata.telemetry.constants import EventName
from codestrata.telemetry.service import get_telemetry_service

telemetry_app = typer.Typer(
    name="telemetry",
    help=(
        "Anonymous Community telemetry (disabled by default; explicit opt-in).\n\n"
        "Examples:\n"
        "  codestrata telemetry status\n"
        "  codestrata telemetry enable\n"
        "  codestrata telemetry disable\n"
        "  codestrata telemetry reset\n"
        "  codestrata telemetry show\n\n"
        "Never collects source code, repository names, findings, prompts, or "
        "credentials. See PRIVACY.md and https://docs.codestrata.ai/security/privacy"
    ),
    no_args_is_help=True,
)


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@telemetry_app.command("status")
def telemetry_status() -> None:
    """Show whether telemetry is enabled and local identity status."""

    _echo_json(get_telemetry_service().status())


@telemetry_app.command("enable")
def telemetry_enable() -> None:
    """Explicitly enable anonymous telemetry."""

    status = get_telemetry_service().enable()
    typer.echo("Anonymous telemetry enabled.")
    _echo_json(status)


@telemetry_app.command("disable")
def telemetry_disable() -> None:
    """Disable anonymous telemetry."""

    status = get_telemetry_service().disable()
    typer.echo("Anonymous telemetry disabled.")
    _echo_json(status)


@telemetry_app.command("reset")
def telemetry_reset() -> None:
    """Reset installation id, preferences, and local queue (asks again later)."""

    status = get_telemetry_service().reset()
    typer.echo("Telemetry identity and preferences reset. Telemetry is disabled.")
    _echo_json(status)


@telemetry_app.command("show")
def telemetry_show(
    event: Annotated[
        str,
        typer.Option(
            "--event",
            help="Event name to preview (default: assessment_completed).",
        ),
    ] = EventName.ASSESSMENT_COMPLETED.value,
) -> None:
    """Display the exact payload shape that would be sent (does not transmit)."""

    try:
        payload = get_telemetry_service().show_sample_payload(event=event)
    except ValueError as error:
        typer.echo(f"Invalid event: {error}", err=True)
        raise typer.Exit(code=2) from error
    _echo_json(payload)


def register_telemetry_command(app: typer.Typer) -> None:
    """Register the ``telemetry`` command group."""

    app.add_typer(telemetry_app, name="telemetry", rich_help_panel="Configuration")
