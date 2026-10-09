"""Engine-owned path classification for the E00.2 scope guard.

A path is in scope only when its first component is exactly ``engine``.
``engine-extra/`` and ``platform/engine/`` are outside. Named surfaces below
are called out in violation text; they are not a separate allow/deny list —
everything outside ``engine/`` already fails.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

ENGINE_PREFIX = "engine/"  # documentation alias; ownership uses ENGINE_DIR_NAME
ENGINE_DIR_NAME = "engine"

# Named outside-Engine surfaces the guard must reject even when reviewers
# might otherwise treat them as "repo glue". These are examples of the
# general rule: any path not under engine/ is out of scope.
NAMED_OUTSIDE_SURFACES: tuple[str, ...] = (
    "scripts/",
    ".github/workflows/",
    "public-export-manifest.yaml",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
)


def posix_relpath(path: str | Path) -> str:
    """Normalize a repo-relative path so Windows and ``./`` prefixes compare equal."""

    text = str(path).replace("\\", "/").strip()
    if text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def is_engine_owned(path: str | Path) -> bool:
    """True only for ``engine`` itself or ``engine/...``. ``..`` segments never pass."""

    normalized = posix_relpath(path)
    if not normalized or normalized in {".", ".."}:
        return False
    parts = PurePosixPath(normalized).parts
    # Reject path-escape attempts even if git somehow emitted them.
    if ".." in parts:
        return False
    return parts[0] == ENGINE_DIR_NAME


def named_outside_surface(path: str | Path) -> str | None:
    """Return the named outside surface a path matches, if any."""

    normalized = posix_relpath(path)
    for surface in NAMED_OUTSIDE_SURFACES:
        if surface.endswith("/"):
            if normalized == surface.rstrip("/") or normalized.startswith(surface):
                return surface
        elif normalized == surface:
            return surface
    return None
