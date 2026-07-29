"""Snapshot MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import resolve_repository_id, run_bounded


def register_snapshot_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="list_snapshots", structured_output=True)
    def list_snapshots(
        repository_identifier: str,
        branch: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List repository content snapshots, newest first."""

        def _run() -> dict[str, Any]:
            repository_id = resolve_repository_id(queries, repository_identifier)
            items = queries.list_repository_snapshots(
                repository_id,
                branch=optional_filter(branch, label="branch"),
                limit=limit,
            )
            return bounded_list(items, limit=limit, truncated=len(items) >= limit)

        return run_bounded("list_snapshots", _run)

    @server.tool(name="get_snapshot", structured_output=True)
    def get_snapshot(snapshot_id: str) -> dict[str, Any]:
        """Get one repository snapshot summary."""

        def _run() -> dict[str, Any]:
            return to_mcp_dict(
                queries.get_repository_snapshot(
                    require_nonblank(snapshot_id, label="snapshot_id")
                )
            )

        return run_bounded("get_snapshot", _run)

    @server.tool(name="compare_snapshots", structured_output=True)
    def compare_snapshots(
        previous_snapshot_id: str,
        current_snapshot_id: str,
    ) -> dict[str, Any]:
        """Compare two persisted manifests (historical; no live tree reads)."""

        def _run() -> dict[str, Any]:
            comparison = queries.compare_repository_snapshots(
                require_nonblank(previous_snapshot_id, label="previous_snapshot_id"),
                require_nonblank(current_snapshot_id, label="current_snapshot_id"),
            )
            return to_mcp_dict(comparison)

        return run_bounded("compare_snapshots", _run)
