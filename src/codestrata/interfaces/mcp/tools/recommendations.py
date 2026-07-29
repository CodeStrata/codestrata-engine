"""Recommendation MCP tools (Phase 3)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import (
    KnowledgeQueryService,
    RecommendationNotFoundError,
)
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import (
    RECOMMENDATIONS_DEFAULT,
    RECOMMENDATIONS_MAX,
    clamp_tool_limit,
    run_bounded,
)


def register_recommendation_tools(
    server: FastMCP,
    queries: KnowledgeQueryService,
) -> None:
    @server.tool(name="list_recommendations", structured_output=True)
    def list_recommendations(
        run_id: str,
        priority: str | None = None,
        limit: int = RECOMMENDATIONS_DEFAULT,
    ) -> dict[str, Any]:
        """List Phase 3 recommendations for an assessment run."""

        def _run() -> dict[str, Any]:
            capped = clamp_tool_limit(
                limit,
                default=RECOMMENDATIONS_DEFAULT,
                maximum=RECOMMENDATIONS_MAX,
                label="recommendations",
            )
            priority_filter = optional_filter(priority, label="priority")
            items = queries.get_recommendations(require_nonblank(run_id, label="run_id"))
            filtered = [
                item
                for item in items
                if priority_filter is None
                or item.priority.lower() == priority_filter.lower()
            ]
            truncated = len(filtered) > capped
            return bounded_list(filtered[:capped], limit=capped, truncated=truncated)

        return run_bounded("list_recommendations", _run)

    @server.tool(name="get_recommendation", structured_output=True)
    def get_recommendation(run_id: str, recommendation_id: str) -> dict[str, Any]:
        """Get one Phase 3 recommendation by stable ID."""

        def _run() -> dict[str, Any]:
            items = queries.get_recommendations(require_nonblank(run_id, label="run_id"))
            wanted = require_nonblank(recommendation_id, label="recommendation_id")
            for item in items:
                if item.recommendation_id == wanted:
                    return to_mcp_dict(item)
            raise RecommendationNotFoundError(f"Recommendation not found: {wanted}")

        return run_bounded("get_recommendation", _run)

    @server.tool(name="explain_recommendation", structured_output=True)
    def explain_recommendation(run_id: str, recommendation_id: str) -> dict[str, Any]:
        """Explain a recommendation using related findings and components."""

        def _run() -> dict[str, Any]:
            return to_mcp_dict(
                queries.explain_recommendation(
                    require_nonblank(run_id, label="run_id"),
                    require_nonblank(recommendation_id, label="recommendation_id"),
                )
            )

        return run_bounded("explain_recommendation", _run)
