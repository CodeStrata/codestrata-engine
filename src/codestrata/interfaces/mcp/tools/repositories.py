"""Repository MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict
from codestrata.interfaces.mcp.tools._common import require_nonblank, run_bounded


def register_repository_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="list_repositories", structured_output=True)
    def list_repositories(limit: int = 50) -> dict[str, Any]:
        """List registered repositories with latest assessment pointers.

        Scope: Community Engine (local knowledge store).
        """

        def _run() -> dict[str, Any]:
            items = queries.list_repositories(limit=limit)
            # Query service already clamps; mark truncated when hitting request limit.
            truncated = len(items) >= limit
            return bounded_list(items, limit=limit, truncated=truncated)

        return run_bounded("list_repositories", _run)

    @server.tool(name="get_repository", structured_output=True)
    def get_repository(repository_identifier: str) -> dict[str, Any]:
        """Get a repository by ID, canonical key, or GitHub URL (not local paths).

        Scope: Community Engine (local knowledge store).
        """

        def _run() -> dict[str, Any]:
            identifier = require_nonblank(
                repository_identifier,
                label="repository_identifier",
            )
            return to_mcp_dict(queries.resolve_repository(identifier))

        return run_bounded("get_repository", _run)
