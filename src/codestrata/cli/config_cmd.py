"""CLI for execution profiles and configuration validation (Phase 5.20)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from codestrata.config.effective import build_effective_settings
from codestrata.config.profiles import (
    ALLOWED_PROFILES,
    PROFILE_ENV_VAR,
    ConfigurationProfileError,
    raise_on_errors,
)
from codestrata.config.settings import load_settings_resolution

config_app = typer.Typer(
    name="config",
    help=(
        "Validate and inspect CodeStrata Engine configuration.\n\n"
        "Examples:\n"
        "  codestrata config show\n"
        "  codestrata config validate\n"
        "  codestrata config profile\n\n"
        "Precedence: --profile > CODESTRATA_PROFILE > codestrata.toml > "
        "profile defaults.\n"
        "AI settings are optional for deterministic assess (--no-ai).\n"
        "Docs: https://docs.codestrata.ai/ · "
        "see docs/configuration-profiles.md in the repository."
    ),
    no_args_is_help=True,
)


def _echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@config_app.command("profile")
def profile_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Override execution profile (CLI > env > file > defaults).",
        ),
    ] = None,
) -> None:
    """Display the active execution profile and selection source."""

    try:
        settings, active, source, issues = load_settings_resolution(
            config,
            profile=profile,
            validate_profile=False,
        )
    except (FileNotFoundError, ValueError, OSError, ConfigurationProfileError) as error:
        typer.echo(f"Failed to load configuration: {error}", err=True)
        raise typer.Exit(code=1) from error

    warnings = [item.format() for item in issues if item.severity == "warning"]
    payload = {
        "profile": active,
        "source": source,
        "allowed_profiles": sorted(ALLOWED_PROFILES),
        "selection_env": PROFILE_ENV_VAR,
        "enterprise_enabled": settings.enterprise.enabled,
        "ai": {
            "provider": settings.ai.provider,
            "embedding_provider": settings.ai.embedding_provider,
            "answer_provider": settings.ai.answer_provider,
        },
        "warnings": warnings,
    }
    _echo_json(payload)


@config_app.command("effective")
def effective_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Override execution profile (CLI > env > file > defaults).",
        ),
    ] = None,
) -> None:
    """Show effective non-secret settings after profile resolution."""

    try:
        settings, active, source, _issues = load_settings_resolution(
            config,
            profile=profile,
            validate_profile=False,
        )
    except (FileNotFoundError, ValueError, OSError, ConfigurationProfileError) as error:
        typer.echo(f"Failed to load configuration: {error}", err=True)
        raise typer.Exit(code=1) from error

    payload = build_effective_settings(
        settings,
        profile=active,
        profile_source=source,  # type: ignore[arg-type]
    )
    _echo_json(payload)


@config_app.command("validate")
def validate_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Override execution profile (CLI > env > file > defaults).",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Also require provider credentials to be present (never printed).",
        ),
    ] = False,
) -> None:
    """Validate configuration for Community assess and execution profiles.

    Distinguishes required settings from optional / AI-only / Platform-only
    configuration where validation errors include categorized Fix guidance.
    """

    try:
        settings, active, source, issues = load_settings_resolution(
            config,
            profile=profile,
            validate_profile=False,
            strict=strict,
        )
        raise_on_errors(issues)
    except (FileNotFoundError, ValueError, OSError, ConfigurationProfileError) as error:
        typer.echo(f"Configuration validation failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    warnings = [item.format() for item in issues if item.severity == "warning"]
    payload = {
        "ok": True,
        "profile": active,
        "source": source,
        "strict": strict,
        "enterprise_enabled": settings.enterprise.enabled,
        "warnings": warnings,
        "message": "Configuration is valid for the active execution profile.",
    }
    _echo_json(payload)


@config_app.command("show")
def show_cmd(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Override execution profile (CLI > env > file > defaults).",
        ),
    ] = None,
    human: Annotated[
        bool,
        typer.Option(
            "--human",
            help="Print a short human summary before the JSON payload.",
        ),
    ] = False,
) -> None:
    """Show current effective settings (non-secret) and config path.

    Alias for ``config effective`` with an optional human preamble.
    """

    if human:
        try:
            settings, active, source, issues = load_settings_resolution(
                config,
                profile=profile,
                validate_profile=False,
            )
        except (FileNotFoundError, ValueError, OSError, ConfigurationProfileError) as error:
            typer.echo(f"Error: Failed to load configuration: {error}", err=True)
            raise typer.Exit(code=1) from error
        warnings = [item.format() for item in issues if item.severity == "warning"]
        typer.echo(f"Config file: {config.expanduser().resolve()}")
        typer.echo(f"Active profile: {active} (source={source})")
        typer.echo(f"Defaults applied via profile: {active}")
        if warnings:
            typer.echo("Validation warnings:")
            for warning in warnings:
                typer.echo(f"  - {warning}")
        else:
            typer.echo("Validation issues: none")
        typer.echo(f"Repository path: {settings.repository.path or '(unset)'}")
        typer.echo(f"Repository URL: {settings.repository.url or '(unset)'}")
        typer.echo("---")
    effective_cmd(config=config, profile=profile)


__all__ = ["config_app"]
