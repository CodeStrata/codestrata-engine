"""AssessmentAgent tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codestrata.application.agents.assessment_agent import AssessmentAgent
from codestrata.application.agents.errors import AgentExecutionError
from codestrata.application.agents.models import RepositoryAssessmentRequest
from codestrata.application.assessment.service import (
    AssessmentCommandError,
    AssessmentCommandResult,
)
from codestrata.reporting.modernization_models import AssessmentMode


def _command(**overrides: object) -> AssessmentCommandResult:
    base = {
        "repository_name": "demo",
        "run_directory": Path("/tmp/run"),
        "html_report_path": Path("/tmp/run/report.html"),
        "json_report_path": Path("/tmp/run/report.json"),
        "mode": AssessmentMode.DETERMINISTIC,
        "findings_count": 1,
        "technologies_count": 1,
        "recommendations_count": 1,
        "phases_count": 1,
        "ai_executed": False,
        "knowledge_repository_id": "repo-1",
        "knowledge_run_id": "run-1",
        "knowledge_snapshot_id": "snap-1",
    }
    base.update(overrides)
    return AssessmentCommandResult(**base)  # type: ignore[arg-type]


def test_deterministic_assessment_returns_ids(tmp_path: Path) -> None:
    service = MagicMock()
    service.run.return_value = _command()
    agent = AssessmentAgent(assessment_service=service)
    result = agent.run_assessment(
        RepositoryAssessmentRequest(repository=str(tmp_path), with_ai=False)
    )
    assert result.repository_id == "repo-1"
    assert result.snapshot_id == "snap-1"
    assert result.run_id == "run-1"
    assert result.ai_requested is False
    kwargs = service.run.call_args.kwargs
    assert kwargs["mode"] is AssessmentMode.DETERMINISTIC


def test_ai_assessment_uses_ai_mode() -> None:
    service = MagicMock()
    service.run.return_value = _command(mode=AssessmentMode.AI_ENHANCED, ai_executed=True)
    provider = MagicMock()
    agent = AssessmentAgent(assessment_service=service)
    result = agent.run_assessment(
        RepositoryAssessmentRequest(repository="/repo", with_ai=True),
        provider=provider,
    )
    assert result.ai_requested is True
    assert service.run.call_args.kwargs["mode"] is AssessmentMode.AI_ENHANCED
    assert service.run.call_args.kwargs["provider"] is provider


def test_application_error_propagated() -> None:
    service = MagicMock()
    service.run.side_effect = AssessmentCommandError("boom")
    agent = AssessmentAgent(assessment_service=service)
    with pytest.raises(AgentExecutionError, match="boom"):
        agent.run_assessment(RepositoryAssessmentRequest(repository="/repo"))


def test_missing_knowledge_ids_warn() -> None:
    service = MagicMock()
    service.run.return_value = _command(
        knowledge_repository_id=None,
        knowledge_run_id=None,
        knowledge_snapshot_id=None,
    )
    agent = AssessmentAgent(assessment_service=service)
    result = agent.run_assessment(RepositoryAssessmentRequest(repository="/repo"))
    assert result.run_id is None
    assert result.warnings
    assert "knowledge-store IDs" in result.warnings[0]


def test_no_cli_or_mcp_invocation() -> None:
    service = MagicMock()
    service.run.return_value = _command()
    agent = AssessmentAgent(assessment_service=service)
    agent.run_assessment(RepositoryAssessmentRequest(repository="/repo"))
    # Only the application service should be invoked.
    service.run.assert_called_once()
