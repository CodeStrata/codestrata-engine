"""High-value MCP resources backed by KnowledgeQueryService."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.interfaces.mcp.errors import call_tool
from codestrata.interfaces.mcp.mapping import to_mcp_payload


def register_resources(
    server: FastMCP,
    queries: KnowledgeQueryService,
) -> None:
    @server.resource("codestrata://repositories", mime_type="application/json")
    def repositories() -> str:
        """List registered repositories."""

        def _run() -> str:
            items = queries.list_repositories()
            return json.dumps(to_mcp_payload(items), indent=2, ensure_ascii=False)

        return call_tool("resource:repositories", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}",
        mime_type="application/json",
    )
    def repository(repository_id: str) -> str:
        """Get one repository summary."""

        def _run() -> str:
            item = queries.get_repository(repository_id)
            return json.dumps(to_mcp_payload(item), indent=2, ensure_ascii=False)

        return call_tool("resource:repository", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}/latest-assessment",
        mime_type="application/json",
    )
    def latest_assessment(repository_id: str) -> str:
        """Get latest completed assessment for a repository."""

        def _run() -> str:
            item = queries.get_latest_completed_run(repository_id)
            return json.dumps(to_mcp_payload(item), indent=2, ensure_ascii=False)

        return call_tool("resource:latest_assessment", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}/manifest",
        mime_type="application/json",
    )
    def repository_manifest(repository_id: str) -> str:
        """Repository summary manifest (tenant scope resolved via knowledge store)."""

        def _run() -> str:
            item = queries.get_repository(repository_id)
            payload = {
                "repository": to_mcp_payload(item),
                "latest_assessment": to_mcp_payload(
                    queries.get_latest_completed_run(repository_id)
                ),
            }
            return json.dumps(payload, indent=2, ensure_ascii=False)

        return call_tool("resource:repository_manifest", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}/assessments",
        mime_type="application/json",
    )
    def repository_assessments(repository_id: str) -> str:
        """List assessments for a repository."""

        def _run() -> str:
            items = queries.list_assessment_runs(repository_id)
            return json.dumps(to_mcp_payload(items), indent=2, ensure_ascii=False)

        return call_tool("resource:repository_assessments", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}/findings",
        mime_type="application/json",
    )
    def repository_findings(repository_id: str) -> str:
        """Findings for the latest completed assessment."""

        def _run() -> str:
            latest = queries.get_latest_completed_run(repository_id)
            if latest is None:
                return json.dumps({"findings": []}, indent=2, ensure_ascii=False)
            items = queries.get_findings(latest.run_id)
            return json.dumps(to_mcp_payload(items), indent=2, ensure_ascii=False)

        return call_tool("resource:repository_findings", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://repositories/{repository_id}/knowledge-status",
        mime_type="application/json",
    )
    def knowledge_status(repository_id: str) -> str:
        """Bounded assessment-knowledge readiness for a repository id."""

        def _run() -> str:
            latest = queries.get_latest_completed_run(repository_id)
            payload = {
                "repository_id": repository_id,
                "latest_completed_run_id": None if latest is None else latest.run_id,
                "assessment_knowledge_available": latest is not None,
                "platform_rag_note": (
                    "Repository RAG readiness is provided by Platform MCP "
                    "extensions when codestrata-platform is installed."
                ),
            }
            return json.dumps(to_mcp_payload(payload), indent=2, ensure_ascii=False)

        return call_tool("resource:knowledge_status", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://assessments/{run_id}/findings",
        mime_type="application/json",
    )
    def findings(run_id: str) -> str:
        """List Phase 3 findings for an assessment."""

        def _run() -> str:
            items = queries.get_findings(run_id)
            return json.dumps(to_mcp_payload(items), indent=2, ensure_ascii=False)

        return call_tool("resource:findings", _run)  # type: ignore[return-value]

    @server.resource(
        "codestrata://assessments/{run_id}/recommendations",
        mime_type="application/json",
    )
    def recommendations(run_id: str) -> str:
        """List Phase 3 recommendations for an assessment."""

        def _run() -> str:
            items = queries.get_recommendations(run_id)
            return json.dumps(to_mcp_payload(items), indent=2, ensure_ascii=False)

        return call_tool("resource:recommendations", _run)  # type: ignore[return-value]
