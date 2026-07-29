"""High-level Agent Framework MCP tools (call AgentOrchestrator only)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.agents import (
    AgentOrchestrator,
    AssessmentValidationRequest,
    ModernizationReviewRequest,
    RepositoryAssessmentRequest,
    RepositoryReviewRequest,
    SnapshotReviewRequest,
    create_agent_orchestrator,
    resolve_agent_policy,
)
from codestrata.application.agents.policies import MAX_DEPENDENCY_DEPTH
from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings
from codestrata.interfaces.mcp.agent_mapping import (
    map_agent_assessment_for_mcp,
    map_agent_modernization_for_mcp,
    map_agent_review_for_mcp,
    map_agent_snapshot_for_mcp,
    map_agent_validation_for_mcp,
)
from codestrata.interfaces.mcp.tools._common import (
    COMPONENTS_MAX,
    FINDINGS_MAX,
    RECOMMENDATIONS_MAX,
    clamp_tool_limit,
    require_nonblank,
    run_bounded,
)


def register_agent_tools(
    server: FastMCP,
    *,
    orchestrator: AgentOrchestrator,
    queries: KnowledgeQueryService,
    assessment_service: AssessmentApplicationService,
    settings: CodestrataSettings | None,
) -> None:
    """Register the five high-level agent workflow tools."""

    def _scoped_orchestrator(**policy_overrides: int) -> AgentOrchestrator:
        policy = resolve_agent_policy(settings, **policy_overrides)  # type: ignore[arg-type]
        return create_agent_orchestrator(
            query_service=queries,
            assessment_service=assessment_service,
            settings=settings,
            policy=policy,
        )

    @server.tool(name="review_repository_with_agents", structured_output=True)
    def review_repository_with_agents(
        repository_identifier: str,
        branch: str | None = None,
        max_findings: int = 100,
        max_recommendations: int = 100,
        max_components: int = 100,
        dependency_depth: int = 2,
    ) -> dict[str, Any]:
        """Review persisted repository knowledge through AgentOrchestrator."""

        def _run() -> dict[str, Any]:
            scoped = _scoped_orchestrator(
                max_findings=clamp_tool_limit(
                    max_findings, default=100, maximum=FINDINGS_MAX, label="max_findings"
                ),
                max_recommendations=clamp_tool_limit(
                    max_recommendations,
                    default=100,
                    maximum=RECOMMENDATIONS_MAX,
                    label="max_recommendations",
                ),
                max_components=clamp_tool_limit(
                    max_components,
                    default=100,
                    maximum=COMPONENTS_MAX,
                    label="max_components",
                ),
                dependency_depth=clamp_tool_limit(
                    dependency_depth,
                    default=2,
                    maximum=MAX_DEPENDENCY_DEPTH,
                    label="dependency_depth",
                ),
            )
            result = scoped.review_repository(
                RepositoryReviewRequest(
                    repository_identifier=require_nonblank(
                        repository_identifier,
                        label="repository_identifier",
                    ),
                    branch=branch,
                )
            )
            return map_agent_review_for_mcp(result)

        return run_bounded("review_repository_with_agents", _run)

    @server.tool(name="assess_repository_with_agents", structured_output=True)
    def assess_repository_with_agents(
        repository: str,
        branch: str | None = None,
        with_ai: bool = False,
        config_path: str | None = None,
    ) -> dict[str, Any]:
        """Assess a repository through AgentOrchestrator (validate + IDs)."""

        def _run() -> dict[str, Any]:
            result = orchestrator.assess_repository(
                RepositoryAssessmentRequest(
                    repository=require_nonblank(repository, label="repository"),
                    branch=branch,
                    with_ai=with_ai,
                    config_path=config_path,
                )
            )
            return map_agent_assessment_for_mcp(result)

        return run_bounded("assess_repository_with_agents", _run)

    @server.tool(name="validate_assessment_with_agents", structured_output=True)
    def validate_assessment_with_agents(
        run_id: str,
        repository_identifier: str | None = None,
    ) -> dict[str, Any]:
        """Validate a persisted assessment through AgentOrchestrator."""

        def _run() -> dict[str, Any]:
            repository_id = None
            if repository_identifier is not None and repository_identifier.strip():
                repository_id = queries.resolve_repository(
                    repository_identifier.strip()
                ).repository_id
            result = orchestrator.validate_assessment(
                AssessmentValidationRequest(
                    run_id=require_nonblank(run_id, label="run_id"),
                    repository_id=repository_id,
                )
            )
            return map_agent_validation_for_mcp(result)

        return run_bounded("validate_assessment_with_agents", _run)

    @server.tool(name="compare_snapshots_with_agents", structured_output=True)
    def compare_snapshots_with_agents(
        previous_snapshot_id: str,
        current_snapshot_id: str,
    ) -> dict[str, Any]:
        """Compare snapshots through AgentOrchestrator."""

        def _run() -> dict[str, Any]:
            result = orchestrator.compare_repository_snapshots(
                SnapshotReviewRequest(
                    previous_snapshot_id=require_nonblank(
                        previous_snapshot_id,
                        label="previous_snapshot_id",
                    ),
                    current_snapshot_id=require_nonblank(
                        current_snapshot_id,
                        label="current_snapshot_id",
                    ),
                )
            )
            return map_agent_snapshot_for_mcp(result)

        return run_bounded("compare_snapshots_with_agents", _run)

    @server.tool(name="review_modernization_with_agents", structured_output=True)
    def review_modernization_with_agents(
        repository_identifier: str,
        run_id: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Assemble a modernization review through AgentOrchestrator."""

        del branch  # reserved for future filter parity

        def _run() -> dict[str, Any]:
            result = orchestrator.modernization_review(
                ModernizationReviewRequest(
                    repository_identifier=require_nonblank(
                        repository_identifier,
                        label="repository_identifier",
                    ),
                    run_id=run_id,
                )
            )
            return map_agent_modernization_for_mcp(result)

        return run_bounded("review_modernization_with_agents", _run)
