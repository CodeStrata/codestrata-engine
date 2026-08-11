"""Clone helpers for SV.10 — reuse SV.4 clone with tier timeouts."""

from __future__ import annotations

import shutil
from pathlib import Path

from verification.curated_repository_validation.catalog import (
    ReleaseValidationEntry,
    to_sv4_catalog_entry,
)
from verification.curated_repository_validation.contract import CLONE_TIMEOUT_S
from verification.repository_assessment.clone import CloneResult, clone_qualified_repository
from verification.repository_assessment.workspace import assert_outside_codestrata_tree


def clone_release_entry(
    entry: ReleaseValidationEntry,
    destination: Path,
    *,
    codestrata_root: Path,
    timeout_s: float | None = None,
) -> CloneResult:
    assert_outside_codestrata_tree(destination, codestrata_root)
    timeout = int(timeout_s if timeout_s is not None else CLONE_TIMEOUT_S.get(entry.tier, 600))
    return clone_qualified_repository(
        to_sv4_catalog_entry(entry),
        destination,
        timeout_s=timeout,
    )


def cleanup_clone(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
