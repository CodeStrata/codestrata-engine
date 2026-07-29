"""SQLite-backed repository snapshot store."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.knowledge.errors import (
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    RepositoryNotFoundError,
)
from codestrata.application.knowledge.models import (
    KnowledgeArtifactKind,
    RepositorySnapshotRecord,
)
from codestrata.domain.repository import RepositoryManifest
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory
from codestrata.domain.repository.manifests import REPOSITORY_MANIFEST_VERSION
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.timeutil import (
    format_timestamp,
    normalize_branch_key,
    parse_timestamp,
)
from codestrata.services.artifact_serialization import repository_manifest_payload


class SqliteSnapshotStore:
    """Persist immutable repository manifests as content-addressed snapshots."""

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

    def create_or_get_snapshot(
        self,
        *,
        repository_id: str,
        branch: str | None,
        revision_type: RepositoryRevisionType,
        revision_id: str,
        manifest: RepositoryManifest,
        content_fingerprint: str,
        captured_at: datetime | None = None,
    ) -> RepositorySnapshotRecord:
        repo = self._connection.execute(
            "SELECT repository_id FROM repositories WHERE repository_id = ?",
            (repository_id,),
        ).fetchone()
        if repo is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")

        computed = RepositoryFingerprintFactory.from_manifest(manifest)
        expected = f"{computed.algorithm.value}:{computed.digest}"
        if content_fingerprint != expected and content_fingerprint != computed.digest:
            raise KnowledgeStoreError(
                "Manifest content fingerprint mismatch; refusing to persist snapshot"
            )
        fingerprint = expected

        branch_key = normalize_branch_key(branch)
        existing = self._connection.execute(
            """
            SELECT * FROM repository_snapshots
            WHERE repository_id = ? AND branch_name = ? AND content_fingerprint = ?
            """,
            (repository_id, branch_key, fingerprint),
        ).fetchone()
        if existing is not None:
            return self._row_to_record(existing)

        payload = repository_manifest_payload(manifest)
        blob_ref, blob_hash = self._blobs.write_json_blob(
            KnowledgeArtifactKind.REPOSITORY_MANIFEST,
            payload,
        )
        now = self._now()
        captured = captured_at or now
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise KnowledgeStoreError("captured_at must be timezone-aware")
        snapshot_id = self._id_factory()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                INSERT INTO repository_snapshots(
                    snapshot_id, repository_id, branch_name, revision_type, revision_id,
                    content_fingerprint, manifest_schema_version, manifest_blob_ref,
                    manifest_blob_hash, captured_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    repository_id,
                    branch_key,
                    revision_type.value,
                    revision_id,
                    fingerprint,
                    manifest.manifest_version or REPOSITORY_MANIFEST_VERSION,
                    blob_ref,
                    blob_hash,
                    format_timestamp(captured),
                    format_timestamp(now),
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError:
            self._connection.execute("ROLLBACK")
            # Concurrent insert of same uniqueness key — reuse winner.
            row = self._connection.execute(
                """
                SELECT * FROM repository_snapshots
                WHERE repository_id = ? AND branch_name = ? AND content_fingerprint = ?
                """,
                (repository_id, branch_key, fingerprint),
            ).fetchone()
            if row is None:
                raise KnowledgeStoreError(
                    "Snapshot insert conflict without reusable row"
                ) from None
            return self._row_to_record(row)
        except sqlite3.Error as error:
            self._connection.execute("ROLLBACK")
            raise KnowledgeStoreError("Failed to persist repository snapshot") from error

        created = self.get_snapshot(snapshot_id)
        if created is None:
            raise KnowledgeStoreError("Snapshot was not created")
        return created

    def get_snapshot(self, snapshot_id: str) -> RepositorySnapshotRecord | None:
        row = self._connection.execute(
            "SELECT * FROM repository_snapshots WHERE snapshot_id = ?",
            (snapshot_id.strip(),),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_latest_snapshot(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> RepositorySnapshotRecord | None:
        if branch is None:
            row = self._connection.execute(
                """
                SELECT * FROM repository_snapshots
                WHERE repository_id = ?
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (repository_id,),
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT * FROM repository_snapshots
                WHERE repository_id = ? AND branch_name = ?
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (repository_id, normalize_branch_key(branch)),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def get_manifest(self, snapshot_id: str) -> RepositoryManifest:
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise KnowledgeStoreError(f"Snapshot not found: {snapshot_id}")
        payload = self._blobs.read_json_blob(
            snapshot.manifest_blob_ref,
            expected_hash=snapshot.manifest_blob_hash,
        )
        if not isinstance(payload, dict):
            raise KnowledgeStoreCorruptionError("Manifest blob must be a JSON object")
        try:
            return RepositoryManifest.model_validate(payload)
        except Exception as error:  # noqa: BLE001
            raise KnowledgeStoreCorruptionError(
                f"Unable to validate repository manifest for snapshot {snapshot_id}"
            ) from error

    def list_snapshots(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
        limit: int = 50,
    ) -> tuple[RepositorySnapshotRecord, ...]:
        capped = max(1, min(int(limit), 500))
        if branch is None:
            rows = self._connection.execute(
                """
                SELECT * FROM repository_snapshots
                WHERE repository_id = ?
                ORDER BY captured_at DESC, created_at DESC
                LIMIT ?
                """,
                (repository_id, capped),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM repository_snapshots
                WHERE repository_id = ? AND branch_name = ?
                ORDER BY captured_at DESC, created_at DESC
                LIMIT ?
                """,
                (repository_id, normalize_branch_key(branch), capped),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KnowledgeStoreError("clock must return timezone-aware UTC datetimes")
        return value.astimezone(UTC)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> RepositorySnapshotRecord:
        branch_name = str(row["branch_name"])
        return RepositorySnapshotRecord(
            snapshot_id=str(row["snapshot_id"]),
            repository_id=str(row["repository_id"]),
            branch=None if branch_name == "" else branch_name,
            revision_type=RepositoryRevisionType(str(row["revision_type"])),
            revision_id=str(row["revision_id"]),
            content_fingerprint=str(row["content_fingerprint"]),
            manifest_schema_version=str(row["manifest_schema_version"]),
            manifest_blob_ref=str(row["manifest_blob_ref"]),
            manifest_blob_hash=str(row["manifest_blob_hash"]),
            captured_at=parse_timestamp(str(row["captured_at"])),
            created_at=parse_timestamp(str(row["created_at"])),
        )
