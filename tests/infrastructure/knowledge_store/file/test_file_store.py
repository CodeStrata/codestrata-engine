"""E02.2 file knowledge store acceptance tests."""

from __future__ import annotations

import errno
import json
import os
import sqlite3
import threading
from pathlib import Path

import pytest
from tests.application.knowledge.queries.conftest_helpers import (
    fingerprint_for,
    make_manifest,
    seed_completed_assessment,
)

from codestrata.application.knowledge import local_knowledge_health
from codestrata.application.knowledge.errors import (
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    KnowledgeStoreVersionError,
)
from codestrata.application.knowledge.models import (
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    RepositoryIdentityHints,
    StagedKnowledgeArtifact,
)
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.application.knowledge.queries.streaming import stream_derived_index
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType
from codestrata.infrastructure.knowledge_store.defaults import DATABASE_FILENAME
from codestrata.infrastructure.knowledge_store.factory import create_knowledge_store
from codestrata.infrastructure.knowledge_store.file.layout import FILE_STORE_SCHEMA_VERSION
from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore
from codestrata.infrastructure.knowledge_store.io import (
    DEFAULT_MAX_JSON_BYTES,
    atomic_write_bytes,
    is_transient_io_error,
    read_json_file,
)


def _register(store: FileKnowledgeStore, tmp_path: Path, name: str = "demo") -> str:
    record = store.registry.register_or_resolve(
        RepositoryIdentityHints(
            source_type=RepositorySourceType.LOCAL,
            display_name=name,
            local_path=tmp_path / name,
        )
    )
    return record.repository_id


def test_factory_constructs_file_store_with_sqlite_connect_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("sqlite3.connect must not be used by the production factory")

    monkeypatch.setattr(sqlite3, "connect", blocked)
    store = create_knowledge_store(tmp_path / "knowledge")
    assert type(store).__name__ == "FileKnowledgeStore"
    store.open()
    try:
        assert store.schema_version == FILE_STORE_SCHEMA_VERSION
        health = local_knowledge_health(store)
        assert health["backend"] == "file"
        assert health["http_service"] is False
        assert health["database"] is False
        assert health["ok"] is True
    finally:
        store.close()


def test_assess_restart_open_evidence_and_compare_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("sqlite blocked")),
    )
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        repo_id, run_id, snap_a, finding, _rec = seed_completed_assessment(
            store,  # type: ignore[arg-type]
            display_name="offline",
            github_url="https://github.com/acme/offline.git",
        )
        second_manifest = make_manifest(
            key="offline",
            files=(("README.md", "b" * 64, 12), ("NEW.md", "c" * 64, 4)),
        )
        snap_b = store.snapshots.create_or_get_snapshot(
            repository_id=repo_id,
            branch="main",
            revision_type=RepositoryRevisionType.COMMIT,
            revision_id="def456",
            manifest=second_manifest,
            content_fingerprint=fingerprint_for(second_manifest),
        )
        service = KnowledgeQueryService(store)
        run = store.runs.get_run(run_id)
        assert run is not None
        assert run.status is AssessmentRunStatus.COMPLETED
        payload = store.runs.read_artifact_payload(run_id, KnowledgeArtifactKind.FINDINGS)
        assert finding.id in {item["id"] for item in payload["findings"]}
        comparison = service.compare_repository_snapshots(snap_a, snap_b.snapshot_id)
        assert comparison.counts.added == 1

    with FileKnowledgeStore(knowledge) as restarted:
        service = KnowledgeQueryService(restarted)
        summary = service.get_assessment_run(run_id)
        assert summary.status is AssessmentRunStatus.COMPLETED
        rows = list(stream_derived_index(restarted, "repositories.jsonl"))
        assert any(row["repository_id"] == repo_id for row in rows)


