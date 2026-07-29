"""Finding MCP tools (Phase 3 stable findings only)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import FindingNotFoundError, KnowledgeQueryService
from codestrata.interfaces.mcp.mapping import bounded_list, to_mcp_dict
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import (
    FINDINGS_DEFAULT,
    FINDINGS_MAX,
    clamp_tool_limit,
    run_bounded,
)


def register_finding_tools(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.tool(name="list_findings", structured_output=True)
    def list_findings(
        run_id: str,
        severity: str | None = None,
        category: str | None = None,
        limit: int = FINDINGS_DEFAULT,
    ) -> dict[str, Any]:
        """List Phase 3 findings for an assessment run.

        Scope: Community Engine (local knowledge store). Deterministic; no AI.
        """

        def _run() -> dict[str, Any]:
            capped = clamp_tool_limit(
                limit,
                default=FINDINGS_DEFAULT,
                maximum=FINDINGS_MAX,
                label="findings",
            )
            severity_filter = optional_filter(severity, label="severity")
            category_filter = optional_filter(category, label="category")
            findings = queries.get_findings(require_nonblank(run_id, label="run_id"))
            filtered = [
                item
                for item in findings
                if (severity_filter is None or item.severity.lower() == severity_filter.lower())
                and (
                    category_filter is None
                    or item.category.lower() == category_filter.lower()
                )
            ]
            truncated = len(filtered) > capped
            return bounded_list(filtered[:capped], limit=capped, truncated=truncated)

        return run_bounded("list_findings", _run)

    @server.tool(name="get_finding", structured_output=True)
    def get_finding(run_id: str, finding_id: str) -> dict[str, Any]:
        """Get one Phase 3 finding by stable ID."""

        def _run() -> dict[str, Any]:
            findings = queries.get_findings(require_nonblank(run_id, label="run_id"))
            wanted = require_nonblank(finding_id, label="finding_id")
            for item in findings:
                if item.finding_id == wanted:
                    return to_mcp_dict(item)
            raise FindingNotFoundError(f"Finding not found: {wanted}")

        return run_bounded("get_finding", _run)

    @server.tool(name="explain_finding", structured_output=True)
    def explain_finding(run_id: str, finding_id: str) -> dict[str, Any]:
        """Explain a finding using persisted evidence and related recommendations."""

        def _run() -> dict[str, Any]:
            return to_mcp_dict(
                queries.explain_finding(
                    require_nonblank(run_id, label="run_id"),
                    require_nonblank(finding_id, label="finding_id"),
                )
            )

        return run_bounded("explain_finding", _run)
