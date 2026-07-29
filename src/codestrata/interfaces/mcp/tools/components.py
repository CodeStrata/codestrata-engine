"""Component and dependency MCP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import (
    COMPONENTS_DEFAULT,
    COMPONENTS_MAX,
    DEPENDENCIES_DEFAULT,
    DEPENDENCIES_MAX,
    clamp_tool_limit,
    parse_direction,
    run_bounded,
)


def register_component_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="list_components", structured_output=True)
    def list_components(
        run_id: str,
        component_type: str | None = None,
        name_contains: str | None = None,
        limit: int = COMPONENTS_DEFAULT,
    ) -> dict[str, Any]:
        """List Repository Graph components for an assessment run."""

        def _run() -> dict[str, Any]:
            capped = clamp_tool_limit(
                limit,
                default=COMPONENTS_DEFAULT,
                maximum=COMPONENTS_MAX,
                label="components",
            )
            type_filter = optional_filter(component_type, label="component_type")
            items = queries.list_components(
                require_nonblank(run_id, label="run_id"),
                node_types=None if type_filter is None else (type_filter,),
                name_contains=optional_filter(name_contains, label="name_contains"),
                limit=capped,
            )
            return bounded_list(items, limit=capped, truncated=len(items) >= capped)

        return run_bounded("list_components", _run)

    @server.tool(name="get_component", structured_output=True)
    def get_component(run_id: str, component_id: str) -> dict[str, Any]:
        """Get one Repository Graph component by ID."""

        def _run() -> dict[str, Any]:
            return to_mcp_dict(
                queries.get_component(
                    require_nonblank(run_id, label="run_id"),
                    require_nonblank(component_id, label="component_id"),
                )
            )

        return run_bounded("get_component", _run)

    @server.tool(name="get_component_dependencies", structured_output=True)
    def get_component_dependencies(
        run_id: str,
        component_id: str,
        direction: str = "outgoing",
        depth: int = 1,
        limit: int = DEPENDENCIES_DEFAULT,
    ) -> dict[str, Any]:
        """Traverse depends_on edges (depth 1–3) for a component."""

        def _run() -> dict[str, Any]:
            capped = clamp_tool_limit(
                limit,
                default=DEPENDENCIES_DEFAULT,
                maximum=DEPENDENCIES_MAX,
                label="dependencies",
            )
            result = queries.get_component_dependencies(
                require_nonblank(run_id, label="run_id"),
                require_nonblank(component_id, label="component_id"),
                direction=parse_direction(direction),
                depth=depth,
                limit=capped,
            )
            return to_mcp_dict(result)

        return run_bounded("get_component_dependencies", _run)
