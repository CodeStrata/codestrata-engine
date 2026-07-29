"""End-to-end Agent Framework integration against a temporary knowledge store."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.agents.factory import create_agent_orchestrator
from codestrata.application.agents.models import (
    AgentStatus,
    AssessmentValidationRequest,
    ModernizationReviewRequest,
    RepositoryReviewRequest,
    SnapshotReviewRequest,
)
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


def test_agent_framework_review_validate_compare_modernize(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo_id, run_id, snapshot_id, finding, recommendation = seed_completed_assessment(
        store,
        display_name="pet",
    )

    # Second assessment snapshot for comparison.
    second_manifest = make_manifest(
        key="pet",
        files=(("README.md", "e" * 64, 18), ("src/App.js", "f" * 64, 100)),
    )
    snapshot2 = store.snapshots.create_or_get_snapshot(
        repository_id=repo_id,
        branch="main",
        revision_type=RepositoryRevisionType.COMMIT,
        revision_id="second",
        manifest=second_manifest,
        content_fingerprint=fingerprint_for(second_manifest),
    )
    seed_completed_assessment(
        store,
        display_name="pet",
        manifest=second_manifest,
    )

    queries = KnowledgeQueryService(store)
    orchestrator = create_agent_orchestrator(
        query_service=queries,
        include_assessment_agent=False,
    )

    review = orchestrator.review_repository(RepositoryReviewRequest(repository_identifier=repo_id))
    assert review.status in {AgentStatus.COMPLETED, AgentStatus.BLOCKED}
    assert review.latest_run is not None
    assert all(item.source_id for item in review.evidence)

    validation = orchestrator.validate_assessment(
        AssessmentValidationRequest(run_id=review.latest_run.run_id, repository_id=repo_id)
    )
    assert validation.run_id == review.latest_run.run_id

    comparison = orchestrator.compare_repository_snapshots(
        SnapshotReviewRequest(
            previous_snapshot_id=snapshot_id,
            current_snapshot_id=snapshot2.snapshot_id,
        )
    )
    assert comparison.comparison is not None

    modernize = orchestrator.modernization_review(
        ModernizationReviewRequest(repository_identifier="pet")
    )
    assert modernize.top_recommendations
    assert recommendation.id in {item.recommendation_id for item in modernize.top_recommendations}
    assert finding.id
    # Agent Framework must not read report artifacts.
    assert not (tmp_path / "report.json").exists()
    assert not any("report.json" in warning for warning in modernize.warnings)
