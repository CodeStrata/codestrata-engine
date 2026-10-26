"""File-backed engineering knowledge store (production adapter)."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from codestrata.application.knowledge.errors import KnowledgeStoreError, KnowledgeStoreVersionError
from codestrata.infrastructure.knowledge_store.defaults import (
    DEFAULT_STALE_RUN_SECONDS,
    default_knowledge_directory,
)
from codestrata.infrastructure.knowledge_store.file.codec import STORE_MANIFEST_SCHEMA
from codestrata.infrastructure.knowledge_store.file.health import (
    FileKnowledgeHealth,
    collect_health,
)
from codestrata.infrastructure.knowledge_store.file.indexes import rebuild_derived_indexes
from codestrata.infrastructure.knowledge_store.file.layout import (
    FILE_STORE_FORMAT,
    FILE_STORE_SCHEMA_VERSION,
    FileStorePaths,
)
from codestrata.infrastructure.knowledge_store.file.registry import FileRepositoryRegistry
from codestrata.infrastructure.knowledge_store.file.retention import (
    assert_retention_protected,
    cleanup_tmp_and_staging,
    list_unrelated_top_level,
)
from codestrata.infrastructure.knowledge_store.file.runs import FileAssessmentRunStore
from codestrata.infrastructure.knowledge_store.file.snapshots import FileSnapshotStore
from codestrata.infrastructure.knowledge_store.io import (
    DEFAULT_MAX_JSON_BYTES,
    atomic_write_json,
    read_json_file,
)
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.locking import repository_file_lock


class FileKnowledgeStore:
    """Local JSON/JSONL knowledge store. Production runtime does not open SQLite.

    Layout under ``directory``::

        store.json
        repositories/{id}/repository.json
        repositories/{id}/aliases.json
        repositories/{id}/snapshots/{snapshot_id}.json
        repositories/{id}/runs/{run_id}/run.json
        repositories/{id}/runs/{run_id}/artifacts.json
        blobs/{manifests,graphs,findings,recommendations,ai}/
        indexes/*.jsonl          (derived; rebuilt from valid manifests)
        locks/
        tmp/
        staging/
    """

    def __init__(
        self,
        directory: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        stale_run_seconds: float = DEFAULT_STALE_RUN_SECONDS,
        max_json_bytes: int | None = None,
    ) -> None:
        self._directory = (directory or default_knowledge_directory()).expanduser()
        self._clock = clock
        self._id_factory = id_factory
        self._stale_run_seconds = stale_run_seconds
        self._max_json_bytes = (
            DEFAULT_MAX_JSON_BYTES if max_json_bytes is None else int(max_json_bytes)
        )
        if self._max_json_bytes < 1:
            raise ValueError("max_json_bytes must be positive")
        self._paths = FileStorePaths(self._directory, max_json_bytes=self._max_json_bytes)
        self._open = False
        self._registry: FileRepositoryRegistry | None = None
        self._snapshots: FileSnapshotStore | None = None
        self._runs: FileAssessmentRunStore | None = None
        self._blobs: BlobStore | None = None

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def locks_directory(self) -> Path:
        return self._paths.locks

    @property
    def blobs_directory(self) -> Path:
        return self._paths.blobs

    @property
    def tmp_directory(self) -> Path:
        return self._paths.tmp

    @property
    def schema_version(self) -> int:
        if not self._open:
            raise KnowledgeStoreError("Knowledge store is not open")
        return FILE_STORE_SCHEMA_VERSION

    @property
    def registry(self) -> FileRepositoryRegistry:
        if self._registry is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._registry

    @property
    def snapshots(self) -> FileSnapshotStore:
        if self._snapshots is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._snapshots

    @property
    def runs(self) -> FileAssessmentRunStore:
        if self._runs is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._runs

    def open(self) -> None:
        if self._open:
            return
        try:
            self._prepare_directories()
            self._load_or_create_store_manifest()
            blobs = BlobStore(
                self._directory,
                self._paths.blobs,
                self._paths.tmp,
                max_bytes=self._max_json_bytes,
            )
            blobs.cleanup_tmp()
            cleanup_tmp_and_staging(self._paths)

            def on_change() -> None:
                rebuild_derived_indexes(self._paths, tmp_directory=self._paths.tmp)

            registry = FileRepositoryRegistry(
                self._paths,
                clock=self._clock,
                id_factory=self._id_factory,
                on_change=on_change,
            )
            snapshots = FileSnapshotStore(
                self._paths,
                blobs,
                registry,
                clock=self._clock,
                id_factory=self._id_factory,
                on_change=on_change,
            )
            runs = FileAssessmentRunStore(
                self._paths,
                blobs,
                registry,
                snapshots,
                clock=self._clock,
                id_factory=self._id_factory,
                on_change=on_change,
            )
            self._blobs = blobs
            self._registry = registry
            self._snapshots = snapshots
            self._runs = runs
            self._open = True
            rebuild_derived_indexes(self._paths, tmp_directory=self._paths.tmp)
            self._runs.abort_stale_runs(older_than_seconds=self._stale_run_seconds)
        except KnowledgeStoreVersionError:
            self.close()
            raise
        except KnowledgeStoreError:
            self.close()
            raise
        except OSError as error:
            self.close()
            raise KnowledgeStoreError(
                f"Failed to prepare knowledge store directory: {self._directory}"
            ) from error

    def close(self) -> None:
        self._open = False
        self._registry = None
        self._snapshots = None
        self._runs = None
        self._blobs = None

    def __enter__(self) -> FileKnowledgeStore:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    @contextmanager
    def repository_lock(
        self,
        repository_id: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> Iterator[None]:
        self.locks_directory.mkdir(parents=True, exist_ok=True)
        with repository_file_lock(
            self.locks_directory,
            repository_id,
            timeout_seconds=timeout_seconds,
        ):
            yield

    def health(self) -> FileKnowledgeHealth:
        """Local status without an HTTP service or database."""

        version = FILE_STORE_SCHEMA_VERSION if self._open else 0
        return collect_health(
            self._paths,
            is_open=self._open,
            schema_version=version,
            runs=self._runs,
        )

    def rebuild_indexes(self) -> int:
        if not self._open:
            raise KnowledgeStoreError("Knowledge store is not open")
        return rebuild_derived_indexes(self._paths, tmp_directory=self._paths.tmp)

    def retain(
        self,
        *,
        source_root: Path | None = None,
        baseline_paths: tuple[Path, ...] = (),
    ) -> int:
        """Cleanup tmp/staging only. Protects source, baselines, and unrelated files."""

        unrelated = list_unrelated_top_level(self._paths)
        assert_retention_protected(
            self._paths,
            source_root=source_root,
            baseline_paths=baseline_paths,
            unrelated_files=(),
        )
        # Unrelated top-level files are recorded, never deleted.
        del unrelated
        return cleanup_tmp_and_staging(self._paths)

    def _prepare_directories(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        for path in (
            self._paths.repositories,
            self._paths.indexes,
            self._paths.staging,
            self._paths.locks,
            self._paths.blobs,
            self._paths.tmp,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for sub in ("manifests", "graphs", "findings", "recommendations", "ai"):
            (self._paths.blobs / sub).mkdir(parents=True, exist_ok=True)
        self._chmod_private(self._directory)

    def _load_or_create_store_manifest(self) -> None:
        manifest = self._paths.store_manifest
        if not manifest.exists():
            atomic_write_json(
                manifest,
                {
                    "schema": STORE_MANIFEST_SCHEMA,
                    "format": FILE_STORE_FORMAT,
                    "schema_version": FILE_STORE_SCHEMA_VERSION,
                    "destructive_auto_migration": False,
                },
                tmp_directory=self._paths.tmp,
                max_bytes=self._paths.max_json_bytes,
            )
            return
        document = read_json_file(
            manifest,
            root=self._directory,
            max_bytes=self._paths.max_json_bytes,
        )
        try:
            version = int(document["schema_version"])
        except (KeyError, TypeError, ValueError) as error:
            raise KnowledgeStoreVersionError("Invalid file knowledge store manifest") from error
        if version > FILE_STORE_SCHEMA_VERSION:
            raise KnowledgeStoreVersionError(
                f"File knowledge store schema {version} is newer than supported "
                f"{FILE_STORE_SCHEMA_VERSION}"
            )
        if version < FILE_STORE_SCHEMA_VERSION:
            raise KnowledgeStoreVersionError(
                "Older file knowledge store schema requires an explicit maintainer "
                "migration; refusing destructive auto-migration"
            )

    @staticmethod
    def _chmod_private(path: Path) -> None:
        try:
            os.chmod(path, stat.S_IRWXU)
        except OSError:
            pass


def open_file_knowledge_store(
    directory: Path | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
    stale_run_seconds: float = DEFAULT_STALE_RUN_SECONDS,
) -> FileKnowledgeStore:
    store = FileKnowledgeStore(
        directory,
        clock=clock,
        id_factory=id_factory,
        stale_run_seconds=stale_run_seconds,
    )
    store.open()
    return store
