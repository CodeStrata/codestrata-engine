"""Schema v2 migration and snapshot/run persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.knowledge import (
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    KnowledgeStoreVersionError,
    RepositoryIdentityHints,
)
from codestrata.domain.repository import (
    FileFingerprint,
    RepositoryFileEntry,
    RepositoryFingerprintFactory,
    RepositoryIdentity,
    RepositoryManifest,
    RepositoryPath,
    RepositoryRevision,
    RepositoryRevisionType,
    RepositorySourceType,
)
from codestrata.domain.repository.enums import HashAlgorithm, RepositoryFileKind
from codestrata.infrastructure.knowledge_store import CURRENT_SCHEMA_VERSION, SqliteKnowledgeStore
from codestrata.infrastructure.knowledge_store.defaults import SCHEMA_VERSION_KEY


def _manifest(*, key: str = "demo", digest: str = "a" * 64) -> RepositoryManifest:
    return RepositoryManifest(
        identity=RepositoryIdentity(
            repository_key=key,
            source_type=RepositorySourceType.LOCAL,
            display_name=key,
        ),
        revision=RepositoryRevision(
            revision_id="working-tree",
            revision_type=RepositoryRevisionType.WORKING_TREE,
        ),
        files=(
            RepositoryFileEntry(
                path=RepositoryPath("README.md"),
                file_kind=RepositoryFileKind.DOCUMENTATION,
                size_bytes=12,
                fingerprint=FileFingerprint(algorithm=HashAlgorithm.SHA256, digest=digest),
            ),
        ),
    )


def test_schema_migrates_to_current_and_preserves_v1_rows(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    store = SqliteKnowledgeStore(store_dir)
    store.open()
    assert store.schema_version == CURRENT_SCHEMA_VERSION == 3
    record = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.GITHUB,
            display_name="app",
            source_location="https://github.com/acme/app.git",
        )
    )
    store.close()

    with SqliteKnowledgeStore(store_dir) as store:
        assert store.schema_version == CURRENT_SCHEMA_VERSION
        assert store.registry.get_by_id(record.repository_id) is not None
        assert store.snapshots.list_snapshots(record.repository_id) == ()
        columns = {
            str(row[1])
            for row in store._connection.execute(  # noqa: SLF001
                "PRAGMA table_info(assessment_runs)"
            ).fetchall()
        }
        assert "codestrata_version" in columns
        assert "aimf_version" not in columns


def test_future_schema_version_rejected(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    with SqliteKnowledgeStore(store_dir) as store:
        store._connection.execute(  # noqa: SLF001
            "UPDATE schema_metadata SET value = ? WHERE key = ?",
            ("99", SCHEMA_VERSION_KEY),
        )
    with pytest.raises(KnowledgeStoreVersionError):
        SqliteKnowledgeStore(store_dir).open()


def test_snapshot_reuse_and_manifest_round_trip(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.LOCAL,
                display_name="demo",
                local_path=tmp_path / "demo",
            )
        )
        (tmp_path / "demo").mkdir()
        manifest = _manifest()
        fp = RepositoryFingerprintFactory.from_manifest(manifest)
        fingerprint = f"{fp.algorithm.value}:{fp.digest}"
        first = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.COMMIT,
            revision_id="abc123",
            manifest=manifest,
            content_fingerprint=fingerprint,
        )
        second = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.COMMIT,
            revision_id="abc123",
            manifest=manifest,
            content_fingerprint=fingerprint,
        )
        assert first.snapshot_id == second.snapshot_id
        restored = store.snapshots.get_manifest(first.snapshot_id)
        assert restored.model_dump(mode="json") == manifest.model_dump(mode="json")
        raw = store.database_path.read_bytes()
        assert b"class Secret" not in raw


def test_run_lifecycle_and_artifacts(tmp_path: Path) -> None:
    from codestrata.application.knowledge.models import StagedKnowledgeArtifact

    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        repo = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="app",
                source_location="https://github.com/acme/lifecycle.git",
            )
        )
        run = store.runs.create_run(
            repository_id=repo.repository_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        assert run.status is AssessmentRunStatus.RUNNING
        assert store.runs.get_latest_completed_run(repo.repository_id) is None

        manifest = _manifest(digest="b" * 64)
        fp = RepositoryFingerprintFactory.from_manifest(manifest)
        fingerprint = f"{fp.algorithm.value}:{fp.digest}"
        snapshot = store.snapshots.create_or_get_snapshot(
            repository_id=repo.repository_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint,
        )
        completed = store.runs.complete_run(
            run.run_id,
            snapshot_id=snapshot.snapshot_id,
            artifacts=[
                StagedKnowledgeArtifact(
                    artifact_kind=KnowledgeArtifactKind.FINDINGS,
                    schema_version="1.0.0",
                    payload={"finding_count": 0, "findings": []},
                    snapshot_id=snapshot.snapshot_id,
                )
            ],
        )
        assert completed.status is AssessmentRunStatus.COMPLETED
        latest = store.runs.get_latest_completed_run(repo.repository_id)
        assert latest is not None
        assert latest.run_id == run.run_id
        payload = store.runs.read_artifact_payload(run.run_id, KnowledgeArtifactKind.FINDINGS)
        assert payload["finding_count"] == 0


def test_stale_running_aborted(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge", stale_run_seconds=0) as store:
        repo = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="app",
                source_location="https://github.com/acme/stale.git",
            )
        )
        run = store.runs.create_run(
            repository_id=repo.repository_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        # Force started_at into the past.
        store._connection.execute(  # noqa: SLF001
            "UPDATE assessment_runs SET started_at = ? WHERE run_id = ?",
            ("2020-01-01T00:00:00Z", run.run_id),
        )
        aborted = store.runs.abort_stale_runs(older_than_seconds=1)
        assert any(item.run_id == run.run_id for item in aborted)
        assert store.runs.get_run(run.run_id).status is AssessmentRunStatus.ABORTED
        assert store.runs.get_latest_completed_run(repo.repository_id) is None


def test_legacy_alias_conflict_does_not_merge_github_repos(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        a = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="app",
                source_location="https://github.com/one/app.git",
                existing_repository_key="app",
            )
        )
        b = store.registry.register_or_resolve(
            RepositoryIdentityHints(
                source_type=RepositorySourceType.GITHUB,
                display_name="app",
                source_location="https://github.com/two/app.git",
                existing_repository_key="app",
            )
        )
        assert a.repository_id != b.repository_id
