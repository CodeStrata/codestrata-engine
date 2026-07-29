"""CLI agent command tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.application.knowledge.queries.conftest_helpers import seed_completed_assessment
from typer.testing import CliRunner

from codestrata.application.agents.models import (
    AgentName,
    AgentStatus,
    AgentStep,
    AssessmentValidationResult,
    AssessmentValidationWorkflowResult,
    RepositoryReviewResult,
    ValidationIssue,
    ValidationSeverity,
)
from codestrata.cli import app
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore

runner = CliRunner()


def _config(tmp_path: Path, knowledge: Path) -> Path:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
        [repository]
        path = "test-fixtures/sample-js-app"

        [knowledge]
        directory = "{knowledge.as_posix()}"

        [agents]
        enabled = true
        """,
        encoding="utf-8",
    )
    return config


def test_agent_help_lists_commands() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    for name in ("review", "assess", "validate", "compare", "modernization-review"):
        assert name in result.stdout


def test_existing_assess_and_mcp_help_unchanged() -> None:
    assess = runner.invoke(app, ["assess", "--help"])
    assert assess.exit_code == 0
    assert "agent" not in assess.stdout.lower() or "Assess" in assess.stdout
    mcp = runner.invoke(app, ["mcp", "serve", "--help"])
    assert mcp.exit_code == 0


def test_agent_review_success_and_json(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with SqliteKnowledgeStore(knowledge) as store:
        seed_completed_assessment(store, display_name="demo")
    config = _config(tmp_path, knowledge)

    result = runner.invoke(
        app,
        ["agent", "review", "--repository", "demo", "--config", str(config)],
    )
    assert result.exit_code == 0
    assert "Repository review" in result.stdout
    assert "demo" in result.stdout

    json_result = runner.invoke(
        app,
        ["agent", "review", "--repository", "demo", "--config", str(config), "--json"],
    )
    assert json_result.exit_code == 0
    assert '"workflow_id"' in json_result.stdout
    assert '"status"' in json_result.stdout


def test_agent_review_not_found(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with SqliteKnowledgeStore(knowledge):
        pass
    config = _config(tmp_path, knowledge)
    result = runner.invoke(
        app,
        ["agent", "review", "--repository", "missing", "--config", str(config)],
    )
    assert result.exit_code != 0


def test_agent_validate_exit_codes(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with SqliteKnowledgeStore(knowledge) as store:
        _repo_id, run_id, _, _, _ = seed_completed_assessment(store, display_name="demo")
    config = _config(tmp_path, knowledge)

    ok = runner.invoke(
        app,
        ["agent", "validate", "--run-id", run_id, "--config", str(config)],
    )
    assert ok.exit_code == 0

    blocked = AssessmentValidationWorkflowResult(
        workflow_id="w",
        status=AgentStatus.BLOCKED,
        run_id=run_id,
        validation=AssessmentValidationResult(
            valid=False,
            blocking=True,
            issues=(
                ValidationIssue(
                    code="required_artifact_missing",
                    severity=ValidationSeverity.BLOCKING,
                    message="missing",
                ),
            ),
        ),
        steps=(
            AgentStep(
                name="validate_assessment",
                agent=AgentName.VALIDATION,
                status=AgentStatus.COMPLETED,
            ),
        ),
    )
    with patch("codestrata.cli.agent._compose") as compose:
        compose.return_value = (
            MagicMock(validate_assessment=MagicMock(return_value=blocked)),
            MagicMock(),
        )
        blocked_result = runner.invoke(
            app,
            ["agent", "validate", "--run-id", run_id, "--config", str(config)],
        )
        assert blocked_result.exit_code == 1


def test_agent_invalid_dependency_depth(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with SqliteKnowledgeStore(knowledge) as store:
        seed_completed_assessment(store, display_name="demo")
    config = _config(tmp_path, knowledge)
    result = runner.invoke(
        app,
        [
            "agent",
            "review",
            "--repository",
            "demo",
            "--config",
            str(config),
            "--dependency-depth",
            "9",
        ],
    )
    assert result.exit_code == 2


def test_cli_agent_module_architecture() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "cli"
    agent_py = (root / "agent.py").read_text(encoding="utf-8")
    assert "fastmcp" not in agent_py.lower()
    assert "AgentOrchestrator" in agent_py or "create_agent_orchestrator" in agent_py
    assert "report.json" not in agent_py
    assert "sqlite3" not in agent_py


def test_review_result_shape_for_mapping() -> None:
    result = RepositoryReviewResult(
        workflow_id="w1",
        status=AgentStatus.COMPLETED,
        steps=(),
        warnings=(),
    )
    assert result.status is AgentStatus.COMPLETED
