"""Load repository-relative texts for Dependency Evidence collectors."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from codestrata.application.evidence.dependency.paths import (
    classify_manifest_basename,
    normalize_relative_path,
)
from codestrata.services.inventory.content_reader import (
    LocalFilesystemContentReader,
    RepositoryContentReader,
)


def load_dependency_manifest_texts(
    *,
    relative_paths: Sequence[str],
    repository_root: Path | None,
    content_reader: RepositoryContentReader | None = None,
    max_files: int = 500,
    max_chars: int = 500_000,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return (paths considered, texts) for supported manifests under root."""

    reader = content_reader
    if reader is None and repository_root is not None:
        root = repository_root.expanduser()
        if root.is_dir():
            reader = LocalFilesystemContentReader(root)
    candidates = [
        normalize_relative_path(path)
        for path in relative_paths
        if classify_manifest_basename(path) is not None
    ]
    ordered = tuple(sorted(set(path for path in candidates if path)))[:max_files]
    if reader is None:
        return ordered, {}
    texts: dict[str, str] = {}
    for path in ordered:
        try:
            raw = reader.read(path).data
        except (OSError, ValueError, FileNotFoundError):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        texts[path] = text[:max_chars]
    return ordered, texts
