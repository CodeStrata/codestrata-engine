"""Register all CodeStrata MCP tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codestrata.application.agents import AgentOrchestrator
from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings
from codestrata.extensions import load_mcp_extensions
from codestrata.interfaces.mcp.context import RepositoryIntelligenceContext
from codestrata.interfaces.mcp.tools.agents import register_agent_tools
from codestrata.interfaces.mcp.tools.architecture_assessment import (
    register_architecture_assessment_tools,
)
from codestrata.interfaces.mcp.tools.architecture_conclusions import (
    register_architecture_conclusion_tools,
)
from codestrata.interfaces.mcp.tools.architecture_report import (
    register_architecture_report_tools,
)
from codestrata.interfaces.mcp.tools.assessment_report import (
    register_assessment_report_tools,
)
from codestrata.interfaces.mcp.tools.artifacts import register_artifact_tools
from codestrata.interfaces.mcp.tools.assessments import register_assessment_tools
from codestrata.interfaces.mcp.tools.components import register_component_tools
from codestrata.interfaces.mcp.tools.evidence import register_evidence_tools
from codestrata.interfaces.mcp.tools.execution import register_execution_tools
from codestrata.interfaces.mcp.tools.findings import register_finding_tools
from codestrata.interfaces.mcp.tools.incremental import register_incremental_tools
from codestrata.interfaces.mcp.tools.recommendations import register_recommendation_tools
from codestrata.interfaces.mcp.tools.repositories import register_repository_tools
from codestrata.interfaces.mcp.tools.rules import register_rules_tools
from codestrata.interfaces.mcp.tools.snapshots import register_snapshot_tools


def register_all_tools(
    server: FastMCP,
    *,
    queries: KnowledgeQueryService,
    assessment_service: AssessmentApplicationService,
    settings: CodestrataSettings | None,
    agent_orchestrator: AgentOrchestrator | None = None,
    incremental_operations: object | None = None,
    incremental_inspection: object | None = None,
    enterprise_knowledge_service: object | None = None,
    enterprise_query_service: object | None = None,
    rule_analysis_service: object | None = None,
    language_evidence_service: object | None = None,
    architecture_conclusion_service: object | None = None,
    repository_intelligence: RepositoryIntelligenceContext | None = None,
) -> None:
    register_repository_tools(server, queries)
    register_assessment_tools(server, queries)
    register_snapshot_tools(server, queries)
    register_finding_tools(server, queries)
    register_recommendation_tools(server, queries)
    register_component_tools(server, queries)
    register_artifact_tools(server, queries)
    register_execution_tools(
        server,
        queries=queries,
        assessment_service=assessment_service,
        settings=settings,
    )
    if agent_orchestrator is not None:
        register_agent_tools(
            server,
            orchestrator=agent_orchestrator,
            queries=queries,
            assessment_service=assessment_service,
            settings=settings,
        )
    register_incremental_tools(
        server,
        operations=incremental_operations,  # type: ignore[arg-type]
        inspection=incremental_inspection,  # type: ignore[arg-type]
    )
    register_rules_tools(
        server,
        rule_analysis_service=rule_analysis_service,  # type: ignore[arg-type]
    )
    register_evidence_tools(
        server,
        language_evidence_service=language_evidence_service,
    )
    register_architecture_conclusion_tools(
        server,
        architecture_conclusion_service=architecture_conclusion_service,
    )
    register_architecture_assessment_tools(server)
    register_architecture_report_tools(server)
    register_assessment_report_tools(server)

    for register in load_mcp_extensions():
        register(
            server,
            queries=queries,
            settings=settings,
            enterprise_knowledge_service=enterprise_knowledge_service,
            enterprise_query_service=enterprise_query_service,
            repository_intelligence=repository_intelligence,
        )
