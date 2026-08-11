"""CLI for anonymous Community telemetry preference and status commands.

``codestrata telemetry status`` reports whether anonymous telemetry is Enabled,
Disabled, or Not configured. ``enable`` / ``disable`` persist an explicit local
preference under CODESTRATA_HOME. Never collects source code or repository identity.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from codestrata.telemetry.constants import EventName
from codestrata.telemetry.persisted_consent import (
    TelemetryPreferenceState,
    persist_preference,
    preference_state,
)
from codestrata.telemetry.preview_builder import build_privacy_first_telemetry_preview
from codestrata.telemetry.preview_formatting import format_privacy_first_telemetry_preview
from codestrata.telemetry.preview_policy import PreviewPolicyError
from codestrata.telemetry.service import get_legacy_telemetry_service

telemetry_app = typer.Typer(
    name="telemetry",
    help=(
        "Anonymous Community telemetry (disabled by default).\n\n"
        "Examples:\n"
        "  codestrata telemetry status\n"
        "  codestrata telemetry enable\n"
        "  codestrata telemetry disable\n"
        "  codestrata telemetry preview\n\n"
        "Preference is stored locally under CODESTRATA_HOME. Never collects "
        "source code, repository names, findings, prompts, or credentials. "
        "See PRIVACY.md and https://docs.codestrata.ai/security/privacy"
    ),
    no_args_is_help=True,
)


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _format_preference_status(state: TelemetryPreferenceState) -> str:
    if state is TelemetryPreferenceState.ENABLED:
        label = "Enabled"
    elif state is TelemetryPreferenceState.DISABLED:
        label = "Disabled"
    else:
        label = "Not configured"
    return "\n".join(
        [
            "Anonymous Community telemetry",
            "-----------------------------",
            f"Preference: {label}",
            "Default: Disabled (no silent telemetry)",
            "Scope: Local preference under CODESTRATA_HOME",
            (
                "Contents: Anonymous usage and assessment metadata only — "
                "no source code, repository names, file paths, findings, "
                "or credentials."
            ),
            "Change later: `codestrata telemetry enable|disable`",
            "",
        ]
    )


@telemetry_app.command("status")
def telemetry_status() -> None:
    """Show local telemetry preference (Enabled / Disabled / Not configured)."""

    typer.echo(_format_preference_status(preference_state()), nl=False)


@telemetry_app.command("preview")
def telemetry_preview(
    event: Annotated[
        str | None,
        typer.Option(
            "--event",
            help=(
                "Runtime event to preview "
                "(application_started, application_completed, feature_invoked, "
                "feature_completed, operation_failed). Default: feature_invoked."
            ),
        ),
    ] = None,
) -> None:
    """Show an illustrative privacy-safe telemetry event (local only)."""

    try:
        preview = build_privacy_first_telemetry_preview(event_name=event)
    except PreviewPolicyError as error:
        typer.echo(f"Invalid preview: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(format_privacy_first_telemetry_preview(preview), nl=False)


@telemetry_app.command("enable")
def telemetry_enable() -> None:
    """Persist explicit opt-in for anonymous Community telemetry."""

    persist_preference(True)
    typer.echo("Anonymous telemetry preference: Enabled.")
    typer.echo(
        "No source code, repository names, file paths, findings, or credentials "
        "are sent."
    )


@telemetry_app.command("disable")
def telemetry_disable() -> None:
    """Persist explicit opt-out for anonymous Community telemetry."""

    persist_preference(False)
    typer.echo("Anonymous telemetry preference: Disabled.")


@telemetry_app.command("reset")
def telemetry_reset() -> None:
    """Reset installation id, preferences, and local queue (legacy only)."""

    status = get_legacy_telemetry_service().reset()
    typer.echo(
        "Telemetry identity and preferences reset. "
        "Preference is Not configured (telemetry remains disabled)."
    )
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
    """Display a sample legacy payload shape (does not transmit via product runtime)."""

    try:
        payload = get_legacy_telemetry_service().show_sample_payload(event=event)
    except ValueError as error:
        typer.echo(f"Invalid event: {error}", err=True)
        raise typer.Exit(code=2) from error
    _echo_json(payload)


def register_telemetry_command(app: typer.Typer) -> None:
    """Register the ``telemetry`` command group."""

    app.add_typer(telemetry_app, name="telemetry", rich_help_panel="Configuration")
