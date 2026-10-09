"""File-backed immutable repository snapshot store."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.knowledge.errors import (
    KnowledgeStoreCorruptionError,
    KnowledgeStoreError,
    RepositoryNotFoundError,
)
from codestrata.application.knowledge.models import KnowledgeArtifactKind, RepositorySnapshotRecord
from codestrata.domain.repository import RepositoryManifest
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.domain.repository.fingerprints import RepositoryFingerprintFactory
from codestrata.domain.repository.manifests import REPOSITORY_MANIFEST_VERSION
from codestrata.infrastructure.knowledge_store.file.codec import (
    snapshot_document,
    snapshot_from_document,
)
from codestrata.infrastructure.knowledge_store.file.indexes import iter_repository_ids
from codestrata.infrastructure.knowledge_store.file.layout import FileStorePaths, require_safe_id
from codestrata.infrastructure.knowledge_store.file.registry import FileRepositoryRegistry
from codestrata.infrastructure.knowledge_store.io import atomic_write_json, read_json_file
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.timeutil import normalize_branch_key
from codestrata.services.artifact_serialization import repository_manifest_payload


class FileSnapshotStore:
    """Persist immutable repository manifests as content-addressed snapshots."""

    def __init__(
        self,
        paths: FileStorePaths,
        blobs: BlobStore,
        registry: FileRepositoryRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._paths = paths
        self._blobs = blobs
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._on_change = on_change or (lambda: None)

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
        if self._registry.get_by_id(repository_id) is None:
            raise RepositoryNotFoundError(f"Repository not found: {repository_id}")

        computed = RepositoryFingerprintFactory.from_manifest(manifest)
        expected = f"{computed.algorithm.value}:{computed.digest}"
        if content_fingerprint != expected and content_fingerprint != computed.digest:
            raise KnowledgeStoreError(
                "Manifest content fingerprint mismatch; refusing to persist snapshot"
            )
        fingerprint = expected
        branch_key = normalize_branch_key(branch)
        existing = self._find_by_fingerprint(repository_id, branch_key, fingerprint)
        if existing is not None:
            return existing

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
        record = RepositorySnapshotRecord(
            snapshot_id=snapshot_id,
            repository_id=repository_id,
            branch=None if branch_key == "" else branch_key,
            revision_type=revision_type,
            revision_id=revision_id,
            content_fingerprint=fingerprint,
            manifest_schema_version=manifest.manifest_version or REPOSITORY_MANIFEST_VERSION,
            manifest_blob_ref=blob_ref,
            manifest_blob_hash=blob_hash,
            captured_at=captured,
            created_at=now,
        )
        destination = self._paths.snapshot_manifest(repository_id, snapshot_id)
        if destination.exists():
            raise KnowledgeStoreError("Concurrent snapshot output collision")
        self._paths.snapshots_dir(repository_id).mkdir(parents=True, exist_ok=True)
        racing = self._find_by_fingerprint(repository_id, branch_key, fingerprint)
        if racing is not None:
            return racing
        atomic_write_json(destination, snapshot_document(record), tmp_directory=self._paths.tmp)
        self._on_change()
        created = self.get_snapshot(snapshot_id)
        if created is None:
            raise KnowledgeStoreError("Snapshot was not created")
        return created

    def get_snapshot(self, snapshot_id: str) -> RepositorySnapshotRecord | None:
        wanted = require_safe_id(snapshot_id.strip(), field="snapshot_id")
        for repository_id in iter_repository_ids(self._paths):
            path = self._paths.snapshot_manifest(repository_id, wanted)
            if not path.is_file() or path.is_symlink():
                continue
            try:
                return snapshot_from_document(read_json_file(path, root=self._paths.root))
            except (KnowledgeStoreError, KeyError, ValueError, TypeError):
                raise KnowledgeStoreCorruptionError(
                    f"Corrupt snapshot manifest: {wanted}"
                ) from None
        return None

    def get_latest_snapshot(
        self,
        repository_id: str,
        *,
        branch: str | None = None,
    ) -> RepositorySnapshotRecord | None:
        items = self.list_snapshots(repository_id, branch=branch, limit=1)
        return items[0] if items else None

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
        directory = self._paths.snapshots_dir(repository_id)
        if not directory.is_dir():
            return ()
        records: list[RepositorySnapshotRecord] = []
        for path in directory.glob("*.json"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                record = snapshot_from_document(read_json_file(path, root=self._paths.root))
            except (KnowledgeStoreError, KeyError, ValueError, TypeError):
                continue
            if branch is not None and normalize_branch_key(record.branch) != normalize_branch_key(
                branch
            ):
                continue
            records.append(record)
        records.sort(key=lambda item: (item.captured_at, item.created_at), reverse=True)
        return tuple(records[:capped])

    def _find_by_fingerprint(
        self,
        repository_id: str,
        branch_key: str,
        fingerprint: str,
    ) -> RepositorySnapshotRecord | None:
        for record in self.list_snapshots(repository_id, limit=500):
            if (
                normalize_branch_key(record.branch) == branch_key
                and record.content_fingerprint == fingerprint
            ):
                return record
        return None

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise KnowledgeStoreError("clock must return timezone-aware UTC datetimes")
        return value.astimezone(UTC)
