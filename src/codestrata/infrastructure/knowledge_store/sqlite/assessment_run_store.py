"""SQLite-backed assessment run store."""

from __future__ import annotations

import sqlite3
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
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.timeutil import (
    format_timestamp,
    normalize_branch_key,
    parse_timestamp,
)


class SqliteAssessmentRunStore:
    """Persist assessment run lifecycle and linked immutable artifacts."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        blob_store: BlobStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._connection = connection
        self._blobs = blob_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

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
        if self._connection.execute(
            "SELECT 1 FROM repositories WHERE repository_id = ?",
            (repository_id,),
        ).fetchone() is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")

        run_id = self._id_factory()
        now = self._now()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                INSERT INTO assessment_runs(
                    run_id, repository_id, snapshot_id, status, assessment_mode,
                    codestrata_version, ruleset_version, request_fingerprint,
                    invalidation_fingerprint, started_at, completed_at, failed_at,
                    error_code, error_message
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    run_id,
                    repository_id,
                    AssessmentRunStatus.RUNNING.value,
                    assessment_mode,
                    codestrata_version,
                    ruleset_version,
                    request_fingerprint,
                    invalidation_fingerprint,
                    format_timestamp(now),
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.Error as error:
            self._connection.execute("ROLLBACK")
            raise KnowledgeStoreError("Failed to create assessment run") from error
        created = self.get_run(run_id)
        if created is None:
            raise KnowledgeStoreError("Assessment run was not created")
        return created

    def attach_snapshot(self, run_id: str, snapshot_id: str) -> AssessmentRunRecord:
        run = self._require_run(run_id)
        if run.status is not AssessmentRunStatus.RUNNING:
            raise KnowledgeStoreError(
                f"Cannot attach snapshot to run in status {run.status.value}"
            )
        if self._connection.execute(
            "SELECT 1 FROM repository_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone() is None:
            raise KnowledgeStoreError(f"Snapshot not found: {snapshot_id}")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "UPDATE assessment_runs SET snapshot_id = ? WHERE run_id = ?",
                (snapshot_id, run_id),
            )
            self._connection.execute("COMMIT")
        except sqlite3.Error as error:
            self._connection.execute("ROLLBACK")
            raise KnowledgeStoreError("Failed to attach snapshot to run") from error
        updated = self.get_run(run_id)
        if updated is None:
            raise KnowledgeStoreError("Assessment run missing after attach")
        return updated

    def complete_run(
        self,
        run_id: str,
        *,
        snapshot_id: str,
        artifacts: Sequence[StagedKnowledgeArtifact],
    ) -> AssessmentRunRecord:
        run = self._require_run(run_id)
        if run.status is not AssessmentRunStatus.RUNNING:
            raise KnowledgeStoreError(
                f"Cannot complete run in status {run.status.value}"
            )
        if self._connection.execute(
            "SELECT 1 FROM repository_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone() is None:
            raise KnowledgeStoreError(f"Snapshot not found: {snapshot_id}")

        staged_rows: list[tuple[str, StagedKnowledgeArtifact, str, str]] = []
        try:
            for artifact in artifacts:
                blob_ref, blob_hash = self._blobs.write_json_blob(
                    artifact.artifact_kind,
                    artifact.payload,
                )
                # Verify immediately before commit.
                self._blobs.read_json_blob(blob_ref, expected_hash=blob_hash)
                staged_rows.append(
                    (self._id_factory(), artifact, blob_ref, blob_hash)
                )
        except KnowledgeStoreError:
            raise
        except Exception as error:  # noqa: BLE001
            raise KnowledgeStoreError("Failed to stage knowledge artifacts") from error

        now = self._now()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                UPDATE assessment_runs
                SET snapshot_id = ?, status = ?, completed_at = ?,
                    failed_at = NULL, error_code = NULL, error_message = NULL
                WHERE run_id = ? AND status = ?
                """,
                (
                    snapshot_id,
                    AssessmentRunStatus.COMPLETED.value,
                    format_timestamp(now),
                    run_id,
                    AssessmentRunStatus.RUNNING.value,
                ),
            )
            if self._connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise KnowledgeStoreError("Assessment run was not in running status")
            for artifact_id, artifact, blob_ref, blob_hash in staged_rows:
                self._connection.execute(
                    """
                    INSERT INTO knowledge_artifacts(
                        artifact_id, run_id, snapshot_id, artifact_kind, schema_version,
                        blob_ref, blob_hash, source_fingerprint, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        run_id,
                        artifact.snapshot_id or snapshot_id,
                        artifact.artifact_kind.value,
                        artifact.schema_version,
                        blob_ref,
                        blob_hash,
                        artifact.source_fingerprint,
                        format_timestamp(now),
                    ),
                )
            self._connection.execute("COMMIT")
        except KnowledgeStoreError:
            self._connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            self._connection.execute("ROLLBACK")
            raise KnowledgeStoreError("Failed to complete assessment run") from error

        completed = self.get_run(run_id)
        if completed is None or completed.status is not AssessmentRunStatus.COMPLETED:
            raise KnowledgeStoreError("Assessment run was not marked completed")
        return completed

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
        message = error_message.strip()[:2000]
        code = error_code.strip()[:128] or "KNOWLEDGE_PERSISTENCE_FAILED"
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                UPDATE assessment_runs
                SET status = ?, failed_at = ?, error_code = ?, error_message = ?
                WHERE run_id = ? AND status = ?
                """,
                (
                    AssessmentRunStatus.FAILED.value,
                    format_timestamp(now),
                    code,
                    message,
                    run_id,
                    AssessmentRunStatus.RUNNING.value,
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.Error as error:
            self._connection.execute("ROLLBACK")
            raise KnowledgeStoreError("Failed to mark assessment run failed") from error
        updated = self.get_run(run_id)
        if updated is None:
            raise KnowledgeStoreError("Assessment run missing after fail")
        return updated

    def abort_stale_runs(
        self,
        *,
        older_than_seconds: float,
    ) -> tuple[AssessmentRunRecord, ...]:
        cutoff = self._now() - timedelta(seconds=max(0.0, older_than_seconds))
        cutoff_text = format_timestamp(cutoff)
        rows = self._connection.execute(
            """
            SELECT run_id FROM assessment_runs
            WHERE status = ? AND started_at < ?
            """,
            (AssessmentRunStatus.RUNNING.value, cutoff_text),
        ).fetchall()
        aborted: list[AssessmentRunRecord] = []
        now = self._now()
        for row in rows:
            run_id = str(row["run_id"])
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    UPDATE assessment_runs
                    SET status = ?, failed_at = ?, error_code = ?, error_message = ?
                    WHERE run_id = ? AND status = ?
                    """,
                    (
                        AssessmentRunStatus.ABORTED.value,
                        format_timestamp(now),
                        "STALE_RUN",
                        "Assessment run aborted after exceeding stale threshold",
                        run_id,
                        AssessmentRunStatus.RUNNING.value,
                    ),
                )
                self._connection.execute("COMMIT")
            except sqlite3.Error:
                self._connection.execute("ROLLBACK")
                continue
            updated = self.get_run(run_id)
            if updated is not None:
                aborted.append(updated)
        return tuple(aborted)

    def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        row = self._connection.execute(
            "SELECT * FROM assessment_runs WHERE run_id = ?",
            (run_id.strip(),),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_latest_completed_run(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> AssessmentRunRecord | None:
        if branch is None:
            row = self._connection.execute(
                """
                SELECT * FROM assessment_runs
                WHERE repository_id = ? AND status = ?
                ORDER BY completed_at DESC, started_at DESC
                LIMIT 1
                """,
                (repository_id, AssessmentRunStatus.COMPLETED.value),
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT r.* FROM assessment_runs r
                JOIN repository_snapshots s ON s.snapshot_id = r.snapshot_id
                WHERE r.repository_id = ? AND r.status = ? AND s.branch_name = ?
                ORDER BY r.completed_at DESC, r.started_at DESC
                LIMIT 1
                """,
                (
                    repository_id,
                    AssessmentRunStatus.COMPLETED.value,
                    normalize_branch_key(branch),
                ),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_runs(
        self,
        repository_id: str,
        *,
        limit: int = 50,
        status: AssessmentRunStatus | None = None,
    ) -> tuple[AssessmentRunRecord, ...]:
        capped = max(1, min(int(limit), 500))
        if status is None:
            rows = self._connection.execute(
                """
                SELECT * FROM assessment_runs
                WHERE repository_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (repository_id, capped),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM assessment_runs
                WHERE repository_id = ? AND status = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (repository_id, status.value, capped),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def list_artifacts(self, run_id: str) -> tuple[KnowledgeArtifactRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM knowledge_artifacts
            WHERE run_id = ?
            ORDER BY artifact_kind ASC
            """,
            (run_id.strip(),),
        ).fetchall()
        return tuple(self._artifact_row(row) for row in rows)

    def get_artifact(
        self,
        run_id: str,
        artifact_kind: KnowledgeArtifactKind,
    ) -> KnowledgeArtifactRecord | None:
        row = self._connection.execute(
            """
            SELECT * FROM knowledge_artifacts
            WHERE run_id = ? AND artifact_kind = ?
            """,
            (run_id.strip(), artifact_kind.value),
        ).fetchone()
        return self._artifact_row(row) if row is not None else None

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

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AssessmentRunRecord:
        return AssessmentRunRecord(
            run_id=str(row["run_id"]),
            repository_id=str(row["repository_id"]),
            snapshot_id=None if row["snapshot_id"] is None else str(row["snapshot_id"]),
            status=AssessmentRunStatus(str(row["status"])),
            assessment_mode=str(row["assessment_mode"]),
            codestrata_version=str(row["codestrata_version"]),
            ruleset_version=str(row["ruleset_version"]),
            started_at=parse_timestamp(str(row["started_at"])),
            completed_at=(
                None
                if row["completed_at"] is None
                else parse_timestamp(str(row["completed_at"]))
            ),
            failed_at=(
                None if row["failed_at"] is None else parse_timestamp(str(row["failed_at"]))
            ),
            error_code=None if row["error_code"] is None else str(row["error_code"]),
            error_message=(
                None if row["error_message"] is None else str(row["error_message"])
            ),
            request_fingerprint=(
                None
                if row["request_fingerprint"] is None
                else str(row["request_fingerprint"])
            ),
            invalidation_fingerprint=(
                None
                if row["invalidation_fingerprint"] is None
                else str(row["invalidation_fingerprint"])
            ),
        )

    @staticmethod
    def _artifact_row(row: sqlite3.Row) -> KnowledgeArtifactRecord:
        return KnowledgeArtifactRecord(
            artifact_id=str(row["artifact_id"]),
            run_id=str(row["run_id"]),
            snapshot_id=None if row["snapshot_id"] is None else str(row["snapshot_id"]),
            artifact_kind=KnowledgeArtifactKind(str(row["artifact_kind"])),
            schema_version=str(row["schema_version"]),
            blob_ref=str(row["blob_ref"]),
            blob_hash=str(row["blob_hash"]),
            source_fingerprint=(
                None
                if row["source_fingerprint"] is None
                else str(row["source_fingerprint"])
            ),
            created_at=parse_timestamp(str(row["created_at"])),
        )
