"""CLI for anonymous Community telemetry preference and status commands.

``codestrata telemetry status`` reports consent-v2 preference state.
``enable`` persists V2_YES (usage + privacy-safe assessment insights).
``disable`` persists DISABLED. Preference lives under CODESTRATA_HOME.
``decline-upgrade`` retains V1_YES and stops v2-upgrade nagging (Slice 20.10).
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from codestrata.telemetry.constants import EventName
from codestrata.telemetry.persisted_consent import (
    consent_status_payload,
    decline_v2_upgrade,
    format_consent_status,
    persist_disabled,
    persist_v2_yes,
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
        "  codestrata telemetry status --json\n"
        "  codestrata telemetry enable\n"
        "  codestrata telemetry disable\n"
        "  codestrata telemetry decline-upgrade\n"
        "  codestrata telemetry preview\n\n"
        "Preference is stored locally under CODESTRATA_HOME. Never collects "
        "source code, repository names, findings, prompts, or credentials. "
        "Enable opts into privacy-safe usage and assessment insights (v2). "
        "This consent does not publish reports. "
        "See PRIVACY.md and https://docs.codestrata.ai/security/privacy"
    ),
    no_args_is_help=True,
)


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@telemetry_app.command("status")
def telemetry_status(
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit machine-stable consent-v2 status JSON (no identifying fields).",
        ),
    ] = False,
) -> None:
    """Show local telemetry preference (undecided / v1 / v2 / disabled)."""

    if as_json:
        _echo_json(consent_status_payload())
        return
    typer.echo(format_consent_status(), nl=False)


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
    """Persist explicit v2 opt-in (usage + privacy-safe assessment insights)."""

    persist_v2_yes()
    typer.echo("Anonymous telemetry preference: Enabled (v2).")
    typer.echo(
        "Includes privacy-safe assessment insights. "
        "No source code, repository names, file paths, findings, or credentials "
        "are sent. This does not publish reports."
    )


@telemetry_app.command("disable")
def telemetry_disable() -> None:
    """Persist explicit opt-out for anonymous Community telemetry."""

    persist_disabled()
    typer.echo("Anonymous telemetry preference: Disabled.")


@telemetry_app.command("decline-upgrade")
def telemetry_decline_upgrade() -> None:
    """Keep legacy v1 lifecycle consent; decline broader v2 assessment insights."""

    state = decline_v2_upgrade()
    typer.echo(
        "Anonymous telemetry preference: Enabled (legacy v1 — lifecycle only)."
    )
    typer.echo(
        "Assessment insights remain off. "
        f"State: {state.value}."
    )


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
