"""KnowledgeAgent tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.agents.errors import AgentEvidenceError
from codestrata.application.agents.knowledge_agent import KnowledgeAgent
from codestrata.application.agents.policies import AgentExecutionPolicy
from codestrata.application.knowledge.models import RepositoryIdentityHints
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


@pytest.fixture
def seeded_store(tmp_path: Path) -> SqliteKnowledgeStore:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    seed_completed_assessment(store, display_name="demo", include_ai=True)
    return store


def test_resolve_repository_by_id_and_canonical_key(seeded_store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(seeded_store)
    agent = KnowledgeAgent(queries)
    repos = queries.list_repositories()
    assert len(repos) == 1
    by_id = agent.resolve_repository(repos[0].repository_id)
    by_key = agent.resolve_repository(repos[0].canonical_key)
    assert by_id.repository_id == by_key.repository_id


def test_latest_completed_assessment_and_package(seeded_store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(seeded_store)
    agent = KnowledgeAgent(queries, policy=AgentExecutionPolicy(max_findings=5))
    context = agent.get_latest_repository_context("demo")
    assert context.latest_run is not None
    assert context.latest_run.status.value == "completed"

    package = agent.build_repository_review_context("demo")
    assert package.findings
    assert package.recommendations
    assert package.components
    assert package.ai_execution is not None
    assert all(item.source_id for item in package.evidence)
    assert not any("blob" in item.summary.lower() for item in package.evidence)


def test_no_completed_assessment_raises(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name="empty",
            local_path=tmp_path / "empty",
            existing_repository_key="empty",
        )
    )
    agent = KnowledgeAgent(KnowledgeQueryService(store))
    with pytest.raises(AgentEvidenceError):
        agent.build_repository_review_context("empty")


def test_snapshot_comparison_and_explanations(seeded_store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(seeded_store)
    agent = KnowledgeAgent(queries)
    repo_id, run_id, snapshot_id, finding, recommendation = seed_completed_assessment(
        seeded_store,
        display_name="demo2",
        manifest=make_manifest(
            key="demo2",
            files=(("README.md", "b" * 64, 20), ("a.txt", "c" * 64, 5)),
        ),
    )
    first = queries.get_repository_snapshot(snapshot_id)
    second_manifest = make_manifest(
        key="demo2",
        files=(("README.md", "d" * 64, 30),),
    )
    snapshot2 = seeded_store.snapshots.create_or_get_snapshot(
        repository_id=repo_id,
        branch="main",
        revision_type=RepositoryRevisionType.COMMIT,
        revision_id="def456",
        manifest=second_manifest,
        content_fingerprint=fingerprint_for(second_manifest),
    )
    comparison = agent.get_snapshot_change_context(first.snapshot_id, snapshot2.snapshot_id)
    assert comparison.counts.added + comparison.counts.modified + comparison.counts.deleted >= 1

    explanation, evidence = agent.get_finding_evidence(run_id, finding.id)
    assert explanation.finding.finding_id == finding.id
    assert evidence.deterministic is True

    rec_explanation, rec_evidence = agent.get_recommendation_evidence(
        run_id,
        recommendation.id,
    )
    assert rec_explanation.recommendation.recommendation_id == recommendation.id
    assert rec_evidence.source_id == recommendation.id


def test_limits_enforced(seeded_store: SqliteKnowledgeStore) -> None:
    queries = KnowledgeQueryService(seeded_store)
    agent = KnowledgeAgent(queries, policy=AgentExecutionPolicy(max_components=1))
    package = agent.build_repository_review_context("demo")
    assert len(package.components) <= 1


def test_no_fabricated_evidence_without_sources(seeded_store: SqliteKnowledgeStore) -> None:
    agent = KnowledgeAgent(KnowledgeQueryService(seeded_store))
    package = agent.build_repository_review_context("demo")
    for item in package.evidence:
        assert item.source_id
        assert item.evidence_id.startswith("evidence:")
