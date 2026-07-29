"""Locate monorepo vs engine checkout roots.

Used by acceptance targets and tests so paths work both inside
``codestrata-platform`` and in a standalone ``codestrata-engine`` export.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def engine_root() -> Path:
    """Return the Community Engine package root (directory with ``pyproject.toml``)."""

    # engine/src/codestrata/<this module's package> — walk up to engine/
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "codestrata"
        ).is_dir():
            return candidate
    # Fallback: src/codestrata/paths.py → parents[2] == package root when flat
    return here.parents[2]


@lru_cache(maxsize=1)
def workspace_root() -> Path:
    """Return monorepo root when present; otherwise the engine root."""

    engine = engine_root()
    parent = engine.parent
    if (parent / "public-export-manifest.yaml").is_file() and (parent / "platform").is_dir():
        return parent
    if (parent / "examples").is_dir() and engine.name == "engine":
        return parent
    return engine


def examples_root() -> Path:
    """Public examples directory (real-world showcases; monorepo or engine)."""

    ws = workspace_root()
    if (ws / "examples").is_dir():
        return ws / "examples"
    eng = engine_root()
    if (eng / "examples").is_dir():
        return eng / "examples"
    return ws / "examples"


def test_fixtures_root() -> Path:
    """Internal language sample fixtures (not part of codestrata-examples)."""

    ws = workspace_root()
    if (ws / "test-fixtures").is_dir():
        return ws / "test-fixtures"
    eng = engine_root()
    if (eng / "test-fixtures").is_dir():
        return eng / "test-fixtures"
    return ws / "test-fixtures"
