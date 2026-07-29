"""ValidationAgent tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.agents.models import ValidationSeverity
from codestrata.application.agents.validation_agent import ValidationAgent
from codestrata.application.knowledge.models import AssessmentRunStatus
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.application.knowledge.queries.models import FindingView
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from tests.application.knowledge.queries.conftest_helpers import seed_completed_assessment


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[SqliteKnowledgeStore, str, str, str]:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo_id, run_id, snapshot_id, _, _ = seed_completed_assessment(store)
    return store, repo_id, run_id, snapshot_id


def test_valid_completed_run(seeded: tuple[SqliteKnowledgeStore, str, str, str]) -> None:
    store, repo_id, run_id, _ = seeded
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(
        run_id,
        expected_repository_id=repo_id,
        ai_requested=False,
    )
    assert result.blocking is False
    assert result.checked_findings >= 1
    assert result.ai_validation_status == "not_requested"


def test_run_not_found(seeded: tuple[SqliteKnowledgeStore, str, str, str]) -> None:
    store, _, _, _ = seeded
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(str(uuid4()))
    assert result.blocking is True
    assert result.issues[0].code == "run_not_found"


def test_repository_mismatch(seeded: tuple[SqliteKnowledgeStore, str, str, str]) -> None:
    store, _, run_id, _ = seeded
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(
        run_id,
        expected_repository_id=str(uuid4()),
    )
    assert any(item.code == "repository_mismatch" for item in result.issues)
    assert result.blocking is True


def test_incomplete_and_failed_runs(
    seeded: tuple[SqliteKnowledgeStore, str, str, str],
) -> None:
    store, repo_id, _, _ = seeded
    incomplete = store.runs.create_run(
        repository_id=repo_id,
        assessment_mode="deterministic",
        codestrata_version="0.1.0",
        ruleset_version="1.0.0",
    )
    agent = ValidationAgent(KnowledgeQueryService(store))
    incomplete_result = agent.validate_assessment(incomplete.run_id)
    assert any(item.code == "run_incomplete" for item in incomplete_result.issues)

    failed = store.runs.create_run(
        repository_id=repo_id,
        assessment_mode="deterministic",
        codestrata_version="0.1.0",
        ruleset_version="1.0.0",
    )
    store.runs.fail_run(failed.run_id, error_code="boom", error_message="failed")
    failed_result = agent.validate_assessment(failed.run_id)
    assert any(item.code == "run_failed" for item in failed_result.issues)
    assert store.runs.get_run(failed.run_id).status is AssessmentRunStatus.FAILED  # type: ignore[union-attr]


def test_missing_required_artifact(
    seeded: tuple[SqliteKnowledgeStore, str, str, str],
) -> None:
    store, repo_id, _, snapshot_id = seeded
    run = store.runs.create_run(
        repository_id=repo_id,
        assessment_mode="deterministic",
        codestrata_version="0.1.0",
        ruleset_version="1.0.0",
    )
    store.runs.complete_run(run.run_id, snapshot_id=snapshot_id, artifacts=[])
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(run.run_id)
    assert result.blocking is True
    assert any(item.code == "required_artifact_missing" for item in result.issues)


def test_phase1_uuid_finding_not_authoritative(
    seeded: tuple[SqliteKnowledgeStore, str, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, repo_id, run_id, _ = seeded
    queries = KnowledgeQueryService(store)
    agent = ValidationAgent(queries)

    fake = (
        FindingView(
            finding_id=str(uuid4()),
            rule_id="rule.x",
            severity="high",
            category="architecture",
            title="uuid finding",
            description="should be blocked",
        ),
    )
    monkeypatch.setattr(queries, "get_findings", lambda _run_id: fake)
    monkeypatch.setattr(queries, "get_recommendations", lambda _run_id: ())

    result = agent.validate_assessment(run_id, expected_repository_id=repo_id)
    assert any(item.code == "phase1_uuid_finding" for item in result.issues)
    assert result.blocking is True


def test_successful_ai_run(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    _, run_id, _, _, _ = seed_completed_assessment(
        store,
        display_name="ai-demo",
        include_ai=True,
    )
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(
        run_id,
        ai_requested=True,
    )
    assert result.ai_validation_status == "succeeded"
    assert result.blocking is False


def test_ai_requested_but_missing(seeded: tuple[SqliteKnowledgeStore, str, str, str]) -> None:
    store, _, run_id, _ = seeded
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(
        run_id,
        ai_requested=True,
    )
    assert result.ai_validation_status == "missing"
    assert any(item.code == "ai_execution_missing" for item in result.issues)


def test_issue_severities_are_typed(
    seeded: tuple[SqliteKnowledgeStore, str, str, str],
) -> None:
    store, _, run_id, _ = seeded
    result = ValidationAgent(KnowledgeQueryService(store)).validate_assessment(run_id)
    for item in result.issues:
        assert isinstance(item.severity, ValidationSeverity)
