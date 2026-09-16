"""Path classification for the Engine-only scope guard.

Git reports paths with mixed slashes. Everything is normalized to POSIX
(``engine/foo``) before the ``engine/`` prefix check. ``..`` and absolute
paths are out of scope so a rename cannot escape the tree.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

ENGINE_PREFIX = "engine"


def posix_relpath(path: str | Path) -> str:
    text = str(path).replace("\\", "/").strip()
    text = text.removeprefix("./")
    return text


def path_escapes_tree(rel: str) -> bool:
    """True if *rel* could leave the repository root via ``/`` or ``..``."""
    normalized = posix_relpath(rel)
    if normalized.startswith("/"):
        return True
    parts = PurePosixPath(normalized).parts
    return any(part == ".." for part in parts)


def is_under_engine(rel: str) -> bool:
    """Return True when *rel* is ``engine`` or a path under ``engine/``."""
    normalized = posix_relpath(rel)
    if not normalized or path_escapes_tree(normalized):
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and parts[0] == ENGINE_PREFIX


def both_under_engine(source: str, destination: str) -> bool:
    """Renames are in-scope only when *both* sides stay under ``engine/``."""
    return is_under_engine(source) and is_under_engine(destination)


# Used by scope_guard: a single path (edits/deletes) or both rename sides.
