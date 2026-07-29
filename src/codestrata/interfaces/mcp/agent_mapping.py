"""MCP-safe mapping for Agent Framework workflow results."""

from __future__ import annotations

from typing import Any

from codestrata.application.agents.models import (
    AssessmentValidationWorkflowResult,
    ModernizationReviewResult,
    RepositoryAssessmentResult,
    RepositoryReviewResult,
    SnapshotReviewResult,
)
from codestrata.application.agents.serialization import (
    DEFAULT_ISSUE_LIMIT,
    map_modernization_review,
    map_repository_assessment,
    map_repository_review,
    map_snapshot_review,
    map_validation_workflow,
)
from codestrata.interfaces.mcp.mapping import to_mcp_dict
from codestrata.interfaces.mcp.security import redact_mapping

FOLLOW_UP_TOOLS_AFTER_ASSESSMENT = (
    "get_assessment",
    "list_findings",
    "list_recommendations",
    "explain_finding",
    "explain_recommendation",
    "get_component_dependencies",
)


def map_agent_review_for_mcp(result: RepositoryReviewResult) -> dict[str, Any]:
    payload = redact_mapping(map_repository_review(result, include_full_evidence=False))
    assert isinstance(payload, dict)
    return payload


def map_agent_assessment_for_mcp(result: RepositoryAssessmentResult) -> dict[str, Any]:
    payload = map_repository_assessment(result, include_full_evidence=False)
    payload["suggested_follow_up_tools"] = list(FOLLOW_UP_TOOLS_AFTER_ASSESSMENT)
    redacted = redact_mapping(payload)
    assert isinstance(redacted, dict)
    return redacted


def map_agent_validation_for_mcp(
    result: AssessmentValidationWorkflowResult,
    *,
    issue_limit: int = DEFAULT_ISSUE_LIMIT,
) -> dict[str, Any]:
    payload = redact_mapping(map_validation_workflow(result, issue_limit=issue_limit))
    assert isinstance(payload, dict)
    return payload


def map_agent_snapshot_for_mcp(result: SnapshotReviewResult) -> dict[str, Any]:
    payload = redact_mapping(map_snapshot_review(result, include_full_evidence=False))
    assert isinstance(payload, dict)
    return payload


def map_agent_modernization_for_mcp(result: ModernizationReviewResult) -> dict[str, Any]:
    payload = redact_mapping(map_modernization_review(result, include_full_evidence=False))
    assert isinstance(payload, dict)
    return payload


def map_agent_result_for_mcp(result: object) -> dict[str, Any]:
    """Dispatch mapping for any supported agent workflow result."""

    if isinstance(result, RepositoryReviewResult):
        return map_agent_review_for_mcp(result)
    if isinstance(result, RepositoryAssessmentResult):
        return map_agent_assessment_for_mcp(result)
    if isinstance(result, AssessmentValidationWorkflowResult):
        return map_agent_validation_for_mcp(result)
    if isinstance(result, SnapshotReviewResult):
        return map_agent_snapshot_for_mcp(result)
    if isinstance(result, ModernizationReviewResult):
        return map_agent_modernization_for_mcp(result)
    return to_mcp_dict(result)