def test_interrupted_complete_does_not_expose_completed_snapshot(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id = _register(store, tmp_path)
        manifest = make_manifest()
        store.snapshots.create_or_get_snapshot(
            repository_id=repo_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint_for(manifest),
        )
        run = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        run_path = store.directory / "repositories" / repo_id / "runs" / run.run_id / "run.json"
        document = json.loads(run_path.read_text(encoding="utf-8"))
        document["status"] = "completed"
        run_path.write_text(json.dumps(document), encoding="utf-8")
        loaded = store.runs.get_run(run.run_id)
        assert loaded is not None
        assert loaded.status is AssessmentRunStatus.RUNNING
        assert store.runs.get_latest_completed_run(repo_id) is None
        assert store.runs.list_artifacts(run.run_id) == ()


def test_fail_run_never_signed_completed(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id = _register(store, tmp_path, "killed")
        run = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        failed = store.runs.fail_run(run.run_id, error_code="KILLED", error_message="interrupted")
        assert failed.status is AssessmentRunStatus.FAILED
        assert store.runs.get_latest_completed_run(repo_id) is None


def test_read_json_file_retries_transient_oserror_then_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "manifest.json"
    target.write_text('{"ok": true}\n', encoding="utf-8")
    attempts = {"count": 0}

    def boom(*_args: object, **_kwargs: object) -> bytes:
        attempts["count"] += 1
        raise OSError(errno.EACCES, "Sharing violation")

    monkeypatch.setattr(
        "codestrata.infrastructure.knowledge_store.io._read_file_bytes",
        boom,
    )
    with pytest.raises(KnowledgeStoreError, match="Failed to read JSON manifest"):
        read_json_file(target, root=tmp_path)
    assert attempts["count"] == 5
    assert is_transient_io_error(OSError(errno.EACCES, "Sharing violation"))


def test_read_json_file_succeeds_after_transient_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.infrastructure.knowledge_store import io as store_io

    target = tmp_path / "manifest.json"
    target.write_text('{"ok": true}\n', encoding="utf-8")
    attempts = {"count": 0}
    real_read = store_io._read_file_bytes

    def flaky(path: Path, *, max_bytes: int) -> bytes:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OSError(errno.EACCES, "Sharing violation")
        return real_read(path, max_bytes=max_bytes)

    monkeypatch.setattr(
        "codestrata.infrastructure.knowledge_store.io._read_file_bytes",
        flaky,
    )
    document = read_json_file(target, root=tmp_path)
    assert document == {"ok": True}
    assert attempts["count"] == 3


def test_concurrent_index_rebuilds_do_not_raise(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        _register(store, tmp_path, "rebuild")
        errors: list[BaseException] = []

        def rebuild() -> None:
            try:
                store.rebuild_indexes()
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=rebuild) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []
        assert store.rebuild_indexes() >= 1


def test_path_escape_rejected(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        with pytest.raises(KnowledgeStoreError, match="path-unsafe"):
            store.runs.get_run("../etc/passwd")
        with pytest.raises(KnowledgeStoreError, match="Illegal blob reference|path-unsafe|escapes"):
            assert store._blobs is not None  # noqa: SLF001
            store._blobs.read_json_blob("blobs/../store.json", expected_hash="00")  # noqa: SLF001


def test_memory_bound_rejects_oversized_payload(tmp_path: Path) -> None:
    target = tmp_path / "knowledge" / "too-big.json"
    target.parent.mkdir(parents=True)
    with pytest.raises(KnowledgeStoreError, match="memory/output bound"):
        atomic_write_bytes(
            target,
            b"x" * (DEFAULT_MAX_JSON_BYTES + 1),
            tmp_directory=tmp_path / "knowledge" / "tmp",
        )


def test_artifact_store_enforces_configured_read_write_bound(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge", max_json_bytes=2048) as store:
        repo_id = _register(store, tmp_path, "bounded")
        manifest = make_manifest()
        snapshot = store.snapshots.create_or_get_snapshot(
            repository_id=repo_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint_for(manifest),
        )
        run = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        with pytest.raises(KnowledgeStoreError, match="output bound"):
            store.runs.complete_run(
                run.run_id,
                snapshot_id=snapshot.snapshot_id,
                artifacts=[
                    StagedKnowledgeArtifact(
                        artifact_kind=KnowledgeArtifactKind.FINDINGS,
                        schema_version="1.0.0",
                        payload={"findings": [{"evidence": "x" * 4096}]},
                    )
                ],
            )
        assert store.runs.get_latest_completed_run(repo_id) is None


def test_corrupt_and_missing_blobs(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        _repo, run_id, _snap, _finding, _rec = seed_completed_assessment(
            store,  # type: ignore[arg-type]
            github_url="https://github.com/acme/corrupt.git",
        )
        artifact = store.runs.get_artifact(run_id, KnowledgeArtifactKind.FINDINGS)
        assert artifact is not None
        blob_path = store.directory / artifact.blob_ref
        blob_path.write_bytes(b'{"tampered": true}\n')
        with pytest.raises(KnowledgeStoreCorruptionError, match="hash mismatch"):
            store.runs.read_artifact_payload(run_id, KnowledgeArtifactKind.FINDINGS)
        blob_path.unlink()
        with pytest.raises(KnowledgeStoreCorruptionError, match="Missing blob"):
            store.runs.read_artifact_payload(run_id, KnowledgeArtifactKind.FINDINGS)


def test_rebuild_derived_indexes_from_valid_manifests(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        repo_id = _register(store, tmp_path, "indexed")
        (knowledge / "indexes" / "repositories.jsonl").write_text("{not-json\n", encoding="utf-8")
        rebuilt = store.rebuild_indexes()
        assert rebuilt >= 1
        rows = list(stream_derived_index(store, "repositories.jsonl"))
        assert any(row["repository_id"] == repo_id for row in rows)


def test_rebuild_truncates_derived_index_without_rejecting_manifests(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        repo_id = _register(store, tmp_path, "many-runs")
        identifiers = iter(f"run-{index:04d}" for index in range(501))
        store.runs._id_factory = lambda: next(identifiers)  # noqa: SLF001
        store.runs._on_change = lambda: None  # noqa: SLF001
        for _ in range(501):
            store.runs.create_run(
                repository_id=repo_id,
                assessment_mode="deterministic",
                codestrata_version="0.1.0",
                ruleset_version="1.2.0",
            )

        store.rebuild_indexes()
        rows = list(stream_derived_index(store, "runs.jsonl"))
        marker = json.loads(
            (knowledge / "indexes" / "rebuild-marker.json").read_text(encoding="utf-8")
        )
        assert len(rows) == 500
        assert marker["run_count"] == 501
        assert marker["run_indexed_count"] == 500
        assert marker["truncated"] is True


def test_no_destructive_auto_migration_of_sqlite(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    sqlite_path = knowledge / DATABASE_FILENAME
    sqlite_path.write_bytes(b"sqlite-placeholder")
    unrelated = knowledge / "notes-from-operator.txt"
    unrelated.write_text("keep me\n", encoding="utf-8")
    with FileKnowledgeStore(knowledge) as store:
        _register(store, tmp_path, "fresh")
        assert sqlite_path.read_bytes() == b"sqlite-placeholder"
        assert unrelated.read_text(encoding="utf-8") == "keep me\n"
        health = store.health()
        assert health.sqlite_present_untouched is True


def test_future_file_schema_rejected(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        store.directory.joinpath("store.json").write_text(
            json.dumps(
                {
                    "schema": "codestrata-file-knowledge-store:1",
                    "format": "codestrata-file-knowledge-store",
                    "schema_version": 99,
                    "destructive_auto_migration": False,
                }
            ),
            encoding="utf-8",
        )
    with pytest.raises(KnowledgeStoreVersionError, match="newer than supported"):
        FileKnowledgeStore(knowledge).open()


def test_concurrent_output_collision(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id = _register(store, tmp_path, "collide")
        fixed = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        def once() -> str:
            return fixed

        store._id_factory = once  # noqa: SLF001
        store.runs._id_factory = once  # noqa: SLF001
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def create() -> None:
            barrier.wait()
            try:
                store.runs.create_run(
                    repository_id=repo_id,
                    assessment_mode="deterministic",
                    codestrata_version="0.1.0",
                    ruleset_version="1.2.0",
                )
                outcomes.append("created")
            except KnowledgeStoreError as error:
                assert "collision" in str(error)
                outcomes.append("collision")

        threads = [threading.Thread(target=create) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(outcomes) == ["collision", "created"]
        assert len(
            store.runs.list_runs(
                repository_id=repo_id,
                limit=10,
            )
        ) == 1


def test_concurrent_readers_see_stable_completed_manifest(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        _repo, run_id, _snap, _finding, _rec = seed_completed_assessment(
            store,  # type: ignore[arg-type]
            github_url="https://github.com/acme/readers.git",
        )
        errors: list[BaseException] = []

        def reader() -> None:
            try:
                for _ in range(20):
                    run = store.runs.get_run(run_id)
                    assert run is not None
                    assert run.status is AssessmentRunStatus.COMPLETED
                    store.runs.read_artifact_payload(run_id, KnowledgeArtifactKind.FINDINGS)
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []


def test_disk_full_does_not_publish_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        repo_id = _register(store, tmp_path, "full")
        manifest = make_manifest()
        snapshot = store.snapshots.create_or_get_snapshot(
            repository_id=repo_id,
            branch="main",
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            manifest=manifest,
            content_fingerprint=fingerprint_for(manifest),
        )
        run = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        real_replace = os.replace

        def maybe_full(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            text = Path(src).read_text(encoding="utf-8")
            if str(dst).endswith("run.json") and "completed" in text:
                raise OSError(errno.ENOSPC, "No space left on device")
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", maybe_full)
        with pytest.raises(KnowledgeStoreError, match="Disk full"):
            store.runs.complete_run(
                run.run_id,
                snapshot_id=snapshot.snapshot_id,
                artifacts=[
                    StagedKnowledgeArtifact(
                        artifact_kind=KnowledgeArtifactKind.FINDINGS,
                        schema_version="1.0.0",
                        payload={"finding_count": 0, "findings": []},
                    )
                ],
            )
        loaded = store.runs.get_run(run.run_id)
        assert loaded is not None
        assert loaded.status is not AssessmentRunStatus.COMPLETED
        assert store.runs.get_latest_completed_run(repo_id) is None


def test_retention_protects_source_baselines_and_unrelated(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py").write_text("print(1)\n", encoding="utf-8")
    baseline = tmp_path / "supplied-baseline.json"
    baseline.write_text("{}\n", encoding="utf-8")
    knowledge = tmp_path / "knowledge"
    with FileKnowledgeStore(knowledge) as store:
        leftover = store.tmp_directory / "orphan.tmp"
        leftover.write_text("tmp\n", encoding="utf-8")
        unrelated = knowledge / "operator-notes.txt"
        unrelated.write_text("do not delete\n", encoding="utf-8")
        deleted = store.retain(source_root=source, baseline_paths=(baseline,))
        assert deleted >= 1
        assert not leftover.exists()
        assert (source / "main.py").read_text(encoding="utf-8") == "print(1)\n"
        assert baseline.read_text(encoding="utf-8") == "{}\n"
        assert unrelated.read_text(encoding="utf-8") == "do not delete\n"


def test_retention_refuses_protected_baseline_inside_cleanup_area(tmp_path: Path) -> None:
    with FileKnowledgeStore(tmp_path / "knowledge") as store:
        baseline = store.tmp_directory / "supplied-baseline.json"
        baseline.write_text("{}\n", encoding="utf-8")
        with pytest.raises(KnowledgeStoreError, match="protected path"):
            store.retain(baseline_paths=(baseline,))
        assert baseline.read_text(encoding="utf-8") == "{}\n"


def test_stale_running_aborted_not_completed(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    clock = {"now": datetime(2020, 1, 1, tzinfo=UTC)}

    def now() -> datetime:
        return clock["now"]

    with FileKnowledgeStore(tmp_path / "knowledge", clock=now, stale_run_seconds=0) as store:
        repo_id = _register(store, tmp_path, "stale")
        run = store.runs.create_run(
            repository_id=repo_id,
            assessment_mode="deterministic",
            codestrata_version="0.1.0",
            ruleset_version="1.2.0",
        )
        clock["now"] = datetime(2020, 1, 2, tzinfo=UTC)
        aborted = store.runs.abort_stale_runs(older_than_seconds=1)
        assert any(item.run_id == run.run_id for item in aborted)
        loaded = store.runs.get_run(run.run_id)
        assert loaded is not None
        assert loaded.status is AssessmentRunStatus.ABORTED
        assert store.runs.get_latest_completed_run(repo_id) is None
