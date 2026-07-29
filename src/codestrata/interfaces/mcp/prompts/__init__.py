"""MCP prompts that supply deterministic CodeStrata context to client models."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.errors import call_tool
from codestrata.interfaces.mcp.mapping import to_mcp_payload
from codestrata.interfaces.mcp.security import require_nonblank


def register_prompts(server: FastMCP, queries: KnowledgeQueryService) -> None:
    @server.prompt(name="review_repository")
    def review_repository(repository_identifier: str) -> str:
        """Provide latest-assessment context for an evidence-based repository review."""

        def _run() -> str:
            identifier = require_nonblank(
                repository_identifier,
                label="repository_identifier",
            )
            repo = queries.resolve_repository(identifier)
            latest = queries.get_latest_completed_run(repo.repository_id)
            if latest is None:
                return (
                    f"No completed assessment exists for repository {repo.display_name}. "
                    "Ask the user to run run_assessment first."
                )
            findings = queries.get_findings(latest.run_id)[:20]
            recommendations = queries.get_recommendations(latest.run_id)[:20]
            context = {
                "repository": to_mcp_payload(repo),
                "assessment": to_mcp_payload(latest),
                "top_findings": to_mcp_payload(findings),
                "top_recommendations": to_mcp_payload(recommendations),
            }
            return (
                "You are reviewing a CodeStrata assessment. Use only the deterministic "
                "context below. Do not invent findings. Summarize major findings, "
                "highlight top recommendations, and cite finding/recommendation IDs.\n\n"
                f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```"
            )

        return call_tool("prompt:review_repository", _run)  # type: ignore[return-value]

    @server.prompt(name="explain_modernization_plan")
    def explain_modernization_plan(repository_identifier: str) -> str:
        """Organize persisted recommendations into a modernization discussion plan."""

        def _run() -> str:
            identifier = require_nonblank(
                repository_identifier,
                label="repository_identifier",
            )
            repo = queries.resolve_repository(identifier)
            latest = queries.get_latest_completed_run(repo.repository_id)
            if latest is None:
                return (
                    f"No completed assessment exists for repository {repo.display_name}. "
                    "Ask the user to run run_assessment first."
                )
            recommendations = queries.get_recommendations(latest.run_id)
            context = {
                "repository": to_mcp_payload(repo),
                "assessment": to_mcp_payload(latest),
                "recommendations": to_mcp_payload(recommendations),
            }
            return (
                "Create a modernization plan using only the persisted recommendations "
                "below. Preserve roadmap_phase values when present. Do not invent new "
                "findings or recommendations.\n\n"
                f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```"
            )

        return call_tool("prompt:explain_modernization_plan", _run)  # type: ignore[return-value]

    @server.prompt(name="review_snapshot_changes")
    def review_snapshot_changes(
        previous_snapshot_id: str,
        current_snapshot_id: str,
    ) -> str:
        """Summarize historical snapshot differences from persisted manifests."""

        def _run() -> str:
            comparison = queries.compare_repository_snapshots(
                require_nonblank(previous_snapshot_id, label="previous_snapshot_id"),
                require_nonblank(current_snapshot_id, label="current_snapshot_id"),
            )
            context = to_mcp_payload(comparison)
            return (
                "Summarize repository content changes between two CodeStrata snapshots. "
                "Use only the comparison JSON. Note that renames appear as delete + add. "
                "Identify areas that may need reassessment attention.\n\n"
                f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```"
            )

        return call_tool("prompt:review_snapshot_changes", _run)  # type: ignore[return-value]
