"""Anonymous banding helpers (never exact counts or paths)."""

from __future__ import annotations

import os
from pathlib import Path

from codestrata.telemetry.constants import (
    DURATION_BANDS_MS,
    LANGUAGE_EXTENSION_MAP,
    SIZE_BANDS,
    SKIP_DIR_NAMES,
)


def repository_size_band(file_count: int) -> str:
    if file_count < 0:
        file_count = 0
    for upper, label in SIZE_BANDS:
        if upper is None or file_count <= upper:
            return label
    return "10000+"


def duration_band(duration_ms: float | None) -> str | None:
    if duration_ms is None:
        return None
    value = max(0.0, float(duration_ms))
    for upper, label in DURATION_BANDS_MS:
        if upper is None or value <= upper:
            return label
    return "15m+"


def language_category_for_suffix(suffix: str) -> str | None:
    return LANGUAGE_EXTENSION_MAP.get(suffix.lower())


def scan_anonymous_repo_stats(root: Path, *, max_files: int = 50_000) -> tuple[int, list[str]]:
    """Count files and language categories without recording paths or names."""

    if not root.is_dir():
        return 0, []
    count = 0
    categories: set[str] = set()
    for _dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIR_NAMES)
        for name in filenames:
            count += 1
            category = language_category_for_suffix(Path(name).suffix)
            if category:
                categories.add(category)
            if count >= max_files:
                return count, sorted(categories)
    return count, sorted(categories)
