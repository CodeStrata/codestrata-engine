"""Local repository mutation locks for the knowledge store.

Platform notes
--------------

* On Unix-like systems this uses ``fcntl.flock`` exclusive locks on a lock file
  under ``.codestrata/knowledge/locks/``.
* On platforms without ``fcntl`` (notably Windows), the implementation falls
  back to atomic lock-file creation (``O_CREAT | O_EXCL``) with PID metadata and
  stale-lock recovery. That fallback is best-effort for a single-machine MVP and
  is not a distributed lock.

Assessment execution does not acquire these locks yet (Increment 1 foundation
only).
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from re import sub

from codestrata.application.knowledge.errors import (
    KnowledgeStoreError,
    RepositoryLockTimeoutError,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - platform specific
    fcntl = None  # type: ignore[assignment]


def safe_lock_filename(repository_id: str) -> str:
    """Return a filesystem-safe lock file name for a repository ID."""

    compact = repository_id.strip().lower()
    if not compact:
        raise KnowledgeStoreError("repository_id is required for locking")
    cleaned = sub(r"[^a-z0-9._-]+", "-", compact).strip(".-") or "repository"
    return f"{cleaned}.lock"


@contextmanager
def repository_file_lock(
    locks_directory: Path,
    repository_id: str,
    *,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.05,
) -> Iterator[None]:
    """Acquire an exclusive local lock for ``repository_id``."""

    locks_directory.mkdir(parents=True, exist_ok=True)
    lock_path = locks_directory / safe_lock_filename(repository_id)
    deadline = time.monotonic() + max(0.0, timeout_seconds)

    if fcntl is not None:
        with _fcntl_lock(lock_path, deadline=deadline, poll_interval=poll_interval_seconds):
            yield
        return

    with _exclusive_create_lock(
        lock_path,
        deadline=deadline,
        poll_interval=poll_interval_seconds,
    ):
        yield


@contextmanager
def _fcntl_lock(
    lock_path: Path,
    *,
    deadline: float,
    poll_interval: float,
) -> Iterator[None]:
    assert fcntl is not None
    handle = open(lock_path, "a+", encoding="utf-8")  # noqa: SIM115
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RepositoryLockTimeoutError(
                        f"Timed out acquiring repository lock: {lock_path.name}"
                    ) from None
                time.sleep(poll_interval)
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def _exclusive_create_lock(
    lock_path: Path,
    *,
    deadline: float,
    poll_interval: float,
) -> Iterator[None]:
    """Best-effort exclusive lock via atomic file creation (non-fcntl platforms)."""

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            if _remove_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise RepositoryLockTimeoutError(
                    f"Timed out acquiring repository lock: {lock_path.name}"
                ) from None
            time.sleep(poll_interval)
    try:
        yield
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _remove_stale_lock(lock_path: Path) -> bool:
    """Remove a lock file if its PID is missing; return True when removed."""

    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        pid = int(raw)
    except (OSError, ValueError):
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    if pid <= 0:
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    except PermissionError:
        # Process exists but we cannot signal it — treat lock as held.
        return False
    return False
