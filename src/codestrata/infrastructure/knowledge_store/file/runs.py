"""File-backed assessment run store with atomic completion."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from codestrata.application.knowledge.errors import (
    KnowledgeArtifactNotFoundError,
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    RepositoryNotFoundError,
)
from codestrata.application.knowledge.models import (
    AssessmentRunRecord,
    AssessmentRunStatus,
    KnowledgeArtifactKind,
    KnowledgeArtifactRecord,
    StagedKnowledgeArtifact,
)
from codestrata.infrastructure.knowledge_store.file.codec import (
    artifacts_document,
    artifacts_from_document,
    run_document,
    run_from_document,
)
from codestrata.infrastructure.knowledge_store.file.indexes import iter_repository_ids
from codestrata.infrastructure.knowledge_store.file.layout import (
    RUN_MANIFEST_NAME,
    FileStorePaths,
    require_safe_id,
)
from codestrata.infrastructure.knowledge_store.file.registry import FileRepositoryRegistry
from codestrata.infrastructure.knowledge_store.file.snapshots import FileSnapshotStore
from codestrata.infrastructure.knowledge_store.io import atomic_write_json, read_json_file
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.timeutil import normalize_branch_key


class FileAssessmentRunStore:
    """Persist assessment run lifecycle; completed manifests appear only after finalize."""

    def __init__(
        self,
        paths: FileStorePaths,
        blobs: BlobStore,
        registry: FileRepositoryRegistry,
        snapshots: FileSnapshotStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._paths = paths
        self._blobs = blobs
        self._registry = registry
        self._snapshots = snapshots
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._on_change = on_change or (lambda: None)

    def create_run(
        self,
        *,
        repository_id: str,
        assessment_mode: str,
        codestrata_version: str,
        ruleset_version: str,
        request_fingerprint: str | None = None,
        invalidation_fingerprint: str | None = None,
    ) -> AssessmentRunRecord:
        if self._registry.get_by_id(repository_id) is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")
        run_id = self._id_factory()
        destination = self._paths.run_dir(repository_id, run_id)
        try:
            destination.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise KnowledgeStoreError("Concurrent run output collision") from None
        now = self._now()
        record = AssessmentRunRecord(
            run_id=run_id,
            repository_id=repository_id,
            snapshot_id=None,
            status=AssessmentRunStatus.RUNNING,
            assessment_mode=assessment_mode,
            codestrata_version=codestrata_version,
            ruleset_version=ruleset_version,
            started_at=now,
            request_fingerprint=request_fingerprint,
            invalidation_fingerprint=invalidation_fingerprint,
        )
        self._write_run(record)
        self._on_change()
        created = self.get_run(run_id)
        if created is None:
            raise KnowledgeStoreError("Assessment run was not created")
        return created

    def attach_snapshot(self, run_id: str, snapshot_id: str) -> AssessmentRunRecord:
        run = self._require_run(run_id)
        if run.status is not AssessmentRunStatus.RUNNING:
            raise KnowledgeStoreError(f"Cannot attach snapshot to run in status {run.status.value}")
        if self._snapshots.get_snapshot(snapshot_id) is None:
            raise KnowledgeStoreError(f"Snapshot not found: {snapshot_id}")
        updated = run.model_copy(update={"snapshot_id": snapshot_id})
        self._write_run(updated)
        self._on_change()
        attached = self.get_run(run_id)
        if attached is None:
            raise KnowledgeStoreError("Assessment run missing after attach")
        return attached

    def complete_run(
        self,
        run_id: str,
        *,
        snapshot_id: str,
        artifacts: Sequence[StagedKnowledgeArtifact],
    ) -> AssessmentRunRecord:
        run = self._require_run(run_id)
        if run.status is not AssessmentRunStatus.RUNNING:
            raise KnowledgeStoreError(f"Cannot complete run in status {run.status.value}")
        if self._snapshots.get_snapshot(snapshot_id) is None:
            raise KnowledgeStoreError(f"Snapshot not found: {snapshot_id}")

        now = self._now()
        staged: list[KnowledgeArtifactRecord] = []
        try:
            for artifact in artifacts:
                blob_ref, blob_hash = self._blobs.write_json_blob(
                    artifact.artifact_kind,
                    artifact.payload,
                )
                self._blobs.read_json_blob(blob_ref, expected_hash=blob_hash)
                staged.append(
                    KnowledgeArtifactRecord(
                        artifact_id=self._id_factory(),
                        run_id=run_id,
                        snapshot_id=artifact.snapshot_id or snapshot_id,
                        artifact_kind=artifact.artifact_kind,
                        schema_version=artifact.schema_version,
                        blob_ref=blob_ref,
                        blob_hash=blob_hash,
                        source_fingerprint=artifact.source_fingerprint,
                        created_at=now,
                    )
                )
        except KnowledgeStoreError:
            raise
        except Exception as error:  # noqa: BLE001
            raise KnowledgeStoreError("Failed to stage knowledge artifacts") from error

        # Artifacts first, then completed run.json. Readers never see completed
        # without a finalized artifacts manifest.
        atomic_write_json(
            self._paths.artifacts_manifest(run.repository_id, run_id),
            artifacts_document(staged),
            tmp_directory=self._paths.tmp,
        )
        completed = run.model_copy(
            update={
                "snapshot_id": snapshot_id,
                "status": AssessmentRunStatus.COMPLETED,
                "completed_at": now,
                "failed_at": None,
                "error_code": None,
                "error_message": None,
            }
        )
        self._write_run(completed)
        self._on_change()
        loaded = self.get_run(run_id)
        if loaded is None or loaded.status is not AssessmentRunStatus.COMPLETED:
            raise KnowledgeStoreError("Assessment run was not marked completed")
        return loaded

    def fail_run(
        self,
        run_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> AssessmentRunRecord:
        run = self._require_run(run_id)
        if run.status is not AssessmentRunStatus.RUNNING:
            return run
        now = self._now()
        failed = run.model_copy(
            update={
                "status": AssessmentRunStatus.FAILED,
                "failed_at": now,
                "error_code": error_code.strip()[:128] or "KNOWLEDGE_PERSISTENCE_FAILED",
                "error_message": error_message.strip()[:2000],
            }
        )
        self._write_run(failed)
        self._on_change()
        updated = self.get_run(run_id)
        if updated is None:
            raise KnowledgeStoreError("Assessment run missing after fail")
        return updated

    def abort_stale_runs(self, *, older_than_seconds: float) -> tuple[AssessmentRunRecord, ...]:
        cutoff = self._now() - timedelta(seconds=max(0.0, older_than_seconds))
        aborted: list[AssessmentRunRecord] = []
        now = self._now()
        for run in self._all_runs():
            if run.status is not AssessmentRunStatus.RUNNING:
                continue
            if run.started_at >= cutoff:
                continue
            updated = run.model_copy(
                update={
                    "status": AssessmentRunStatus.ABORTED,
                    "failed_at": now,
                    "error_code": "STALE_RUN",
                    "error_message": "Assessment run aborted after exceeding stale threshold",
                }
            )
            self._write_run(updated)
            loaded = self.get_run(run.run_id)
            if loaded is not None:
                aborted.append(loaded)
        if aborted:
            self._on_change()
        return tuple(aborted)

    def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        wanted = require_safe_id(run_id.strip(), field="run_id")
        for repository_id in iter_repository_ids(self._paths):
            path = self._paths.run_manifest(repository_id, wanted)
            if not path.is_file() or path.is_symlink():
                continue
            try:
                run = run_from_document(read_json_file(path, root=self._paths.root))
            except (KnowledgeStoreError, KeyError, ValueError, TypeError):
                raise KnowledgeStoreCorruptionError(f"Corrupt run manifest: {wanted}") from None
            if run.status is AssessmentRunStatus.COMPLETED:
                artifacts_path = self._paths.artifacts_manifest(repository_id, wanted)
                if not artifacts_path.is_file():
                    # Incomplete finalize must not look completed.
                    return run.model_copy(update={"status": AssessmentRunStatus.RUNNING})
            return run
        return None

    def get_latest_completed_run(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> AssessmentRunRecord | None:
        completed = [
            run
            for run in self.list_runs(
                repository_id,
                limit=500,
                status=AssessmentRunStatus.COMPLETED,
            )
        ]
        if branch is not None:
            wanted = normalize_branch_key(branch)
            filtered: list[AssessmentRunRecord] = []
            for run in completed:
                if run.snapshot_id is None:
                    continue
                snapshot = self._snapshots.get_snapshot(run.snapshot_id)
                if snapshot is None:
                    continue
                if normalize_branch_key(snapshot.branch) == wanted:
                    filtered.append(run)
            completed = filtered
        completed.sort(
            key=lambda item: (item.completed_at or item.started_at, item.started_at),
            reverse=True,
        )
        return completed[0] if completed else None

    def list_runs(
        self,
        repository_id: str,
        *,
        limit: int = 50,
        status: AssessmentRunStatus | None = None,
    ) -> tuple[AssessmentRunRecord, ...]:
        capped = max(1, min(int(limit), 500))
        runs_dir = self._paths.runs_dir(repository_id)
        if not runs_dir.is_dir():
            return ()
        records: list[AssessmentRunRecord] = []
        for run_dir in runs_dir.iterdir():
            run_file = run_dir / RUN_MANIFEST_NAME
            if not run_file.is_file() or run_file.is_symlink():
                continue
            try:
                run = run_from_document(read_json_file(run_file, root=self._paths.root))
            except (KnowledgeStoreError, KeyError, ValueError, TypeError):
                continue
            if run.status is AssessmentRunStatus.COMPLETED:
                artifacts_path = self._paths.artifacts_manifest(repository_id, run.run_id)
                if not artifacts_path.is_file():
                    run = run.model_copy(update={"status": AssessmentRunStatus.RUNNING})
            if status is not None and run.status is not status:
                continue
            records.append(run)
        records.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(records[:capped])

    def list_artifacts(self, run_id: str) -> tuple[KnowledgeArtifactRecord, ...]:
        run = self.get_run(run_id)
        if run is None or run.status is not AssessmentRunStatus.COMPLETED:
            return ()
        path = self._paths.artifacts_manifest(run.repository_id, run_id)
        if not path.is_file():
            return ()
        try:
            records = artifacts_from_document(read_json_file(path, root=self._paths.root))
        except (KnowledgeStoreError, KeyError, ValueError, TypeError) as error:
            raise KnowledgeStoreCorruptionError(
                f"Corrupt artifacts manifest for {run_id}"
            ) from error
        return tuple(sorted(records, key=lambda item: item.artifact_kind.value))

    def get_artifact(
        self,
        run_id: str,
        artifact_kind: KnowledgeArtifactKind,
    ) -> KnowledgeArtifactRecord | None:
        for record in self.list_artifacts(run_id):
            if record.artifact_kind is artifact_kind:
                return record
        return None

    def read_artifact_payload(
        self,
        run_id: str,
        artifact_kind: KnowledgeArtifactKind,
    ) -> Mapping[str, Any] | list[Any]:
        artifact = self.get_artifact(run_id, artifact_kind)
        if artifact is None:
            raise KnowledgeArtifactNotFoundError(
                f"Artifact {artifact_kind.value} not found for run {run_id}"
            )
        payload = self._blobs.read_json_blob(
            artifact.blob_ref,
            expected_hash=artifact.blob_hash,
        )
        if not isinstance(payload, (dict, list)):
            raise KnowledgeStoreCorruptionError(
                f"Artifact payload must be object or array: {artifact_kind.value}"
            )
        return payload

    def _all_runs(self) -> tuple[AssessmentRunRecord, ...]:
        found: list[AssessmentRunRecord] = []
        for repository_id in iter_repository_ids(self._paths):
            found.extend(self.list_runs(repository_id, limit=500))
        return tuple(found)

    def _write_run(self, record: AssessmentRunRecord) -> None:
        self._paths.run_dir(record.repository_id, record.run_id).mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self._paths.run_manifest(record.repository_id, record.run_id),
            run_document(record),
            tmp_directory=self._paths.tmp,
        )

    def _require_run(self, run_id: str) -> AssessmentRunRecord:
        run = self.get_run(run_id)
        if run is None:
            raise KnowledgeStoreError(f"Assessment run not found: {run_id}")
        return run

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KnowledgeStoreError("clock must return timezone-aware UTC datetimes")
        return value.astimezone(UTC)
