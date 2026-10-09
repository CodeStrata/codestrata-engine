"""G40-D004: the CLI MCP server is the bounded artifact server."""

from __future__ import annotations

import asyncio

from codestrata.cli.mcp import build_cli_mcp_server


def test_cli_mcp_server_does_not_register_run_assessment() -> None:
    server = build_cli_mcp_server(settings=None, config_path=None)

    async def _names() -> set[str]:
        listed = await server.list_tools()
        return {tool.name for tool in listed}

    names = asyncio.run(_names())
    assert "run_assessment" not in names
    assert "list_findings" in names
