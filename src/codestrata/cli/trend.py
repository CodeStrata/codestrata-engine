"""Fixed-five committed-state trend journey. No configurable commit count."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.assessment.service import default_assessment_clock
from codestrata.application.incremental.trend_bundle import resolve_series_directory
from codestrata.application.incremental.trend_series import (
    DEFAULT_TREND_OUTPUT_DIRECTORY,
    run_trend_series,
)
from codestrata.cli.community_contract import EXIT_FAILURE, EXIT_USAGE
from codestrata.config import CodestrataSettings, load_settings


def register_trend_command(app: typer.Typer) -> None:
    """Register ``codestrata trend``."""

    @app.command("trend", rich_help_panel="Primary")
    def trend_command(
        repo: Annotated[
            Path,
            typer.Option(
                "--repo",
                "-r",
                help="Local repository path. Trend uses committed HEAD, not dirty files.",
            ),
        ],
        output: Annotated[
            Path,
            typer.Option(
                "--output",
                "-o",
                help=(
                    "Artifact root or series directory "
                    "(default: .codestrata-artifacts). "
                    "Durable layout: <root>/trends/<repository-id>/<series-id>/."
                ),
            ),
        ] = DEFAULT_TREND_OUTPUT_DIRECTORY,
        config: Annotated[
            Path,
            typer.Option("--config", "-c", help="Optional codestrata.toml used to pin settings."),
        ] = Path("codestrata.toml"),
    ) -> None:
        """Assess committed HEAD plus four first-parent predecessors.

        The working tree is never checked out or rewritten. Uncommitted changes
        are excluded. Failed or missing slots stay visible.
        """

        if not repo.exists():
            typer.echo(f"repository not found: {repo}", err=True)
            raise typer.Exit(code=EXIT_USAGE)
        settings = _load_trend_settings(config, repo)
        series_directory = resolve_series_directory(output, repo)
        try:
            result = run_trend_series(
                repo,
                series_directory,
                evaluation_time=_evaluation_time(),
                settings=settings,
            )
        except Exception as error:  # noqa: BLE001 - command boundary
            typer.echo(f"trend failed: {error}", err=True)
            raise typer.Exit(code=EXIT_FAILURE) from error
        if result.dirty_notice:
            typer.echo(result.dirty_notice)
        typer.echo(json.dumps(result.to_json(), indent=2))
        if not result.worktree_unchanged:
            typer.echo("trend left the working tree changed", err=True)
            raise typer.Exit(code=EXIT_FAILURE)
        head = next((slot for slot in result.slots if slot.slot == 5), None)
        if head is None or head.status == "failed":
            raise typer.Exit(code=EXIT_FAILURE)


def _load_trend_settings(config_path: Path, repo: Path) -> CodestrataSettings:
    if config_path.is_file():
        loaded = load_settings(config_path)
        repository = loaded.repository.model_copy(update={"path": str(repo)})
        return loaded.model_copy(update={"repository": repository})
    return CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repo)},
            "knowledge": {"enabled": False},
            "static_analysis": {"enabled": False},
        }
    )


def _evaluation_time() -> datetime:
    clock = default_assessment_clock()
    if clock.tzinfo is None:
        return clock.replace(tzinfo=UTC)
    return clock.astimezone(UTC)


__all__ = ["register_trend_command"]
