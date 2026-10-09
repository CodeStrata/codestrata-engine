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
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from re import sub

from codestrata.application.knowledge.errors import (
    KnowledgeStoreError,
    RepositoryLockTimeoutError,
)
from codestrata.application.knowledge.lock_policy import knowledge_lock_timeout_seconds
from codestrata.application.runtime_performance.posix_fcntl import posix_fcntl_module

_fcntl = posix_fcntl_module()
_process_lock_guard = threading.Lock()
_process_locks: dict[str, threading.Lock] = {}
_process_owners: dict[str, int] = {}


def _lock_key(lock_path: Path) -> str:
    return os.path.normcase(str(lock_path))


def _same_process_lock(key: str) -> tuple[threading.Lock, bool]:
    """Return the in-process lock and whether this thread already holds it."""

    me = threading.get_ident()
    with _process_lock_guard:
        if _process_owners.get(key) == me:
            return _process_locks[key], True
        lock = _process_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _process_locks[key] = lock
        return lock, False


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
    timeout_seconds = knowledge_lock_timeout_seconds(timeout_seconds)
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    key = _lock_key(lock_path)
    process_lock, same_thread = _same_process_lock(key)
    if same_thread:
        # Nested acquisition on this thread still uses the file lock so a
        # second take times out. Sibling threads queue below instead.
        with _held_file_lock(
            lock_path,
            deadline=deadline,
            poll_interval=poll_interval_seconds,
        ):
            yield
        return

    # The suite caps file-lock waits at 2s. That cap is for a stuck other
    # process, not for siblings in this process waiting out a live rebuild.
    process_lock.acquire()
    try:
        with _process_lock_guard:
            _process_owners[key] = threading.get_ident()
        try:
            with _held_file_lock(
                lock_path,
                deadline=deadline,
                poll_interval=poll_interval_seconds,
            ):
                yield
        finally:
            with _process_lock_guard:
                if _process_owners.get(key) == threading.get_ident():
                    _process_owners.pop(key, None)
    finally:
        process_lock.release()


@contextmanager
def _held_file_lock(
    lock_path: Path,
    *,
    deadline: float,
    poll_interval: float,
) -> Iterator[None]:
    if _fcntl is not None:
        with _fcntl_lock(lock_path, deadline=deadline, poll_interval=poll_interval):
            yield
        return
    with _exclusive_create_lock(
        lock_path,
        deadline=deadline,
        poll_interval=poll_interval,
    ):
        yield


@contextmanager
def _fcntl_lock(
    lock_path: Path,
    *,
    deadline: float,
    poll_interval: float,
) -> Iterator[None]:
    fcntl = posix_fcntl_module()
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
    if not _process_exists(pid):
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    return False


def _process_exists(pid: int) -> bool:
    """Return whether ``pid`` is active without terminating it."""

    if os.name == "nt":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it.
        return True
    except OSError:
        # Windows and some POSIX hosts reject signal 0; treat as absent.
        return False
    return True


def _windows_process_exists(pid: int) -> bool:
    """Probe a Windows PID using process handles; ``os.kill(pid, 0)`` is invalid."""

    import ctypes
    from ctypes import wintypes
    from typing import Any

    process_query_limited_information = 0x1000
    error_access_denied = 5
    still_active = 259
    # Windows-only ctypes names. Indirect lookup keeps Darwin typechecking honest
    # without skipping the branch or disabling the check.
    win_dll = "WinDLL"
    last_error = "get_last_error"
    windll: Any = getattr(ctypes, win_dll)
    get_last_error: Any = getattr(ctypes, last_error)
    try:
        kernel32 = windll("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        handle = open_process(process_query_limited_information, False, pid)
        if not handle:
            # Access denied proves a protected process exists. Other failures are
            # treated as absent so stale lock files can be recovered.
            return bool(get_last_error() == error_access_denied)
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                # A failed query on an opened handle is inconclusive; keep the lock.
                return True
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    except OSError:
        return False
