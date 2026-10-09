"""Repository lock foundation tests."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from codestrata.application.knowledge import RepositoryLockTimeoutError
from codestrata.infrastructure.knowledge_store.sqlite import locking
from codestrata.infrastructure.knowledge_store.sqlite.store import SqliteKnowledgeStore


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


def test_stale_lock_is_removed_when_pid_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_path = tmp_path / "stale.lock"
    lock_path.write_text("424242", encoding="utf-8")
    monkeypatch.setattr(locking, "_process_exists", lambda _pid: False)

    assert locking._remove_stale_lock(lock_path) is True
    assert not lock_path.exists()


def test_active_pid_lock_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "active.lock"
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(locking, "_process_exists", lambda _pid: True)

    assert locking._remove_stale_lock(lock_path) is False
    assert lock_path.exists()


def test_process_exists_current_pid_and_missing_pid() -> None:
    assert locking._process_exists(os.getpid()) is True
    assert locking._process_exists(2_000_000_000) is False


def test_isolation_overwrites_host_knowledge_directory(tmp_path: Path) -> None:
    from tests.conftest import (
        KNOWLEDGE_DIRECTORY_ENV,
        LOCK_TIMEOUT_ENV,
        apply_test_knowledge_isolation,
    )

    host = str(tmp_path / "host-knowledge")
    isolated = tmp_path / "isolated-knowledge"
    environ = {
        KNOWLEDGE_DIRECTORY_ENV: host,
        LOCK_TIMEOUT_ENV: "3600",
    }
    previous = apply_test_knowledge_isolation(environ, isolated)
    assert environ[KNOWLEDGE_DIRECTORY_ENV] == str(isolated)
    assert environ[LOCK_TIMEOUT_ENV] == "2"
    assert previous[KNOWLEDGE_DIRECTORY_ENV] == host
    assert previous[LOCK_TIMEOUT_ENV] == "3600"


def test_repository_file_lock_respects_env_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    monkeypatch.setenv("CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS", "0.2")
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    repo_id = str(uuid4())
    started = time.monotonic()
    with locking.repository_file_lock(lock_dir, repo_id, timeout_seconds=3600.0):
        with pytest.raises(RepositoryLockTimeoutError):
            with locking.repository_file_lock(lock_dir, repo_id, timeout_seconds=3600.0):
                pass
    assert time.monotonic() - started < 2.0


def test_lock_timeout_cap_prevents_hour_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    from codestrata.application.knowledge.lock_policy import knowledge_lock_timeout_seconds

    monkeypatch.delenv("CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS", raising=False)
    assert knowledge_lock_timeout_seconds(3600.0) == 3600.0
    monkeypatch.setenv("CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS", "2")
    assert knowledge_lock_timeout_seconds(3600.0) == 2.0
    assert knowledge_lock_timeout_seconds(0.2) == 0.2


def test_assessment_session_contended_lock_fails_quickly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    from codestrata.application.knowledge.errors import RepositoryLockTimeoutError
    from codestrata.application.knowledge.session import AssessmentKnowledgeSession
    from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore
    from codestrata.models import Repository
    from codestrata.reporting import AssessmentMode

    monkeypatch.delenv("CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS", raising=False)
    (tmp_path / "repo").mkdir()
    store = FileKnowledgeStore(tmp_path / "knowledge")
    store.open()
    repo = Repository(name="lock-demo", path=tmp_path / "repo")
    first = AssessmentKnowledgeSession(
        store=store,
        repository=repo,
        mode=AssessmentMode.DETERMINISTIC,
        lock_timeout_seconds=2.0,
    )
    first.__enter__()
    try:
        started = time.monotonic()
        with pytest.raises(RepositoryLockTimeoutError):
            with AssessmentKnowledgeSession(
                store=store,
                repository=repo,
                mode=AssessmentMode.DETERMINISTIC,
                lock_timeout_seconds=0.2,
            ):
                pass
        assert time.monotonic() - started < 2.0
    finally:
        first.__exit__(None, None, None)
        store.close()


def test_default_factory_uses_isolated_knowledge_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from codestrata.infrastructure.knowledge_store.defaults import KNOWLEDGE_DIRECTORY_ENV
    from codestrata.infrastructure.knowledge_store.factory import create_knowledge_store

    isolated = tmp_path / "isolated-default"
    monkeypatch.setenv(KNOWLEDGE_DIRECTORY_ENV, str(isolated))
    store = create_knowledge_store()
    assert store._directory.resolve() == isolated.resolve()  # noqa: SLF001


def test_stale_windows_style_lock_recovers_without_os_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_path = tmp_path / "legacy.lock"
    lock_path.write_text("424242", encoding="utf-8")

    def boom(_pid: int, _signal: int = 0) -> None:
        raise OSError(87, "The parameter is incorrect")

    monkeypatch.setattr(locking.os, "kill", boom)
    monkeypatch.setattr(locking, "_windows_process_exists", lambda _pid: False)
    monkeypatch.setattr(locking.os, "name", "posix")
    assert locking._remove_stale_lock(lock_path) is True
    assert not lock_path.exists()


def test_sibling_threads_wait_through_the_suite_lock_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same-process waiters must not trip the 2s file-lock cap while a sibling holds it."""

    import threading

    monkeypatch.setenv("CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS", "0.05")
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    finished: list[str] = []

    def hold() -> None:
        try:
            with locking.repository_file_lock(lock_dir, "derived-indexes", timeout_seconds=30.0):
                entered.set()
                assert release.wait(timeout=2.0)
                finished.append("holder")
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    def wait_for_lock(name: str) -> None:
        try:
            with locking.repository_file_lock(lock_dir, "derived-indexes", timeout_seconds=30.0):
                finished.append(name)
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(timeout=2.0)
    waiters = [threading.Thread(target=wait_for_lock, args=(f"w{index}",)) for index in range(4)]
    for waiter in waiters:
        waiter.start()
    # Longer than the 0.05s env cap. Waiters must still be queued, not timed out.
    threading.Event().wait(0.2)
    assert errors == []
    assert finished == []
    release.set()
    holder.join(timeout=2.0)
    for waiter in waiters:
        waiter.join(timeout=2.0)
    assert errors == []
    assert holder.is_alive() is False
    assert all(not waiter.is_alive() for waiter in waiters)
    assert set(finished) == {"holder", "w0", "w1", "w2", "w3"}
