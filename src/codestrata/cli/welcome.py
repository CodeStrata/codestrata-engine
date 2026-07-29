"""First-run welcome / branded landing command."""

from __future__ import annotations

from typing import Annotated

import typer

from codestrata.cli.landing import landing_suppressed, render_landing
from codestrata.cli.ux import (
    format_onboarding_message,
    mark_onboarding_completed,
    success,
    tip,
)


def register_welcome_command(app: typer.Typer) -> None:
    """Register ``codestrata welcome`` for the branded landing / onboarding."""

    @app.command("welcome", rich_help_panel="Primary")
    def welcome_command(
        done: Annotated[
            bool,
            typer.Option(
                "--done",
                help="Mark first-run onboarding complete and hide future tips.",
            ),
        ] = False,
        show: Annotated[
            bool,
            typer.Option(
                "--show",
                help="Reserved for compatibility; landing always renders when allowed.",
                hidden=True,
            ),
        ] = False,
    ) -> None:
        """Show the CodeStrata branded landing page (same as bare ``codestrata``).

        Disable first-run welcome line:

            codestrata welcome --done
            # or: CODESTRATA_SKIP_ONBOARDING=1
        """

        del show
        if done:
            mark_onboarding_completed()
            success("Onboarding marked complete. Welcome tips will stay hidden.")
            tip("Set CODESTRATA_SKIP_ONBOARDING=1 to skip in automation environments.")
            return

        if landing_suppressed():
            typer.echo(format_onboarding_message())
            return

        render_landing(include_first_run=True)
        try:
            from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in

            maybe_prompt_telemetry_opt_in()
        except Exception:  # noqa: BLE001
            return


__all__ = ["register_welcome_command"]
