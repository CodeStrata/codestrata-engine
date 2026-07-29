"""Factory and composition tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from codestrata.application.agents.factory import create_agent_orchestrator
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import load_settings
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore


def test_fake_service_injection(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    queries = KnowledgeQueryService(store)
    assessment = MagicMock()
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        assessment_service=assessment,
        policy=AgentExecutionPolicy(max_findings=10),
    )
    assert orchestrator is not None


def test_default_and_custom_policy(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    queries = KnowledgeQueryService(store)
    default = create_agent_orchestrator(query_service=queries, include_assessment_agent=False)
    custom = create_agent_orchestrator(
        query_service=queries,
        include_assessment_agent=False,
        policy=AgentExecutionPolicy(max_steps=6),
    )
    assert default._policy.max_steps == 10  # noqa: SLF001
    assert custom._policy.max_steps == 6  # noqa: SLF001


def test_production_composition_with_temporary_settings(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    config = tmp_path / "codestrata.toml"
    config.write_text(
        f"""
        [repository]
        path = "test-fixtures/sample-js-app"

        [knowledge]
        directory = "{knowledge.as_posix()}"

        [agents]
        max_steps = 9
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    orchestrator = create_agent_orchestrator(settings=settings)
    assert orchestrator._policy.max_steps == 9  # noqa: SLF001
