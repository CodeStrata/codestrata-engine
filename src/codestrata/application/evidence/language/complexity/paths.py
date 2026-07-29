"""Shared path filtering and metrics helpers for complexity evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.scan_boundary import default_ignore_path_markers

# Default exclusions for complexity measurement (includes .codestrata workspace clones).
DEFAULT_COMPLEXITY_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_SUPPORTED_SUFFIXES: dict[str, frozenset[str]] = {
    "python": frozenset({".py"}),
    "java": frozenset({".java"}),
    "php": frozenset({".php"}),
    "csharp": frozenset({".cs"}),
}


def normalize_relative_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def physical_line_count(text: str) -> int:
    """Count physical lines. Empty text is 0; trailing newline does not add a line."""

    if not text:
        return 0
    return len(text.splitlines())


def is_complexity_source_path(
    path: str,
    *,
    ignore_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    language: str | None = None,
) -> bool:
    """Return True when a relative path is eligible for complexity measurement."""

    lower = normalize_relative_path(path).lower()
    if lower.startswith(".codestrata/") or "/.codestrata/" in lower:
        return False
    for marker in ignore_markers:
        compact = marker.strip().lower()
        if not compact:
            continue
        if compact in lower:
            return False
        # Also match markers without leading slash for relative roots.
        stripped = compact.lstrip("/")
        if stripped and (lower.startswith(stripped) or f"/{stripped}" in lower):
            return False
    suffix = PurePosixPath(lower).suffix
    if language is None:
        return suffix in {".py", ".java", ".php", ".cs"}
    allowed = _SUPPORTED_SUFFIXES.get(language.strip().lower(), frozenset())
    return suffix in allowed


def select_complexity_paths(
    relative_paths: Sequence[str],
    *,
    language: str,
    ignore_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    max_files: int = 2000,
) -> tuple[tuple[str, ...], int]:
    """Return (sorted eligible paths truncated to max_files, excluded_count)."""

    eligible: list[str] = []
    excluded = 0
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path:
            continue
        if is_complexity_source_path(path, ignore_markers=ignore_markers, language=language):
            eligible.append(path)
        elif PurePosixPath(path).suffix.lower() in _SUPPORTED_SUFFIXES.get(
            language.strip().lower(), frozenset()
        ):
            excluded += 1
    ordered = tuple(sorted(set(eligible)))
    if len(ordered) > max_files:
        return ordered[:max_files], excluded + (len(ordered) - max_files)
    return ordered, excluded


def texts_for_paths(
    paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in paths:
        if path in file_texts:
            mapping[path] = file_texts[path]
            continue
        # Allow callers that keyed with alternate separators.
        alt = path.replace("/", "\\")
        if alt in file_texts:
            mapping[path] = file_texts[alt]
    return mapping


def classification_for_path(path: str) -> SourceClassification:
    return classify_source_path(path)
