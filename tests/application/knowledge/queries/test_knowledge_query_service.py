"""Knowledge query service tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.knowledge.models import (
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    RepositoryIdentityHints,
)
from codestrata.application.knowledge.queries import (
    ArtifactNotFoundError,
    ComponentNotFoundError,
    DependencyDirection,
    FindingNotFoundError,
    KnowledgeArtifactCorruptionError,
    KnowledgeQueryService,
    QueryLimitError,
    RecommendationNotFoundError,
    RepositoryQueryNotFoundError,
    SnapshotComparisonError,
    SnapshotNotFoundError,
)
from codestrata.domain.repository.enums import RepositorySourceType
from codestrata.infrastructure.knowledge_store import (
    SqliteKnowledgeStore,
    create_knowledge_query_service,
)
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)


def test_list_repositories_empty(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        service = KnowledgeQueryService(store)
        assert service.list_repositories() == ()


def test_list_and_resolve_repositories(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        seed_completed_assessment(
            store,
            display_name="zeta",
            github_url="https://github.com/acme/zeta.git",
        )
        seed_completed_assessment(
            store,
            display_name="alpha",
            github_url="https://github.com/acme/alpha.git",
        )
        service = KnowledgeQueryService(store)
        repos = service.list_repositories()
        assert [item.display_name for item in repos] == ["alpha", "zeta"]
        assert all(item.latest_completed_run_id for item in repos)
        assert all(item.latest_snapshot_id for item in repos)

        by_id = service.get_repository(repos[0].repository_id)
        assert by_id.canonical_key == "github:acme/alpha"
        resolved = service.resolve_repository("github:acme/zeta")
        assert resolved.display_name == "zeta"
        url_resolved = service.resolve_repository("https://github.com/acme/alpha.git")
        assert url_resolved.repository_id == repos[0].repository_id
        # Public summary never includes local path fields.
        assert "local_path" not in by_id.model_dump()


def test_unknown_repository(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        service = KnowledgeQueryService(store)
        with pytest.raises(RepositoryQueryNotFoundError):
            service.get_repository(str(uuid4()))
        with pytest.raises(RepositoryQueryNotFoundError):
            service.resolve_repository("github:missing/repo")


def test_run_history_and_latest_completed(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id, run_id, _, _, _ = seed_completed_assessment(store)
        failed = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        store.runs.fail_run(failed.run_id, error_code="X", error_message="boom")
        running = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        service = KnowledgeQueryService(store)
        all_runs = service.list_assessment_runs(repo_id, limit=20)
        statuses = {item.status for item in all_runs}
        assert AssessmentRunStatus.COMPLETED in statuses
        assert AssessmentRunStatus.FAILED in statuses
        assert AssessmentRunStatus.RUNNING in statuses
        latest = service.get_latest_completed_run(repo_id)
        assert latest is not None
        assert latest.run_id == run_id
        assert latest.status is AssessmentRunStatus.COMPLETED
        assert running.run_id != latest.run_id
        branch_latest = service.get_latest_completed_run(repo_id, branch="main")
        assert branch_latest is not None
        assert branch_latest.branch == "main"
        with pytest.raises(QueryLimitError):
            service.list_assessment_runs(repo_id, limit=0)


def test_snapshot_queries_and_comparison(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="cmp",
                source_location="https://github.com/acme/cmp.git",
            )
        )
        previous_manifest = make_manifest(
            key="cmp",
            files=(
                ("README.md", "a" * 64, 10),
                ("old.txt", "b" * 64, 5),
                ("meta.txt", "c" * 64, 3),
            ),
        )
        current_manifest = make_manifest(
            key="cmp",
            files=(
                ("README.md", "d" * 64, 11),  # modified
                ("new.txt", "e" * 64, 4),  # added
                ("meta.txt", "c" * 64, 9),  # metadata-only size change
                # old.txt deleted
            ),
        )
        previous = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=previous_manifest.revision.revision_type,
            revision_id="1",
            manifest=previous_manifest,
            content_fingerprint=fingerprint_for(previous_manifest),
        )
        current = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=current_manifest.revision.revision_type,
            revision_id="2",
            manifest=current_manifest,
            content_fingerprint=fingerprint_for(current_manifest),
        )
        other = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="other",
                source_location="https://github.com/acme/other.git",
            )
        )
        foreign_manifest = make_manifest(key="other")
        foreign = store.snapshots.create_or_get_snapshot(
            repository_id=other.repository_id,
            branch="main",
            revision_type=foreign_manifest.revision.revision_type,
            revision_id="9",
            manifest=foreign_manifest,
            content_fingerprint=fingerprint_for(foreign_manifest),
        )

        service = KnowledgeQueryService(store)
        listed = service.list_repository_snapshots(repo.repository_id)
        assert len(listed) == 2
        assert service.get_latest_repository_snapshot(repo.repository_id, branch="main")
        restored = service.get_repository_manifest(current.snapshot_id)
        assert restored.model_dump(mode="json") == current_manifest.model_dump(mode="json")

        comparison = service.compare_repository_snapshots(
            previous.snapshot_id,
            current.snapshot_id,
        )
        assert comparison.counts.added == 1
        assert comparison.counts.modified == 1
        assert comparison.counts.deleted == 1
        assert comparison.counts.metadata_changed == 1
        assert comparison.renamed_files == ()
        assert [item.path for item in comparison.added_files] == ["new.txt"]
        assert [item.path for item in comparison.deleted_files] == ["old.txt"]
        assert [item.path for item in comparison.modified_files] == ["README.md"]
        assert [item.path for item in comparison.metadata_changed_files] == ["meta.txt"]

        unchanged = service.compare_repository_snapshots(
            current.snapshot_id,
            current.snapshot_id,
        )
        assert unchanged.counts.added == 0
        assert unchanged.counts.modified == 0

        with pytest.raises(SnapshotComparisonError):
            service.compare_repository_snapshots(previous.snapshot_id, foreign.snapshot_id)
        with pytest.raises(SnapshotNotFoundError):
            service.get_repository_snapshot(str(uuid4()))


def test_artifact_queries_optional_ai_and_required(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _, run_id, snapshot_id, _, _ = seed_completed_assessment(store, include_ai=False)
        service = KnowledgeQueryService(store)
        kinds = {item.artifact_kind for item in service.list_run_artifacts(run_id)}
        assert KnowledgeArtifactKind.FINDINGS in kinds
        assert KnowledgeArtifactKind.REPOSITORY_GRAPH in kinds
        assert service.get_ai_execution(run_id) is None
        assert service.get_ai_enrichment(run_id) is None
        assert service.get_repository_graph(run_id=run_id).metadata.graph_type.value == "repository"
        assert service.get_repository_graph(snapshot_id=snapshot_id).metadata.graph_id
        assert service.get_engineering_knowledge_graph(run_id).metadata.graph_type.value == (
            "engineering_knowledge"
        )
        assert service.get_knowledge_bindings(run_id).repository_graph_id
        assert service.get_assessment_graph(run_id).metadata.graph_type.value == "assessment"

        # Missing required artifact on a fresh incomplete run.
        repo_id = service.get_assessment_run(run_id).repository_id
        bare = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        with pytest.raises(ArtifactNotFoundError):
            service.get_findings(bare.run_id)


def test_ai_artifacts_when_present(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _, run_id, _, _, _ = seed_completed_assessment(store, include_ai=True)
        service = KnowledgeQueryService(store)
        assert service.get_ai_execution(run_id) is not None
        assert service.get_ai_enrichment(run_id) is not None


def test_corrupt_artifact_raises(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _, run_id, snapshot_id, _, _ = seed_completed_assessment(store)
        artifact = store.runs.get_artifact(run_id, KnowledgeArtifactKind.FINDINGS)
        assert artifact is not None
        blob_path = store.directory / artifact.blob_ref
        blob_path.write_text('{"broken": true}\n', encoding="utf-8")
        service = KnowledgeQueryService(store)
        with pytest.raises(KnowledgeArtifactCorruptionError):
            service.get_findings(run_id)


def test_findings_recommendations_and_explanations(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _, run_id, _, finding, recommendation = seed_completed_assessment(store)
        service = KnowledgeQueryService(store)
        findings = service.get_findings(run_id)
        assert len(findings) == 1
        assert findings[0].finding_id == finding.id
        assert findings[0].finding_id.startswith("finding:")
        assert recommendation.id in findings[0].recommendation_ids

        explanation = service.explain_finding(run_id, finding.id)
        assert explanation.rule_id == "rule.demo"
        assert explanation.ruleset_version == "1.2.0"
        assert explanation.related_recommendations
        assert explanation.evidence
        assert explanation.subjects

        recs = service.get_recommendations(run_id)
        assert recs[0].recommendation_id == recommendation.id
        assert recs[0].roadmap_phase == "phase-1"
        rec_explanation = service.explain_recommendation(run_id, recommendation.id)
        assert rec_explanation.related_findings[0].finding_id == finding.id
        assert rec_explanation.affected_components
        assert rec_explanation.roadmap_phase == "phase-1"

        with pytest.raises(FindingNotFoundError):
            service.explain_finding(run_id, "finding:missing:deadbeefdeadbeef")
        with pytest.raises(RecommendationNotFoundError):
            service.explain_recommendation(run_id, "recommendation:missing:deadbeefdeadbeef")


def test_component_and_dependency_queries(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        _, run_id, _, _, _ = seed_completed_assessment(store, with_cycle=True)
        service = KnowledgeQueryService(store)
        modules = service.list_components(run_id, node_types=("module",), limit=10)
        assert len(modules) == 2
        module_a = next(item for item in modules if item.name == "module-a")
        fetched = service.get_component(run_id, module_a.component_id)
        assert fetched.outgoing_dependency_count == 1

        outgoing = service.get_component_dependencies(
            run_id,
            module_a.component_id,
            direction=DependencyDirection.OUTGOING,
            depth=2,
        )
        assert outgoing.dependencies
        assert all(item.direction == "outgoing" for item in outgoing.dependencies)
        assert max(item.depth for item in outgoing.dependencies) <= 2

        dep = next(
            item
            for item in service.list_components(run_id, node_types=("dependency",))
            if item.name == "lib-b"
        )
        both = service.get_component_dependencies(
            run_id,
            dep.component_id,
            direction=DependencyDirection.BOTH,
            depth=3,
        )
        assert both.dependencies
        # Cycle must not explode; unique edges only.
        keys = {
            (
                item.source_component_id,
                item.target_component_id,
                item.relationship_type,
                item.direction,
            )
            for item in both.dependencies
        }
        assert len(keys) == len(both.dependencies)

        with pytest.raises(ComponentNotFoundError):
            service.get_component(run_id, "node:missing")
        with pytest.raises(QueryLimitError):
            service.get_component_dependencies(
                run_id,
                module_a.component_id,
                depth=9,
            )


def test_factory_composition(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    with SqliteKnowledgeStore(knowledge_dir) as store:
        seed_completed_assessment(store, github_url="https://github.com/acme/factory.git")
    service = create_knowledge_query_service(directory=knowledge_dir)
    assert service.list_repositories()
    assert "blob_ref" not in service.list_repositories()[0].model_dump()


def test_incomplete_run_never_latest(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id, completed_run_id, _, _, _ = seed_completed_assessment(store)
        store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        service = KnowledgeQueryService(store)
        latest = service.get_latest_completed_run(repo_id)
        assert latest is not None
        assert latest.run_id == completed_run_id
