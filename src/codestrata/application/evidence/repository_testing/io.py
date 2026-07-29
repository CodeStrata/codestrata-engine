"""Load repository texts for repository-testing evidence."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from codestrata.application.evidence.repository_testing.discovery import (
    DEFAULT_IGNORE_MARKERS,
    discover_build_paths,
    discover_candidates,
    discover_ci_paths,
    discover_coverage_paths,
    discover_fixture_paths,
    normalize_relative_path,
)
from codestrata.domain.evidence.repository_testing.enums import TestDiscoveryBasis, TestFileRole
from codestrata.services.inventory.content_reader import (
    LocalFilesystemContentReader,
    RepositoryContentReader,
)


def load_repository_testing_inputs(
    *,
    relative_paths: Sequence[str],
    repository_root: Path | None,
    content_reader: RepositoryContentReader | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    max_file_chars: int = 500_000,
    max_file_bytes: int = 2_000_000,
) -> tuple[
    list[tuple[str, TestFileRole, tuple[TestDiscoveryBasis, ...], str | None]],
    dict[str, str],
    dict[str, str],
]:
    """Return (file_candidates_meta, texts, load_errors).

    ``file_candidates_meta`` is a list of ``(path, role, bases, language_hint)``.
    Absolute paths are never returned.
    """

    reader = content_reader
    if reader is None and repository_root is not None:
        root = repository_root.expanduser()
        if root.is_dir():
            reader = LocalFilesystemContentReader(root)

    candidates = discover_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    build_paths = discover_build_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    ci_paths = discover_ci_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    fixture_paths = discover_fixture_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    coverage_paths = discover_coverage_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    paths_to_load = tuple(
        sorted(
            {
                *(path for path, _, _, _ in candidates),
                *(path for path, _ in build_paths),
                *ci_paths,
                *fixture_paths,
                *(path for path, _ in coverage_paths),
            }
        )
    )

    texts: dict[str, str] = {}
    errors: dict[str, str] = {}
    file_candidates_meta = [
        (path, role, bases, language_hint)
        for path, role, bases, language_hint in candidates
    ]

    if reader is None:
        return file_candidates_meta, texts, errors

    for path in paths_to_load:
        normalized = normalize_relative_path(path)
        try:
            raw = reader.read(normalized).data
        except FileNotFoundError:
            errors[normalized] = "unreadable_file"
            continue
        except (OSError, ValueError):
            errors[normalized] = "unreadable_file"
            continue

        if len(raw) > max_file_bytes:
            errors[normalized] = "file_too_large"
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors[normalized] = "unsupported_encoding"
            continue

        if len(text) > max_file_chars:
            texts[normalized] = text[:max_file_chars]
            errors[normalized] = "truncated_parsing"
        else:
            texts[normalized] = text

    return file_candidates_meta, texts, errors
