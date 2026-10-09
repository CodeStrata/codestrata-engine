"""Bounded atomic filesystem helpers for the file knowledge store."""

from __future__ import annotations

import errno
import json
import os
import stat
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from codestrata.application.knowledge.errors import KnowledgeStoreError

_TRANSIENT_WINERRORS = frozenset({5, 32, 33, 995})
_READ_ATTEMPTS = 5

DEFAULT_MAX_JSON_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_JSONL_LINE_BYTES = 1024 * 1024
DEFAULT_MAX_STREAM_RECORDS = 500


def is_disk_full(error: OSError) -> bool:
    """Return True when ``error`` indicates a full or oversized filesystem."""

    return error.errno in {
        errno.ENOSPC,
        getattr(errno, "EDQUOT", None),
        getattr(errno, "EFBIG", None),
    }


def is_transient_io_error(error: OSError) -> bool:
    """Return True for sharing/lock races that Windows raises during replace/read."""

    if error.errno in {errno.EACCES, errno.EPERM, errno.EBUSY}:
        return True
    winerror = getattr(error, "winerror", None)
    return winerror in _TRANSIENT_WINERRORS


def _read_file_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Bounded read that does not allocate from a torn ``st_size``."""

    with path.open("rb") as handle:
        return handle.read(max_bytes + 1)


def refuse_path_escape(root: Path, candidate: Path) -> Path:
    """Resolve ``candidate`` and require it to stay under ``root``."""

    resolved_root = root.resolve()
    absolute = candidate.resolve()
    if not _is_relative_to(absolute, resolved_root):
        raise KnowledgeStoreError(f"Path escapes knowledge root: {candidate}")
    return absolute


def relative_ref_to_path(root: Path, blob_ref: str) -> Path:
    """Map a store-relative POSIX ref onto ``root``, rejecting escapes."""

    compact = blob_ref.strip().replace("\\", "/")
    if not compact or compact.startswith("/") or ".." in compact.split("/"):
        raise KnowledgeStoreError(f"Illegal store path reference: {blob_ref}")
    return refuse_path_escape(root, Path(*compact.split("/")))


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    tmp_directory: Path,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> None:
    """Write ``payload`` via a temporary file and ``os.replace``.

    Interrupted or disk-full writes never replace the destination. Partial
    temporary files are removed.
    """

    if len(payload) > max_bytes:
        raise KnowledgeStoreError(
            f"Payload exceeds memory/output bound of {max_bytes} bytes"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_directory.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_directory / f".{path.name}.{uuid4().hex}.tmp"
    try:
        tmp_path.write_bytes(payload)
        try:
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        with tmp_path.open("rb") as handle:
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    except OSError as error:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        if is_disk_full(error):
            raise KnowledgeStoreError("Disk full while writing knowledge artifact") from error
        raise KnowledgeStoreError(f"Failed to write {path.name}") from error
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_json(
    path: Path,
    document: Any,
    *,
    tmp_directory: Path,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> None:
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    atomic_write_bytes(
        path,
        (text + "\n").encode("utf-8"),
        tmp_directory=tmp_directory,
        max_bytes=max_bytes,
    )


def read_json_file(
    path: Path,
    *,
    root: Path,
    max_bytes: int = DEFAULT_MAX_JSON_BYTES,
) -> Any:
    absolute = refuse_path_escape(root, path)
    last_error: OSError | None = None
    for attempt in range(_READ_ATTEMPTS):
        try:
            if not absolute.is_file() or absolute.is_symlink():
                raise KnowledgeStoreError(f"JSON manifest missing or unsafe: {path}")
            raw = _read_file_bytes(absolute, max_bytes=max_bytes)
            if len(raw) > max_bytes:
                raise KnowledgeStoreError(f"JSON manifest exceeds memory bound: {path}")
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise KnowledgeStoreError(f"Malformed JSON manifest: {path}") from error
        except OSError as error:
            last_error = error
            if is_transient_io_error(error) and attempt + 1 < _READ_ATTEMPTS:
                time.sleep(0.02 * (attempt + 1))
                continue
            raise KnowledgeStoreError(f"Failed to read JSON manifest: {path}") from error
    raise KnowledgeStoreError(f"Failed to read JSON manifest: {path}") from last_error


def iter_jsonl(
    path: Path,
    *,
    root: Path,
    max_line_bytes: int = DEFAULT_MAX_JSONL_LINE_BYTES,
    max_records: int = DEFAULT_MAX_STREAM_RECORDS,
) -> Iterator[Any]:
    """Stream JSONL records without loading the whole file."""

    if not path.exists():
        return
    absolute = refuse_path_escape(root, path)
    if not absolute.is_file() or absolute.is_symlink():
        raise KnowledgeStoreError(f"JSONL index missing or unsafe: {path}")
    count = 0
    with absolute.open("rb") as handle:
        for raw_line in handle:
            if len(raw_line) > max_line_bytes:
                raise KnowledgeStoreError(f"JSONL line exceeds memory bound in {path.name}")
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            if count >= max_records:
                raise KnowledgeStoreError(f"JSONL index exceeds record bound in {path.name}")
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise KnowledgeStoreError(f"Malformed JSONL index: {path}") from error
            count += 1


def write_jsonl(
    path: Path,
    records: Iterator[Any] | list[Any],
    *,
    tmp_directory: Path,
    max_line_bytes: int = DEFAULT_MAX_JSONL_LINE_BYTES,
    max_records: int = DEFAULT_MAX_STREAM_RECORDS,
) -> None:
    """Atomically replace a derived JSONL index from an iterator."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_directory.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_directory / f".{path.name}.{uuid4().hex}.jsonl"
    count = 0
    try:
        with tmp_path.open("wb") as handle:
            for record in records:
                line = json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False)
                encoded = (line + "\n").encode("utf-8")
                if len(encoded) > max_line_bytes:
                    raise KnowledgeStoreError("JSONL record exceeds memory bound")
                if count >= max_records:
                    raise KnowledgeStoreError("JSONL index exceeds record bound")
                handle.write(encoded)
                count += 1
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
    except OSError as error:
        if is_disk_full(error):
            raise KnowledgeStoreError("Disk full while writing knowledge index") from error
        raise KnowledgeStoreError(f"Failed to write JSONL index {path.name}") from error
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
