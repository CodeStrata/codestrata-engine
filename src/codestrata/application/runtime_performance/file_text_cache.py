"""Shared source-text loading with optional bounded concurrency."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from codestrata.services.inventory import (
    LocalFilesystemContentReader,
    RepositoryContentReader,
)

# Extensions eligible for architecture / complexity / language evidence reuse.
DEFAULT_SOURCE_SUFFIXES: tuple[str, ...] = (
    ".java",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".php",
    ".cs",
)


@dataclass(frozen=True)
class FileTextLoadStats:
    """Telemetry for a shared source-text load."""

    files_considered: int
    files_loaded: int
    files_skipped: int
    files_truncated: int
    files_failed: int
    cache_hits: int
    cache_misses: int
    max_files: int
    max_chars: int
    max_read_workers: int


def select_source_paths(
    relative_paths: Sequence[str],
    *,
    suffixes: Sequence[str] = DEFAULT_SOURCE_SUFFIXES,
    max_files: int = 2000,
) -> tuple[tuple[str, ...], int]:
    """Return deterministic eligible paths and skip count past ``max_files``."""

    allowed = {item.lower() for item in suffixes}
    eligible = sorted(
        {
            path.replace("\\", "/")
            for path in relative_paths
            if path and Path(path.replace("\\", "/")).suffix.lower() in allowed
        }
    )
    if len(eligible) > max_files:
        return tuple(eligible[:max_files]), len(eligible) - max_files
    return tuple(eligible), 0


def load_shared_source_texts(
    *,
    relative_paths: Sequence[str],
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    suffixes: Sequence[str] = DEFAULT_SOURCE_SUFFIXES,
    max_files: int = 2000,
    max_chars: int = 100_000,
    max_read_workers: int = 1,
    prior_texts: dict[str, str] | None = None,
) -> tuple[dict[str, str], FileTextLoadStats]:
    """Load source texts once for reuse across architecture/complexity/language.

    When ``max_read_workers`` > 1, independent files are read concurrently and
    merged in sorted path order so the resulting map is deterministic.
    """

    reader = content_reader
    if reader is None and repository_root is not None:
        root = repository_root.expanduser()
        if root.is_dir():
            reader = LocalFilesystemContentReader(root)
    paths, truncated_count = select_source_paths(
        relative_paths,
        suffixes=suffixes,
        max_files=max_files,
    )
    cache = dict(prior_texts or {})
    hits = 0
    misses = 0
    failed = 0
    truncated_chars = 0
    to_read: list[str] = []
    for path in paths:
        if path in cache:
            hits += 1
            continue
        misses += 1
        to_read.append(path)

    loaded: dict[str, str] = {}
    if reader is not None and to_read:
        workers = max(1, int(max_read_workers))
        if workers == 1 or len(to_read) == 1:
            for path in to_read:
                text, ok, was_truncated = _read_one(reader, path, max_chars=max_chars)
                if not ok:
                    failed += 1
                    continue
                if was_truncated:
                    truncated_chars += 1
                loaded[path] = text
        else:
            # Bounded concurrency; merge by sorted path for determinism.
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_read_one, reader, path, max_chars=max_chars): path
                    for path in to_read
                }
                for future in as_completed(futures):
                    path = futures[future]
                    try:
                        text, ok, was_truncated = future.result()
                    except Exception:  # noqa: BLE001
                        failed += 1
                        continue
                    if not ok:
                        failed += 1
                        continue
                    if was_truncated:
                        truncated_chars += 1
                    loaded[path] = text
            loaded = {path: loaded[path] for path in sorted(loaded)}

    cache.update(loaded)
    # Preserve only requested paths in deterministic order.
    ordered = {path: cache[path] for path in paths if path in cache}
    stats = FileTextLoadStats(
        files_considered=len(paths) + truncated_count,
        files_loaded=len(ordered),
        files_skipped=truncated_count + failed + (len(paths) - len(ordered)),
        files_truncated=truncated_chars + truncated_count,
        files_failed=failed,
        cache_hits=hits,
        cache_misses=misses,
        max_files=max_files,
        max_chars=max_chars,
        max_read_workers=max(1, int(max_read_workers)),
    )
    return ordered, stats


def _read_one(
    reader: RepositoryContentReader,
    path: str,
    *,
    max_chars: int,
) -> tuple[str, bool, bool]:
    try:
        raw = reader.read(path).data
    except (OSError, ValueError, FileNotFoundError):
        return "", False, False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars], True, True
    return text, True, False
