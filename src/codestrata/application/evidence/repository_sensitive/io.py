"""Load repository texts/bytes for repository-sensitive evidence."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from codestrata.application.evidence.repository_sensitive.discovery import (
    DEFAULT_IGNORE_MARKERS,
    discover_candidates,
    discover_configuration_paths,
    is_binary_extension,
    normalize_relative_path,
)
from codestrata.services.inventory.content_reader import (
    LocalFilesystemContentReader,
    RepositoryContentReader,
)


def load_repository_sensitive_inputs(
    *,
    relative_paths: Sequence[str],
    repository_root: Path | None,
    content_reader: RepositoryContentReader | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    max_file_chars: int = 500_000,
    max_file_bytes: int = 2_000_000,
) -> tuple[
    tuple[tuple[str, object, tuple[object, ...]], ...],
    dict[str, str],
    dict[str, bytes],
    dict[str, str],
]:
    """Return (candidates, texts, binaries, load_errors).

    ``load_errors`` maps repository-relative path → diagnostic code.
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
    config_paths = discover_configuration_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    paths_to_load = tuple(
        sorted(
            {
                *(path for path, _, _ in candidates),
                *config_paths,
            }
        )
    )

    texts: dict[str, str] = {}
    binaries: dict[str, bytes] = {}
    errors: dict[str, str] = {}
    if reader is None:
        return candidates, texts, binaries, errors

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

        if is_binary_extension(normalized):
            binaries[normalized] = raw[:max_file_bytes]
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

    return candidates, texts, binaries, errors
