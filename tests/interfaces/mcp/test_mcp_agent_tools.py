"""MCP agent tool tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from codestrata.application.agents import (
    AgentOrchestrator,
    AgentStatus,
)
from codestrata.application.agents.errors import AgentExecutionError
from codestrata.application.agents.models import (
    AssessmentValidationResult,
    AssessmentValidationWorkflowResult,
    ValidationIssue,
    ValidationSeverity,
)
from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.interfaces.mcp import create_mcp_server
from codestrata.interfaces.mcp.errors import raise_tool_error
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


async def _call(server: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    result = await server.call_tool(name, arguments or {})
    if isinstance(result, tuple):
        structured = result[1]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    if isinstance(result, list) and result:
        return json.loads(result[0].text)
    return result


def test_agent_tools_registered_alongside_granular(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            tools = {tool.name for tool in await server.list_tools()}
            assert "list_repositories" in tools
            assert "run_assessment" in tools
            for name in (
                "review_repository_with_agents",
                "assess_repository_with_agents",
                "validate_assessment_with_agents",
                "compare_snapshots_with_agents",
                "review_modernization_with_agents",
            ):
                assert name in tools
            assert len([t for t in tools if t.endswith("_with_agents")]) == 5

        asyncio.run(_check())


def test_review_and_validate_agent_tools(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id, run_id, snapshot_id, _, _ = seed_completed_assessment(store, display_name="alpha")
        queries = KnowledgeQueryService(store)
        server = create_mcp_server(
            query_service=queries,
            assessment_service=AssessmentApplicationService(),
        )

        async def _check() -> None:
            review = await _call(
                server,
                "review_repository_with_agents",
                {"repository_identifier": "alpha"},
            )
            assert review["status"] in {"completed", "blocked"}
            assert review["repository"]["repository_id"] == repo_id
            assert "steps" in review
            assert "evidence" not in review or "evidence_summary" in review
            assert "html" not in json.dumps(review).lower()

            validation = await _call(
                server,
                "validate_assessment_with_agents",
                {"run_id": run_id, "repository_identifier": repo_id},
            )
            assert validation["run_id"] == run_id
            assert "validation" in validation
            assert "issue_total_count" in validation["validation"]

            modern = await _call(
                server,
                "review_modernization_with_agents",
                {"repository_identifier": "alpha"},
            )
            assert modern["repository_id"] == repo_id
            assert "roadmap_phases" in modern

            second = store.snapshots.create_or_get_snapshot(
                repository_id=repo_id,
                branch="main",
                revision_type=RepositoryRevisionType.COMMIT,
                revision_id="second",
                manifest=make_manifest(
                    key="alpha",
                    files=(("README.md", "a" * 64, 20), ("x.txt", "b" * 64, 1)),
                ),
                content_fingerprint=fingerprint_for(
                    make_manifest(
                        key="alpha",
                        files=(("README.md", "a" * 64, 20), ("x.txt", "b" * 64, 1)),
                    )
                ),
            )
            compared = await _call(
                server,
                "compare_snapshots_with_agents",
                {
                    "previous_snapshot_id": snapshot_id,
                    "current_snapshot_id": second.snapshot_id,
                },
            )
            assert compared["status"] == "completed"
            assert compared["comparison"] is not None

        asyncio.run(_check())


def test_factory_accepts_injected_orchestrator(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _repo_id, run_id, _, _, _ = seed_completed_assessment(store, display_name="demo")
        queries = KnowledgeQueryService(store)
        fake = MagicMock(spec=AgentOrchestrator)
        fake.validate_assessment.return_value = AssessmentValidationWorkflowResult(
            workflow_id="wf",
            status=AgentStatus.COMPLETED,
            run_id=run_id,
            validation=AssessmentValidationResult(valid=True, blocking=False),
        )
        server = create_mcp_server(
            query_service=queries,
            assessment_service=AssessmentApplicationService(),
            agent_orchestrator=fake,
        )

        async def _check() -> None:
            result = await _call(
                server,
                "validate_assessment_with_agents",
                {"run_id": run_id},
            )
            assert result["workflow_id"] == "wf"
            fake.validate_assessment.assert_called_once()

        asyncio.run(_check())


def test_blocking_validation_returned_structurally() -> None:
    blocked = AssessmentValidationWorkflowResult(
        workflow_id="w",
        status=AgentStatus.BLOCKED,
        run_id="run-1",
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
    )
    from codestrata.interfaces.mcp.agent_mapping import map_agent_validation_for_mcp

    payload = map_agent_validation_for_mcp(blocked)
    assert payload["status"] == "blocked"
    assert payload["validation"]["blocking"] is True


def test_agent_error_translation() -> None:
    with pytest.raises(ToolError) as raised:
        raise_tool_error(AgentExecutionError("boom"), tool_name="assess_repository_with_agents")
    assert "boom" in str(raised.value)
    assert "Traceback" not in str(raised.value)


def test_mcp_agent_tools_call_orchestrator_not_sqlite() -> None:
    root = Path(__file__).resolve().parents[3] / "src" / "codestrata" / "interfaces" / "mcp"
    agents_tool = (root / "tools" / "agents.py").read_text(encoding="utf-8")
    assert "AgentOrchestrator" in agents_tool or "create_agent_orchestrator" in agents_tool
    assert "sqlite3" not in agents_tool
    assert "SqliteKnowledgeStore" not in agents_tool
    assert "report.json" not in agents_tool
