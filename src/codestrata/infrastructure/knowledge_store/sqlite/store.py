"""SQLite knowledge store lifecycle."""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from codestrata.application.knowledge.errors import KnowledgeStoreError, KnowledgeStoreVersionError
from codestrata.infrastructure.knowledge_store.defaults import (
    BLOBS_DIRECTORY_NAME,
    CURRENT_SCHEMA_VERSION,
    DATABASE_FILENAME,
    DEFAULT_BUSY_TIMEOUT_MS,
    DEFAULT_KNOWLEDGE_DIRECTORY,
    DEFAULT_STALE_RUN_SECONDS,
    LOCKS_DIRECTORY_NAME,
    TMP_DIRECTORY_NAME,
)
from codestrata.infrastructure.knowledge_store.sqlite.assessment_run_store import (
    SqliteAssessmentRunStore,
)
from codestrata.infrastructure.knowledge_store.sqlite.blobs import BlobStore
from codestrata.infrastructure.knowledge_store.sqlite.locking import repository_file_lock
from codestrata.infrastructure.knowledge_store.sqlite.migrations import apply_migrations
from codestrata.infrastructure.knowledge_store.sqlite.repository_registry import (
    SqliteRepositoryRegistry,
)
from codestrata.infrastructure.knowledge_store.sqlite.snapshot_store import SqliteSnapshotStore


class SqliteKnowledgeStore:
    """Local SQLite-backed engineering knowledge store.

    Layout under ``directory``::

        knowledge.sqlite
        locks/
        blobs/{manifests,graphs,findings,recommendations,ai}/
        tmp/
    """

    def __init__(
        self,
        directory: Path | None = None,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        stale_run_seconds: float = DEFAULT_STALE_RUN_SECONDS,
    ) -> None:
        self._directory = (directory or DEFAULT_KNOWLEDGE_DIRECTORY).expanduser()
        self._busy_timeout_ms = busy_timeout_ms
        self._clock = clock
        self._id_factory = id_factory
        self._stale_run_seconds = stale_run_seconds
        self._connection: sqlite3.Connection | None = None
        self._registry: SqliteRepositoryRegistry | None = None
        self._snapshots: SqliteSnapshotStore | None = None
        self._runs: SqliteAssessmentRunStore | None = None
        self._blobs: BlobStore | None = None

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def database_path(self) -> Path:
        return self._directory / DATABASE_FILENAME

    @property
    def locks_directory(self) -> Path:
        return self._directory / LOCKS_DIRECTORY_NAME

    @property
    def blobs_directory(self) -> Path:
        return self._directory / BLOBS_DIRECTORY_NAME

    @property
    def tmp_directory(self) -> Path:
        return self._directory / TMP_DIRECTORY_NAME

    @property
    def registry(self) -> SqliteRepositoryRegistry:
        if self._registry is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._registry

    @property
    def snapshots(self) -> SqliteSnapshotStore:
        if self._snapshots is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._snapshots

    @property
    def runs(self) -> SqliteAssessmentRunStore:
        if self._runs is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        return self._runs

    @property
    def schema_version(self) -> int:
        if self._connection is None:
            raise KnowledgeStoreError("Knowledge store is not open")
        from codestrata.infrastructure.knowledge_store.sqlite.migrations import read_schema_version

        version = read_schema_version(self._connection)
        if version is None:
            raise KnowledgeStoreError("Knowledge store schema version is missing")
        return version

    def open(self) -> None:
        if self._connection is not None:
            return
        try:
            self._prepare_directories()
            connection = sqlite3.connect(
                self.database_path,
                timeout=max(self._busy_timeout_ms / 1000.0, 0.1),
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
            self._harden_permissions()
            try:
                connection.execute("BEGIN IMMEDIATE")
                apply_migrations(connection)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                connection.close()
                raise
            blobs = BlobStore(self._directory, self.blobs_directory, self.tmp_directory)
            blobs.cleanup_tmp()
            self._connection = connection
            self._blobs = blobs
            self._registry = SqliteRepositoryRegistry(
                connection,
                clock=self._clock,
                id_factory=self._id_factory,
            )
            self._snapshots = SqliteSnapshotStore(
                connection,
                blobs,
                clock=self._clock,
                id_factory=self._id_factory,
            )
            self._runs = SqliteAssessmentRunStore(
                connection,
                blobs,
                clock=self._clock,
                id_factory=self._id_factory,
            )
            self._runs.abort_stale_runs(older_than_seconds=self._stale_run_seconds)
        except KnowledgeStoreVersionError:
            raise
        except KnowledgeStoreError:
            raise
        except sqlite3.Error as error:
            raise KnowledgeStoreError(
                "Failed to open the engineering knowledge store"
            ) from error
        except OSError as error:
            raise KnowledgeStoreError(
                f"Failed to prepare knowledge store directory: {self._directory}"
            ) from error

    def close(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.close()
        finally:
            self._connection = None
            self._registry = None
            self._snapshots = None
            self._runs = None
            self._blobs = None

    def __enter__(self) -> SqliteKnowledgeStore:
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
        """Exclusive mutation lock for a repository."""

        self.locks_directory.mkdir(parents=True, exist_ok=True)
        with repository_file_lock(
            self.locks_directory,
            repository_id,
            timeout_seconds=timeout_seconds,
        ):
            yield

    def _prepare_directories(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        for path in (self.locks_directory, self.blobs_directory, self.tmp_directory):
            path.mkdir(parents=True, exist_ok=True)
        for sub in ("manifests", "graphs", "findings", "recommendations", "ai"):
            (self.blobs_directory / sub).mkdir(parents=True, exist_ok=True)
        self._chmod_private(self._directory)
        for path in (self.locks_directory, self.blobs_directory, self.tmp_directory):
            self._chmod_private(path)

    def _harden_permissions(self) -> None:
        if self.database_path.exists():
            try:
                os.chmod(self.database_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass

    @staticmethod
    def _chmod_private(path: Path) -> None:
        try:
            os.chmod(path, stat.S_IRWXU)
        except OSError:
            pass


def open_knowledge_store(
    directory: Path | None = None,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
    stale_run_seconds: float = DEFAULT_STALE_RUN_SECONDS,
) -> SqliteKnowledgeStore:
    """Convenience helper: open a store and return it (caller must close)."""

    store = SqliteKnowledgeStore(
        directory,
        busy_timeout_ms=busy_timeout_ms,
        clock=clock,
        id_factory=id_factory,
        stale_run_seconds=stale_run_seconds,
    )
    store.open()
    return store


SUPPORTED_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION
