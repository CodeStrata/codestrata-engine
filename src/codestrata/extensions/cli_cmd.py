"""``codestrata extensions`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from codestrata.config.settings import load_settings
from codestrata.extensions.inventory import (
    build_extension_inventory,
    inventory_to_jsonable,
)
from codestrata.extensions.namespaces import (
    RESERVED_ASSESS_AI_PROVIDER_IDS,
    RESERVED_CLI_COMMAND_NAMES,
    RESERVED_EXTENSION_NAMESPACES,
    RESERVED_RENDERER_IDS,
)
from codestrata.extensions.version import EXTENSION_API_VERSION


def register_extensions_command(app: typer.Typer) -> None:
    """Register ``codestrata extensions``."""

    extensions_app = typer.Typer(
        name="extensions",
        help="Inspect Community Edition extension surfaces.",
        no_args_is_help=True,
    )

    @extensions_app.command("list")
    def list_command(
        config: Annotated[
            Path,
            typer.Option("--config", "-c", help="Path to codestrata.toml."),
        ] = Path("codestrata.toml"),
        as_json: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON."),
        ] = False,
    ) -> None:
        """List loaded, disabled, and problematic extensions."""

        enabled_analyzers: list[str] = []
        disabled_cli: list[str] = []
        disabled_mcp: list[str] = []
        if config.expanduser().is_file():
            try:
                settings = load_settings(config)
                enabled_analyzers = list(settings.extensions.analyzers.enabled)
                disabled_cli = list(settings.extensions.cli.disabled)
                disabled_mcp = list(settings.extensions.mcp.disabled)
            except (FileNotFoundError, ValueError, OSError):
                pass

        items = build_extension_inventory(
            enabled_analyzers=enabled_analyzers,
            disabled_cli=disabled_cli,
            disabled_mcp=disabled_mcp,
        )

        if as_json:
            payload = {
                "extension_api_version": EXTENSION_API_VERSION,
                "reserved_namespaces": list(RESERVED_EXTENSION_NAMESPACES),
                "reserved_assess_ai_providers": sorted(RESERVED_ASSESS_AI_PROVIDER_IDS),
                "reserved_renderers": sorted(RESERVED_RENDERER_IDS),
                "reserved_cli_commands": sorted(RESERVED_CLI_COMMAND_NAMES),
                "extensions": inventory_to_jsonable(items),
            }
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return

        typer.echo(f"Extension API: {EXTENSION_API_VERSION}")
        typer.echo(
            "Reserved analyzer namespaces: " + ", ".join(RESERVED_EXTENSION_NAMESPACES)
        )
        typer.echo("")
        for item in items:
            version = f" api={item.api_version}" if item.api_version else ""
            typer.echo(
                f"[{item.status}] {item.kind}/{item.extension_id}{version}: {item.detail}"
            )

    app.add_typer(extensions_app, name="extensions", rich_help_panel="Advanced")


__all__ = ["register_extensions_command"]
