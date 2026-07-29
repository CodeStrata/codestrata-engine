"""Repository lock foundation tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.knowledge import RepositoryLockTimeoutError
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore


def test_lock_acquire_and_release(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo_id = str(uuid4())
    with store.repository_lock(repo_id, timeout_seconds=1.0):
        pass
    with store.repository_lock(repo_id, timeout_seconds=1.0):
        pass
    store.close()


def test_second_acquisition_times_out(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo_id = str(uuid4())
    with store.repository_lock(repo_id, timeout_seconds=1.0):
        with pytest.raises(RepositoryLockTimeoutError):
            with store.repository_lock(repo_id, timeout_seconds=0.2):
                pass
    store.close()


def test_lock_released_after_exception(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo_id = str(uuid4())
    with pytest.raises(RuntimeError, match="inside lock"):
        with store.repository_lock(repo_id, timeout_seconds=1.0):
            raise RuntimeError("inside lock")
    with store.repository_lock(repo_id, timeout_seconds=1.0):
        pass
    store.close()


def test_different_repository_ids_do_not_block(tmp_path: Path) -> None:
    store = SqliteKnowledgeStore(tmp_path / "knowledge")
    store.open()
    a = str(uuid4())
    b = str(uuid4())
    with store.repository_lock(a, timeout_seconds=1.0):
        with store.repository_lock(b, timeout_seconds=1.0):
            pass
    store.close()
