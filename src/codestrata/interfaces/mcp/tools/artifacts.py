"""Optional AI artifact MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import to_mcp_dict, to_mcp_payload
from codestrata.interfaces.mcp.models import AbsentArtifactResponse
from codestrata.interfaces.mcp.security import require_nonblank
from codestrata.interfaces.mcp.tools._common import run_bounded


def register_artifact_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="get_ai_execution", structured_output=True)
    def get_ai_execution(run_id: str) -> dict[str, Any]:
        """Return AI execution metadata when present for a run.

        Scope: Community Engine. Optional AI dependency — artifact exists only
        when the assessment ran with AI and persisted execution metadata.
        Requires Engine AI provider credentials at assess time, not Platform keys.
        """

        def _run() -> dict[str, Any]:
            payload = queries.get_ai_execution(require_nonblank(run_id, label="run_id"))
            if payload is None:
                return to_mcp_dict(
                    AbsentArtifactResponse(
                        present=False,
                        artifact="ai_execution",
                        message="AI execution artifact was not persisted for this run",
                    )
                )
            return {
                "present": True,
                "artifact": "ai_execution",
                "data": to_mcp_payload(payload),
            }

        return run_bounded("get_ai_execution", _run)

    @server.tool(name="get_ai_enrichment", structured_output=True)
    def get_ai_enrichment(run_id: str) -> dict[str, Any]:
        """Return AI enrichment narrative when present for a run.

        Scope: Community Engine. Optional AI dependency — absent when the run
        was deterministic-only or AI was skipped.
        """

        def _run() -> dict[str, Any]:
            payload = queries.get_ai_enrichment(require_nonblank(run_id, label="run_id"))
            if payload is None:
                return to_mcp_dict(
                    AbsentArtifactResponse(
                        present=False,
                        artifact="ai_enrichment",
                        message="AI enrichment artifact was not persisted for this run",
                    )
                )
            return {
                "present": True,
                "artifact": "ai_enrichment",
                "data": to_mcp_payload(payload),
            }

        return run_bounded("get_ai_enrichment", _run)
