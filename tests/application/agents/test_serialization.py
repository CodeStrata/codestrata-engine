"""Tests for agent result serialization used by CLI/MCP adapters."""

from __future__ import annotations

from codestrata.application.agents.models import (
    AgentStatus,
    AssessmentValidationResult,
    AssessmentValidationWorkflowResult,
    RepositoryAssessmentResult,
    RepositoryReviewResult,
    ValidationIssue,
    ValidationSeverity,
)
from codestrata.application.agents.serialization import (
    agent_result_to_dict,
    exit_code_for_status,
    map_validation,
)
from codestrata.cli.agent_mapping import EXIT_BLOCKED, EXIT_ERROR, EXIT_SUCCESS


def test_review_serialization_omits_full_evidence_by_default() -> None:
    result = RepositoryReviewResult(
        workflow_id="w",
        status=AgentStatus.COMPLETED,
        ai_status="not_present",
    )
    payload = agent_result_to_dict(result)
    assert payload["workflow_id"] == "w"
    assert payload["status"] == "completed"
    assert "evidence_summary" in payload
    assert "evidence" not in payload


def test_validation_issue_truncation() -> None:
    issues = tuple(
        ValidationIssue(
            code=f"code-{index}",
            severity=ValidationSeverity.WARNING,
            message=f"m{index}",
        )
        for index in range(60)
    )
    validation = AssessmentValidationResult(
        valid=True,
        blocking=False,
        issues=issues,
    )
    mapped = map_validation(validation, issue_limit=10)
    assert mapped is not None
    assert mapped["issue_total_count"] == 60
    assert mapped["issue_returned_count"] == 10
    assert mapped["issue_truncated"] is True


def test_exit_codes() -> None:
    assert exit_code_for_status(AgentStatus.COMPLETED) == EXIT_SUCCESS
    assert exit_code_for_status(AgentStatus.BLOCKED) == EXIT_BLOCKED
    assert exit_code_for_status(AgentStatus.FAILED) == EXIT_ERROR


def test_assessment_mapping_fields() -> None:
    result = RepositoryAssessmentResult(
        workflow_id="w",
        status=AgentStatus.COMPLETED,
        repository_id="r",
        snapshot_id="s",
        run_id="run",
        ai_status="not_requested",
    )
    payload = agent_result_to_dict(result)
    assert payload["repository_id"] == "r"
    assert payload["run_id"] == "run"


def test_validation_workflow_mapping() -> None:
    result = AssessmentValidationWorkflowResult(
        workflow_id="w",
        status=AgentStatus.COMPLETED,
        run_id="run",
        validation=AssessmentValidationResult(valid=True, blocking=False),
    )
    payload = agent_result_to_dict(result)
    assert payload["validation"]["valid"] is True
