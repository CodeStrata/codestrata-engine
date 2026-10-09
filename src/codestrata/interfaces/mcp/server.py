"""FastMCP server construction for CodeStrata."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from codestrata import __version__ as PACKAGE_VERSION
from codestrata.application.agents import AgentOrchestrator
from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings
from codestrata.interfaces.mcp.context import RepositoryIntelligenceContext
from codestrata.interfaces.mcp.prompts import register_prompts
from codestrata.interfaces.mcp.resources import register_resources
from codestrata.interfaces.mcp.tools import register_all_tools

CODESSTRATA_MCP_NAME = "CodeStrata"
CODESSTRATA_MCP_INSTRUCTIONS = (
    "CodeStrata MCP — Engineering Assessment knowledge for AI clients.\n\n"
    "Community Engine (local): list/get/explain assessments, findings, "
    "recommendations, components, rules, evidence, architecture helpers, "
    "and run_assessment. Optional AI artifacts via get_ai_execution / "
    "get_ai_enrichment (requires AI provider credentials in Engine config — "
    "not Platform API keys).\n\n"
    "CodeStrata Platform extensions (when installed): repository_* retrieval/"
    "answering tools and enterprise_* Engineering Knowledge Graph tools. "
    "These are not available on Community Engine alone.\n\n"
    "Prefer precise list/get/explain tools. Prefer deterministic evidence over "
    "optional AI. Source code is not retained unless explicitly configured. "
    "Agents should call application services directly rather than nesting "
    "through this MCP server when embedding CodeStrata in-process."
)


def build_mcp_server(
    *,
    queries: KnowledgeQueryService,
    assessment_service: AssessmentApplicationService,
    settings: CodestrataSettings | None = None,
    agent_orchestrator: AgentOrchestrator | None = None,
    incremental_operations: object | None = None,
    incremental_inspection: object | None = None,
    enterprise_knowledge_service: object | None = None,
    enterprise_query_service: object | None = None,
    rule_analysis_service: object | None = None,
    language_evidence_service: object | None = None,
    architecture_conclusion_service: object | None = None,
    repository_intelligence: RepositoryIntelligenceContext | None = None,
) -> FastMCP:
    """Assemble a FastMCP server with tools, resources, and prompts registered."""

    mcp_settings = settings.mcp if settings is not None else None
    host = mcp_settings.host if mcp_settings is not None else "127.0.0.1"
    port = mcp_settings.port if mcp_settings is not None else 8765
    log_level = mcp_settings.log_level if mcp_settings is not None else "INFO"
    server_name = (
        mcp_settings.server_name if mcp_settings is not None else None
    ) or CODESSTRATA_MCP_NAME

    server = FastMCP(
        name=server_name,
        instructions=CODESSTRATA_MCP_INSTRUCTIONS,
        host=host,
        port=port,
        log_level=log_level,  # type: ignore[arg-type]
    )
    evidence_service = language_evidence_service
    if evidence_service is None:
        from codestrata.application.evidence.language.factory import (
            create_language_evidence_service,
        )

        evidence_service = create_language_evidence_service(settings)

    conclusion_service = architecture_conclusion_service
    if conclusion_service is None:
        from codestrata.application.architecture.conclusions.factory import (
            create_architecture_conclusion_service,
        )

        conclusion_service = create_architecture_conclusion_service(settings)

    register_all_tools(
        server,
        queries=queries,
        assessment_service=assessment_service,
        settings=settings,
        agent_orchestrator=agent_orchestrator,
        incremental_operations=incremental_operations,
        incremental_inspection=incremental_inspection,
        enterprise_knowledge_service=enterprise_knowledge_service,
        enterprise_query_service=enterprise_query_service,
        rule_analysis_service=rule_analysis_service,
        language_evidence_service=evidence_service,
        architecture_conclusion_service=conclusion_service,
        repository_intelligence=repository_intelligence,
    )
    register_resources(server, queries)
    register_prompts(server, queries)

    version = (mcp_settings.server_version if mcp_settings is not None else None) or PACKAGE_VERSION
    transport = mcp_settings.transport if mcp_settings is not None else "stdio"
    attached = cast(Any, server)
    attached._codestrata_manifest = {
        "server_name": server_name,
        "server_version": version,
        "transport": transport,
        "package_version": PACKAGE_VERSION,
    }
    return server


CODESSTRATA_ARTIFACT_MCP_NAME = "CodeStrataEvidence"
CODESSTRATA_ARTIFACT_MCP_INSTRUCTIONS = (
    "CodeStrata MCP — Bounded local evidence queries from artifacts.\n\n"
    "Pure local, zero-database, read-only evidence interface.\n"
    "Exposes repositories, snapshots, components, findings, metrics, dependencies, "
    "changes, evidence, and lineage with pagination and explicit local root scope."
)


def build_artifact_mcp_server(
    *,
    evidence_service: Any | None = None,
    local_root: Any = ".",
    settings: CodestrataSettings | None = None,
) -> FastMCP:
    """Assemble a FastMCP server with only bounded local artifact evidence tools registered."""

    mcp_settings = settings.mcp if settings is not None else None
    host = mcp_settings.host if mcp_settings is not None else "127.0.0.1"
    port = mcp_settings.port if mcp_settings is not None else 8765
    log_level = mcp_settings.log_level if mcp_settings is not None else "INFO"
    server_name = (
        mcp_settings.server_name if mcp_settings is not None else None
    ) or CODESSTRATA_ARTIFACT_MCP_NAME

    server = FastMCP(
        name=server_name,
        instructions=CODESSTRATA_ARTIFACT_MCP_INSTRUCTIONS,
        host=host,
        port=port,
        log_level=log_level,  # type: ignore[arg-type]
    )

    max_chars = mcp_settings.max_result_characters if mcp_settings is not None else 50_000

    from codestrata.interfaces.mcp.tools.artifact_queries import (
        register_artifact_evidence_tools,
    )

    register_artifact_evidence_tools(
        server,
        service=evidence_service,
        default_root=str(local_root),
        max_character_budget=max_chars,
    )

    version = (mcp_settings.server_version if mcp_settings is not None else None) or PACKAGE_VERSION
    transport = mcp_settings.transport if mcp_settings is not None else "stdio"
    attached = cast(Any, server)
    attached._codestrata_manifest = {
        "server_name": server_name,
        "server_version": version,
        "transport": transport,
        "package_version": PACKAGE_VERSION,
    }
    return server


CODESSTRATA_EXPLANATION_MCP_NAME = "CodeStrataLocalExplanation"
CODESSTRATA_EXPLANATION_MCP_INSTRUCTIONS = (
    "CodeStrata MCP — optional local/BYO explanation.\n\n"
    "AI explanation is disabled unless enabled is true. Prompt and evidence "
    "egress is a separate flag and is not authorized by product telemetry. "
    "The tool cites permitted evidence IDs through the OpenAI adapter only. "
    "It does not execute source instructions or change assessment status or "
    "the canonical digest."
)


def build_local_explanation_mcp_server(
    *,
    explanation_path: Any | None = None,
    evidence_service: Any | None = None,
    settings: CodestrataSettings | None = None,
) -> FastMCP:
    """Assemble a FastMCP server with only the optional explanation tool."""

    mcp_settings = settings.mcp if settings is not None else None
    host = mcp_settings.host if mcp_settings is not None else "127.0.0.1"
    port = mcp_settings.port if mcp_settings is not None else 8765
    log_level = mcp_settings.log_level if mcp_settings is not None else "INFO"
    server_name = (
        mcp_settings.server_name if mcp_settings is not None else None
    ) or CODESSTRATA_EXPLANATION_MCP_NAME

    server = FastMCP(
        name=server_name,
        instructions=CODESSTRATA_EXPLANATION_MCP_INSTRUCTIONS,
        host=host,
        port=port,
        log_level=log_level,  # type: ignore[arg-type]
    )
    from codestrata.interfaces.mcp.tools.local_explanation import (
        register_local_explanation_tool,
    )

    register_local_explanation_tool(
        server,
        explanation_path=explanation_path,
        evidence_service=evidence_service,
    )
    version = (mcp_settings.server_version if mcp_settings is not None else None) or PACKAGE_VERSION
    transport = mcp_settings.transport if mcp_settings is not None else "stdio"
    attached = cast(Any, server)
    attached._codestrata_manifest = {
        "server_name": server_name,
        "server_version": version,
        "transport": transport,
        "package_version": PACKAGE_VERSION,
    }
    return server
