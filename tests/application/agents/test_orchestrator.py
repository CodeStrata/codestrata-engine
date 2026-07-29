"""AgentOrchestrator workflow tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codestrata.application.agents.assessment_agent import AssessmentAgent
from codestrata.application.agents.errors import AgentWorkflowBlockedError
from codestrata.application.agents.factory import create_agent_orchestrator
from codestrata.application.agents.models import (
    AgentStatus,
    AssessmentValidationRequest,
    AssessmentValidationResult,
    ModernizationReviewRequest,
    RepositoryAssessmentRequest,
    RepositoryReviewRequest,
    SnapshotReviewRequest,
    ValidationIssue,
    ValidationSeverity,
)
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.assessment.service import AssessmentCommandResult
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.reporting.modernization_models import AssessmentMode
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


@pytest.fixture
def store(tmp_path: Path) -> SqliteKnowledgeStore:
    knowledge = SqliteKnowledgeStore(tmp_path / "knowledge")
    knowledge.open()
    seed_completed_assessment(knowledge, display_name="demo", include_ai=False)
    return knowledge


def test_repository_review_workflow(store: SqliteKnowledgeStore) -> None:
    orchestrator = create_agent_orchestrator(
        query_service=KnowledgeQueryService(store),
        include_assessment_agent=False,
    )
    result = orchestrator.review_repository(RepositoryReviewRequest(repository_identifier="demo"))
    assert result.status is AgentStatus.COMPLETED
    assert result.repository is not None
    assert result.latest_run is not None
    assert result.validation is not None
    assert result.validation.blocking is False
    assert result.top_findings
    assert result.evidence
    step_names = [step.name for step in result.steps]
    assert step_names[0] == "resolve_repository_context"
    assert "validate_assessment" in step_names
    assert result.workflow_id


def test_validation_workflow(store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(store)
    run = queries.get_latest_completed_run(queries.resolve_repository("demo").repository_id)
    assert run is not None
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        include_assessment_agent=False,
    )
    result = orchestrator.validate_assessment(AssessmentValidationRequest(run_id=run.run_id))
    assert result.status is AgentStatus.COMPLETED
    assert result.validation.valid or not result.validation.blocking


def test_snapshot_comparison_workflow(store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(store)
    repo = queries.resolve_repository("demo")
    first = queries.get_latest_repository_snapshot(repo.repository_id)
    assert first is not None
    second_manifest = make_manifest(
        key="demo",
        files=(("README.md", "a" * 64, 40), ("new.md", "b" * 64, 3)),
    )
    from codestrata.domain.repository.enums import RepositoryRevisionType

    second = store.snapshots.create_or_get_snapshot(
        repository_id=repo.repository_id,
        branch="main",
        revision_type=RepositoryRevisionType.COMMIT,
        revision_id="zzz",
        manifest=second_manifest,
        content_fingerprint=fingerprint_for(second_manifest),
    )
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        include_assessment_agent=False,
    )
    result = orchestrator.compare_repository_snapshots(
        SnapshotReviewRequest(
            previous_snapshot_id=first.snapshot_id,
            current_snapshot_id=second.snapshot_id,
        )
    )
    assert result.status is AgentStatus.COMPLETED
    assert result.comparison is not None


def test_modernization_review_package(store: SqliteKnowledgeStore) -> None:
    orchestrator = create_agent_orchestrator(
        query_service=KnowledgeQueryService(store),
        include_assessment_agent=False,
    )
    result = orchestrator.modernization_review(
        ModernizationReviewRequest(repository_identifier="demo")
    )
    assert result.status is AgentStatus.COMPLETED
    assert result.recommendation_summary is not None
    assert result.top_recommendations
    assert result.roadmap_phases  # seeded metadata roadmap_phase=phase-1
    assert result.validation is not None


def test_stop_on_blocking_validation(
    store: SqliteKnowledgeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries = KnowledgeQueryService(store)
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        include_assessment_agent=False,
        policy=AgentExecutionPolicy(stop_on_blocking_validation=True),
    )

    blocking = AssessmentValidationResult(
        valid=False,
        blocking=True,
        issues=(
            ValidationIssue(
                code="required_artifact_missing",
                severity=ValidationSeverity.BLOCKING,
                message="missing",
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator._validation,  # noqa: SLF001
        "validate_assessment",
        lambda *args, **kwargs: blocking,
    )
    result = orchestrator.review_repository(RepositoryReviewRequest(repository_identifier="demo"))
    assert result.status is AgentStatus.BLOCKED


def test_assessment_workflow_with_fake_service(store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(store)
    repo = queries.resolve_repository("demo")
    run = queries.get_latest_completed_run(repo.repository_id)
    assert run is not None

    service = MagicMock()
    command = AssessmentCommandResult(
        repository_name="demo",
        run_directory=Path("/tmp/run"),
        html_report_path=Path("/tmp/run/report.html"),
        json_report_path=Path("/tmp/run/report.json"),
        mode=AssessmentMode.DETERMINISTIC,
        findings_count=1,
        technologies_count=1,
        recommendations_count=1,
        phases_count=1,
        ai_executed=False,
        knowledge_repository_id=repo.repository_id,
        knowledge_run_id=run.run_id,
        knowledge_snapshot_id=run.snapshot_id,
    )
    service.run.return_value = command
    assessment_agent = AssessmentAgent(assessment_service=service)
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        assessment_service=service,
    )
    # Replace with our agent that already has the mock (create already built one).
    orchestrator._assessment = assessment_agent  # noqa: SLF001

    result = orchestrator.assess_repository(
        RepositoryAssessmentRequest(repository="demo", with_ai=False)
    )
    assert result.status in {AgentStatus.COMPLETED, AgentStatus.BLOCKED}
    assert result.repository_id == repo.repository_id
    assert result.run_id == run.run_id
    assert result.steps
    assert [step.name for step in result.steps][2] == "run_assessment"
    service.run.assert_called_once()


def test_max_steps_enforced(store: SqliteKnowledgeStore) -> None:
    with pytest.raises(AgentWorkflowBlockedError):
        create_agent_orchestrator(
            query_service=KnowledgeQueryService(store),
            include_assessment_agent=False,
            policy=AgentExecutionPolicy(max_steps=1),
        ).review_repository(RepositoryReviewRequest(repository_identifier="demo"))
