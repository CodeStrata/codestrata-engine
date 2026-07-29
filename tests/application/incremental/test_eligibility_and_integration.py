"""Previous-run eligibility and planning integration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from codestrata import RULESET_VERSION, __version__
from codestrata.application.incremental.eligibility import PreviousRunEligibilityChecker
from codestrata.application.incremental.models import (
    IncrementalPlanMode,
    IncrementalPlanningRequest,
)
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.application.knowledge.models import AssessmentRunStatus, KnowledgeArtifactKind
from codestrata.application.knowledge.queries.service import KnowledgeQueryService
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from tests.application.incremental.helpers import candidate_state, entry, manifest
from tests.application.knowledge.queries.conftest_helpers import (
    make_manifest,
    seed_completed_assessment,
)


def test_eligibility_completed_run(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    try:
        repo_id, run_id, snapshot_id, _, _ = seed_completed_assessment(store)
        queries = KnowledgeQueryService(store)
        result = PreviousRunEligibilityChecker(queries).check(
            run_id,
            expected_repository_id=repo_id,
            branch="main",
        )
        assert result.eligible is True
        assert result.snapshot_id == snapshot_id
    finally:
        store.close()


def test_eligibility_rejects_running_failed_and_uuid_findings(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    try:
        repo_id, run_id, _, _, _ = seed_completed_assessment(store)
        queries = KnowledgeQueryService(store)

        running = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version=__version__,
            ruleset_version=RULESET_VERSION,
        )
        running_check = PreviousRunEligibilityChecker(queries).check(
            running.run_id,
            expected_repository_id=repo_id,
        )
        assert running_check.eligible is False
        assert "run_running" in running_check.reasons

        # Fail the running run and re-check.
        store.runs.fail_run(running.run_id, error_code="boom", error_message="failed")
        failed_check = PreviousRunEligibilityChecker(queries).check(
            running.run_id,
            expected_repository_id=repo_id,
        )
        assert failed_check.eligible is False
        assert "run_failed" in failed_check.reasons

        # Repository mismatch against a completed run.
        mismatch = PreviousRunEligibilityChecker(queries).check(
            run_id,
            expected_repository_id="00000000-0000-0000-0000-000000000000",
        )
        assert mismatch.eligible is False
        assert "repository_mismatch" in mismatch.reasons
    finally:
        store.close()


def test_planning_integration_no_change_and_source_change(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    try:
        base_manifest = manifest(
            entry("src/A.java", "a" * 64),
            entry("README.md", "b" * 64, kind=RepositoryFileKind.DOCUMENTATION, language=None),
            key="demo",
        )
        # seed_completed_assessment uses make_manifest by default; override with ours
        # via the helper's manifest parameter.
        repo_id, run_id, snapshot_id, _, _ = seed_completed_assessment(
            store,
            display_name="demo",
            manifest=base_manifest,
        )
        queries = KnowledgeQueryService(store)
        service = IncrementalPlanningService(query_service=queries)

        # No-change candidate.
        unchanged = candidate_state(base_manifest, key="demo")
        plan = service.create_plan(
            IncrementalPlanningRequest(
                repository_identifier=repo_id,
                previous_run_id=run_id,
                candidate=unchanged,
            )
        )
        assert plan.mode is IncrementalPlanMode.NO_CHANGES
        assert plan.full_rebuild_required is False
        assert plan.previous_run_id == run_id
        assert plan.previous_snapshot_id == snapshot_id

        # Documentation-only change.
        doc_changed = candidate_state(
            manifest(
                entry("src/A.java", "a" * 64),
                entry(
                    "README.md",
                    "c" * 64,
                    kind=RepositoryFileKind.DOCUMENTATION,
                    language=None,
                ),
                key="demo",
            ),
            key="demo",
        )
        doc_plan = service.create_plan(
            IncrementalPlanningRequest(
                repository_identifier=repo_id,
                previous_run_id=run_id,
                candidate=doc_changed,
            )
        )
        assert doc_plan.mode is IncrementalPlanMode.METADATA_ONLY
        assert doc_plan.full_rebuild_required is False

        # Dependency manifest change → full rebuild.
        with_pom = candidate_state(
            manifest(
                entry("src/A.java", "a" * 64),
                entry(
                    "README.md",
                    "b" * 64,
                    kind=RepositoryFileKind.DOCUMENTATION,
                    language=None,
                ),
                entry(
                    "pom.xml",
                    "d" * 64,
                    kind=RepositoryFileKind.DEPENDENCY_MANIFEST,
                    language=None,
                ),
                key="demo",
            ),
            key="demo",
        )
        dep_plan = service.create_plan(
            IncrementalPlanningRequest(
                repository_identifier=repo_id,
                previous_run_id=run_id,
                candidate=with_pom,
            )
        )
        assert dep_plan.mode is IncrementalPlanMode.FULL_REBUILD
        assert dep_plan.full_rebuild_required is True

        # Engine fingerprint mismatch → full rebuild.
        engine_changed = candidate_state(base_manifest, key="demo")
        engine_changed = engine_changed.model_copy(
            update={
                "engine": engine_changed.engine.model_copy(update={"scanner": "scanner:other-v99"})
            }
        )
        engine_plan = service.create_plan(
            IncrementalPlanningRequest(
                repository_identifier=repo_id,
                previous_run_id=run_id,
                candidate=engine_changed,
            )
        )
        assert engine_plan.full_rebuild_required is True
        assert "scanner_mismatch" in engine_plan.full_rebuild_reasons

        # Confirm planning did not create a new completed assessment run.
        runs = queries.list_assessment_runs(repo_id)
        completed = [item for item in runs if item.status is AssessmentRunStatus.COMPLETED]
        assert len(completed) == 1
    finally:
        store.close()


def test_service_does_not_read_reports(tmp_path: Path) -> None:
    queries = MagicMock()
    queries.resolve_repository.return_value = MagicMock(
        repository_id="repo-1",
        canonical_key="demo",
        display_name="demo",
    )
    queries.get_latest_completed_run.return_value = None
    service = IncrementalPlanningService(query_service=queries)
    plan = service.create_plan(
        IncrementalPlanningRequest(
            repository_identifier="demo",
            candidate=candidate_state(make_manifest(key="demo")),
        )
    )
    assert plan.mode is IncrementalPlanMode.FULL_REBUILD
    # Planning must not consult report artifacts.
    assert "report.json" not in plan.model_dump_json()
    assert "report.html" not in plan.model_dump_json()
    queries.get_latest_completed_run.assert_called()
    del tmp_path


def test_missing_required_artifact_ineligible(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    try:
        repo_id, run_id, _, _, _ = seed_completed_assessment(store)
        # Drop recommendations artifact linkage by completing a new run without artifacts.
        incomplete = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version=__version__,
            ruleset_version=RULESET_VERSION,
        )
        # Mark completed without attaching required artifacts (if API allows).
        # Prefer simulating missing kinds via summary mock if complete_run requires artifacts.
        queries = KnowledgeQueryService(store)
        run = queries.get_assessment_run(run_id)
        assert KnowledgeArtifactKind.FINDINGS in run.artifact_kinds

        # Use mock for missing artifact case.
        fake = MagicMock()
        fake.get_assessment_run.return_value = run.model_copy(
            update={
                "artifact_kinds": (
                    KnowledgeArtifactKind.REPOSITORY_GRAPH,
                    KnowledgeArtifactKind.ENGINEERING_KNOWLEDGE_GRAPH,
                    KnowledgeArtifactKind.KNOWLEDGE_BINDINGS,
                    KnowledgeArtifactKind.ASSESSMENT_GRAPH,
                    KnowledgeArtifactKind.FINDINGS,
                )
            }
        )
        fake.get_repository_snapshot.return_value = queries.get_repository_snapshot(
            run.snapshot_id  # type: ignore[arg-type]
        )
        result = PreviousRunEligibilityChecker(fake).check(
            run_id,
            expected_repository_id=repo_id,
            branch="main",
        )
        assert result.eligible is False
        assert any("missing_artifact:recommendations" in reason for reason in result.reasons)
        del incomplete
    finally:
        store.close()
