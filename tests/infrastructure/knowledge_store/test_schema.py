"""SQLite knowledge store schema and lifecycle tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from codestrata.application.knowledge import KnowledgeStoreVersionError
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.infrastructure.knowledge_store.defaults import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
)
from codestrata.infrastructure.knowledge_store.sqlite import migrations as migrations_module


def test_empty_directory_initializes_current_schema(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    with SqliteKnowledgeStore(store_dir) as store:
        assert store.schema_version == CURRENT_SCHEMA_VERSION
        assert store.database_path.is_file()
        assert store.locks_directory.is_dir()
        assert store.blobs_directory.is_dir()
        assert store.tmp_directory.is_dir()
        row = store._connection.execute(  # noqa: SLF001 - test introspection
            "SELECT value FROM schema_metadata WHERE key = ?",
            (SCHEMA_VERSION_KEY,),
        ).fetchone()
        assert row is not None
        assert int(row[0]) == CURRENT_SCHEMA_VERSION
        fk = store._connection.execute("PRAGMA foreign_keys").fetchone()  # noqa: SLF001
        assert fk is not None
        assert int(fk[0]) == 1


def test_reopening_store_is_safe(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    with SqliteKnowledgeStore(store_dir) as store:
        assert store.schema_version == CURRENT_SCHEMA_VERSION
    with SqliteKnowledgeStore(store_dir) as store:
        assert store.schema_version == CURRENT_SCHEMA_VERSION
        assert store.registry.list_repositories() == ()


def test_unsupported_future_schema_version_fails(tmp_path: Path) -> None:
    store_dir = tmp_path / "knowledge"
    with SqliteKnowledgeStore(store_dir) as store:
        store._connection.execute(  # noqa: SLF001
            "UPDATE schema_metadata SET value = ? WHERE key = ?",
            ("99", SCHEMA_VERSION_KEY),
        )
    with pytest.raises(KnowledgeStoreVersionError, match="newer than supported"):
        SqliteKnowledgeStore(store_dir).open()


def test_partial_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store_dir = tmp_path / "knowledge"

    def boom(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        raise RuntimeError("migration interrupted")

    monkeypatch.setattr(migrations_module, "migrate_to_v1", boom)
    store = SqliteKnowledgeStore(store_dir)
    with pytest.raises(RuntimeError, match="migration interrupted"):
        store.open()

    # Restore real migration and open successfully — prior partial work rolled back.
    monkeypatch.undo()
    with SqliteKnowledgeStore(store_dir) as store:
        assert store.schema_version == CURRENT_SCHEMA_VERSION
        tables = {
            row[0]
            for row in store._connection.execute(  # noqa: SLF001
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "repositories" in tables
        assert "repository_snapshots" in tables
        assert "assessment_runs" in tables
        assert "knowledge_artifacts" in tables
