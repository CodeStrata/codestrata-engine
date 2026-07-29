"""CLI adapter for the CodeStrata FastMCP server."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from codestrata import __version__ as PACKAGE_VERSION
from codestrata.config import load_settings
from codestrata.interfaces.mcp.factory import create_mcp_server
from codestrata.interfaces.mcp.mapping import to_mcp_payload
from codestrata.logging_config import configure_logging
from codestrata.security.database_url import sanitize_exception_message

mcp_app = typer.Typer(
    name="mcp",
    help=(
        "CodeStrata Model Context Protocol (MCP) server commands. "
        "Community Engine tools query local assessment knowledge; "
        "Platform extensions add repository_* and enterprise_* tools when installed. "
        "Requires [mcp].enabled=true. Not required for codestrata assess."
    ),
    no_args_is_help=True,
)

TransportOption = Literal["stdio", "http", "streamable-http", "sse"]


def _configure_stderr_logging(level: str) -> None:
    configure_logging(level=level)
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setStream(sys.stderr)


def _load_or_exit(config: Path, *, profile: str | None = None) -> Any:
    try:
        return load_settings(config, profile=profile)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(
            f"CodeStrata MCP failed to load configuration: {error}",
            file=sys.stderr,
        )
        raise typer.Exit(code=1) from error


@mcp_app.command("serve")
def serve(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Execution profile override (CLI > env > file > defaults).",
        ),
    ] = None,
    transport: Annotated[
        str | None,
        typer.Option(
            "--transport",
            help="Transport: stdio | http (streamable-http) | sse.",
        ),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="HTTP bind host (default 127.0.0.1)."),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", help="HTTP bind port (default 8765)."),
    ] = None,
    log_level: Annotated[
        str | None,
        typer.Option(
            "--log-level",
            help="Override MCP log level (default from [mcp].log_level).",
        ),
    ] = None,
) -> None:
    """Start the CodeStrata FastMCP server.

    Logs are written to stderr so the MCP protocol on stdout stays clean for
    stdio transport.
    """

    settings = _load_or_exit(config, profile=profile)
    if not settings.mcp.enabled:
        print(
            "CodeStrata MCP is disabled in configuration ([mcp].enabled=false).\n"
            "Fix: set [mcp].enabled = true in codestrata.toml, then re-run this command.\n"
            "MCP is optional and not required for codestrata assess.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    resolved_transport = (transport or settings.mcp.transport).strip().lower()
    if resolved_transport == "http":
        resolved_transport = "streamable-http"
    if resolved_transport not in {"stdio", "streamable-http", "sse"}:
        print(
            f"Unknown MCP transport: {resolved_transport!r}. "
            "Supported: stdio, http (streamable-http), sse.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    mcp_updates: dict[str, object] = {"transport": resolved_transport}
    if host is not None:
        mcp_updates["host"] = host
    if port is not None:
        mcp_updates["port"] = port
    settings = settings.model_copy(
        update={"mcp": settings.mcp.model_copy(update=mcp_updates)}
    )
    resolved_level = (log_level or settings.mcp.log_level).upper()
    _configure_stderr_logging(resolved_level)
    logger = logging.getLogger("codestrata.interfaces.mcp")
    try:
        server = create_mcp_server(settings=settings, config_path=config)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        logger.exception("mcp_server_composition_failed")
        print(
            f"CodeStrata MCP failed to start: {sanitize_exception_message(str(error))}",
            file=sys.stderr,
        )
        raise typer.Exit(code=1) from error

    logger.info(
        "Starting CodeStrata MCP server transport=%s host=%s port=%s",
        resolved_transport,
        settings.mcp.host,
        settings.mcp.port,
    )
    try:
        if resolved_transport == "stdio":
            server.run(transport="stdio")
        else:
            server.run(transport=resolved_transport)  # type: ignore[arg-type]
    except KeyboardInterrupt:
        logger.info("CodeStrata MCP server interrupted; shutting down")
        raise typer.Exit(code=0) from None


@mcp_app.command("tools")
def tools_command(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Execution profile override (CLI > env > file > defaults).",
        ),
    ] = None,
) -> None:
    """List registered MCP tool names and short descriptions.

    Community Engine tools are always listed when MCP is enabled. Platform
    `repository_*` and `enterprise_*` tools appear when Platform extensions load.
    """

    settings = _load_or_exit(config, profile=profile)
    if not settings.mcp.enabled:
        print(
            "CodeStrata MCP is disabled in configuration ([mcp].enabled=false).\n"
            "Fix: set [mcp].enabled = true in codestrata.toml, then re-run this command.\n"
            "MCP is optional and not required for codestrata assess.\n"
            "Docs: engine/docs/mcp/setup.md",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    try:
        server = create_mcp_server(settings=settings, config_path=config)
    except Exception as error:  # noqa: BLE001
        print(
            f"CodeStrata MCP failed to start: {sanitize_exception_message(str(error))}",
            file=sys.stderr,
        )
        raise typer.Exit(code=1) from error

    import asyncio

    async def _list() -> list[dict[str, str]]:
        listed = await server.list_tools()
        return [
            {"name": tool.name, "description": (tool.description or "")[:200]}
            for tool in sorted(listed, key=lambda item: item.name)
        ]

    payload = {
        "server_name": settings.mcp.server_name,
        "server_version": settings.mcp.server_version or PACKAGE_VERSION,
        "transport": settings.mcp.transport,
        "product_boundary": {
            "community_engine": (
                "Local assessment knowledge tools (list/get/explain, run_assessment, "
                "optional AI artifacts)."
            ),
            "platform_extensions": (
                "repository_* Retrieval/Answering and enterprise_* Engineering "
                "Knowledge Graph tools when Platform is installed."
            ),
            "auth_note": (
                "MCP does not use CODESTRATA_PLATFORM_API_KEY. Optional AI uses "
                "Engine AI provider credentials only."
            ),
        },
        "tools": asyncio.run(_list()),
        "aliases": {
            "repository.search": "repository_search",
            "repository.answer": "repository_answer",
            "repository.health": "repository_health",
        },
    }
    print(json.dumps(to_mcp_payload(payload), indent=2, sort_keys=True))


@mcp_app.command("health")
def health_command(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Execution profile override (CLI > env > file > defaults).",
        ),
    ] = None,
) -> None:
    """Return sanitized MCP/dependency health without starting a transport."""

    settings = _load_or_exit(config, profile=profile)
    if not settings.mcp.enabled:
        print(
            "CodeStrata MCP is disabled in configuration ([mcp].enabled=false).\n"
            "Fix: set [mcp].enabled = true in codestrata.toml, then re-run this command.\n"
            "MCP is optional and not required for codestrata assess.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    try:
        server = create_mcp_server(settings=settings, config_path=config)
    except Exception as error:  # noqa: BLE001
        print(
            f"CodeStrata MCP failed to start: {sanitize_exception_message(str(error))}",
            file=sys.stderr,
        )
        raise typer.Exit(code=1) from error

    import asyncio

    async def _health() -> Any:
        return await server.call_tool("repository_health", {})

    try:
        result = asyncio.run(_health())
    except Exception as error:  # noqa: BLE001
        print(
            f"CodeStrata MCP health failed: {sanitize_exception_message(str(error))}",
            file=sys.stderr,
        )
        raise typer.Exit(code=1) from error

    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            structured = structured["result"]
        print(json.dumps(to_mcp_payload(structured), indent=2, sort_keys=True))
    else:
        print(json.dumps(to_mcp_payload(result), indent=2, sort_keys=True))
