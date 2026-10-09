"""Local retention that never touches source, baselines, or unrelated files."""

from __future__ import annotations

import shutil
from pathlib import Path

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.infrastructure.knowledge_store.defaults import DATABASE_FILENAME
from codestrata.infrastructure.knowledge_store.file.layout import FileStorePaths
from codestrata.infrastructure.knowledge_store.io import refuse_path_escape

_OWNED_TOP_LEVEL = frozenset(
    {
        "store.json",
        "repositories",
        "indexes",
        "staging",
        "locks",
        "blobs",
        "tmp",
        DATABASE_FILENAME,
    }
)


def cleanup_tmp_and_staging(paths: FileStorePaths) -> int:
    """Remove leftover tmp/staging files owned by the store. Return count deleted."""

    deleted = 0
    for directory in (paths.tmp, paths.staging):
        if not directory.is_dir() or directory.is_symlink():
            continue
        refuse_path_escape(paths.root, directory)
        for child in list(directory.iterdir()):
            try:
                refuse_path_escape(paths.root, child)
            except KnowledgeStoreError:
                continue
            if child.is_symlink():
                continue
            try:
                if child.is_file():
                    child.unlink()
                    deleted += 1
                elif child.is_dir():
                    shutil.rmtree(child)
                    deleted += 1
            except OSError:
                continue
    return deleted


def assert_retention_protected(
    paths: FileStorePaths,
    *,
    source_root: Path | None = None,
    baseline_paths: tuple[Path, ...] = (),
    unrelated_files: tuple[Path, ...] = (),
) -> None:
    """Refuse cleanup targets that would destroy source, baselines, or foreign files."""

    root = paths.root.resolve()
    protected = list(baseline_paths) + list(unrelated_files)
    if source_root is not None:
        protected.append(source_root)
    for item in protected:
        resolved = item.resolve()
        if resolved == root:
            raise KnowledgeStoreError("Retention refuses to delete the knowledge root")
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        if resolved == root:
            raise KnowledgeStoreError("Retention refuses to delete the knowledge root")
        if relative.parts and relative.parts[0] in {"tmp", "staging"}:
            raise KnowledgeStoreError(f"Retention refuses protected path: {item}")


def list_unrelated_top_level(paths: FileStorePaths) -> tuple[Path, ...]:
    if not paths.root.is_dir():
        return ()
    found: list[Path] = []
    for child in paths.root.iterdir():
        if child.name not in _OWNED_TOP_LEVEL:
            found.append(child)
    return tuple(found)
