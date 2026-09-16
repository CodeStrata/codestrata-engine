"""Engine-owned scope and quality-command harness (E00.2).

Read in this order:

1. ``paths``            — is a git path under ``engine/``?
2. ``git_changes``      — collect staged / unstaged / untracked / rename / delete / cumulative events
3. ``inventory``        — dirty paths that already existed (do not treat as this story's leak)
4. ``scope_guard``      — PASS / FAIL / ERROR / BUDGET from those events
5. ``quality_commands`` — run the YAML manifest (harness vs product baseline vs security)
6. ``cli`` / ``__main__`` — ``python -m verification scope|quality``

This package is not the installable ``codestrata`` product. Product code stays at
the repository root (``src/codestrata``).
"""

from __future__ import annotations

__all__ = ["PACKAGE_REVISION"]

PACKAGE_REVISION = "ENGINE-2026-09-15-R1"
