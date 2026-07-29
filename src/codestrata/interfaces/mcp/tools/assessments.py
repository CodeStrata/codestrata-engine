"""Assessment history MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict, to_mcp_payload
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import (
    parse_run_status,
    resolve_repository_id,
    run_bounded,
)


def register_assessment_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="list_assessments", structured_output=True)
    def list_assessments(
        repository_identifier: str,
        limit: int = 20,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List assessment runs for a repository, newest first.

        Scope: Community Engine (local knowledge store).
        """

        def _run() -> dict[str, Any]:
            repository_id = resolve_repository_id(queries, repository_identifier)
            items = queries.list_assessment_runs(
                repository_id,
                limit=limit,
                status=parse_run_status(status),
            )
            return bounded_list(items, limit=limit, truncated=len(items) >= limit)

        return run_bounded("list_assessments", _run)

    @server.tool(name="get_assessment", structured_output=True)
    def get_assessment(run_id: str) -> dict[str, Any]:
        """Get one assessment run by ID.

        Scope: Community Engine (local knowledge store).
        """

        def _run() -> dict[str, Any]:
            return to_mcp_dict(
                queries.get_assessment_run(require_nonblank(run_id, label="run_id"))
            )

        return run_bounded("get_assessment", _run)

    @server.tool(name="get_latest_assessment", structured_output=True)
    def get_latest_assessment(
        repository_identifier: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Get the latest completed assessment for a repository.

        Scope: Community Engine (local knowledge store).
        """

        def _run() -> dict[str, Any]:
            repository_id = resolve_repository_id(queries, repository_identifier)
            latest = queries.get_latest_completed_run(
                repository_id,
                branch=optional_filter(branch, label="branch"),
            )
            if latest is None:
                return {
                    "present": False,
                    "assessment": None,
                    "message": "No completed assessment found",
                }
            return {"present": True, "assessment": to_mcp_payload(latest)}

        return run_bounded("get_latest_assessment", _run)
