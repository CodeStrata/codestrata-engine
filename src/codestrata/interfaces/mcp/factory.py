"""Composition helpers for the CodeStrata FastMCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from codestrata.application.agents import AgentOrchestrator, create_agent_orchestrator
from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings, load_settings
from codestrata.infrastructure.knowledge_store.factory import (
    create_knowledge_query_service,
    create_knowledge_store,
)
from codestrata.interfaces.mcp.context import RepositoryIntelligenceContext
from codestrata.interfaces.mcp.server import build_mcp_server


def create_mcp_server(
    *,
    query_service: KnowledgeQueryService | None = None,
    assessment_service: AssessmentApplicationService | None = None,
    settings: CodestrataSettings | None = None,
    config_path: Path | None = None,
    knowledge_store: KnowledgeStore | None = None,
    agent_orchestrator: AgentOrchestrator | None = None,
    incremental_planning_service: object | None = None,
    incremental_execution_service: object | None = None,
    incremental_inspection_service: object | None = None,
    enterprise_knowledge_service: object | None = None,
    enterprise_query_service: object | None = None,
    rule_analysis_service: object | None = None,
    repository_intelligence: RepositoryIntelligenceContext | None = None,
    retriever: Any | None = None,
    answer_engine: Any | None = None,
    answer_provider: Any | None = None,
    embedding_provider: Any | None = None,
    vector_store: Any | None = None,
) -> FastMCP:
    """Create a CodeStrata FastMCP server with injectable application services.

    Importing this module has no side effects. Platform RAG/KG services are only
    constructed when injected or when Platform MCP entry points register them.
    """

    del retriever, answer_engine, answer_provider, embedding_provider, vector_store

    resolved_settings = settings
    if resolved_settings is None and config_path is not None:
        resolved_settings = load_settings(config_path)

    queries = query_service
    if queries is None:
        if knowledge_store is not None:
            queries = KnowledgeQueryService(knowledge_store)
        else:
            queries = create_knowledge_query_service(settings=resolved_settings)

    assess = assessment_service or AssessmentApplicationService()
    orchestrator = agent_orchestrator
    if orchestrator is None:
        orchestrator = create_agent_orchestrator(
            query_service=queries,
            assessment_service=assess,
            settings=resolved_settings,
        )

    operations = incremental_execution_service
    inspection = incremental_inspection_service
    if operations is None and resolved_settings is not None:
        from codestrata.application.incremental.factory import (
            AssessmentApplicationServiceRunner,
            create_incremental_operations_service,
            create_incremental_planning_service,
        )
        from codestrata.application.incremental.inspection import IncrementalInspectionService
        from codestrata.application.incremental.provenance import (
            FileIncrementalExecutionRecordStore,
        )

        planning = incremental_planning_service or create_incremental_planning_service(
            query_service=queries,
            settings=resolved_settings,
        )
        runner = AssessmentApplicationServiceRunner(
            assess,
            knowledge_store=knowledge_store,
            config_path=config_path or Path("codestrata.toml"),
        )
        operations = create_incremental_operations_service(
            assessment_runner=runner,
            query_service=queries,
            planning_service=planning,  # type: ignore[arg-type]
            settings=resolved_settings,
        )
        if inspection is None:
            store = FileIncrementalExecutionRecordStore(
                Path(resolved_settings.knowledge.directory) / "incremental_executions"
            )
            inspection = IncrementalInspectionService(store)

    # Community MCP never constructs Platform KG services.
    # Injected services (tests / Platform hosts) are passed through unchanged.
    enterprise_knowledge = enterprise_knowledge_service
    enterprise_queries = enterprise_query_service
    if resolved_settings is not None and not resolved_settings.enterprise.enabled:
        if enterprise_knowledge_service is None:
            enterprise_knowledge = None
        if enterprise_query_service is None:
            enterprise_queries = None

    rules_service = rule_analysis_service
    if rules_service is None:
        from codestrata.application.rules.factory import create_rule_analysis_service

        rules_service = create_rule_analysis_service(settings=resolved_settings)

    ri_context = repository_intelligence
    if ri_context is None:
        mcp_settings = resolved_settings.mcp if resolved_settings else None
        from codestrata.config import McpSettings

        ri_context = RepositoryIntelligenceContext(
            queries=queries,
            settings=resolved_settings,
            mcp=mcp_settings or McpSettings(),
        )

    return build_mcp_server(
        queries=queries,
        assessment_service=assess,
        settings=resolved_settings,
        agent_orchestrator=orchestrator,
        incremental_operations=operations,
        incremental_inspection=inspection,
        enterprise_knowledge_service=enterprise_knowledge,
        enterprise_query_service=enterprise_queries,
        rule_analysis_service=rules_service,
        repository_intelligence=ri_context,
    )


def open_default_knowledge_store(settings: CodestrataSettings) -> KnowledgeStore:
    """Open the configured SQLite knowledge store for MCP composition."""

    store = create_knowledge_store(settings=settings)
    store.open()
    return cast(KnowledgeStore, store)
