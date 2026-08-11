"""Workspace helpers for SV.10."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from verification.repository_assessment.workspace import assert_outside_codestrata_tree


@dataclass(frozen=True, slots=True)
class WorkspaceBundle:
    root: Path
    clone_dir: Path
    home_dir: Path
    artifact_dir: Path


def create_workspace(*, prefix: str = "cs-sv10-") -> WorkspaceBundle:
    root = Path(tempfile.mkdtemp(prefix=prefix))
    clone_dir = root / "clone"
    home_dir = root / "home"
    artifact_dir = root / "artifacts"
    home_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return WorkspaceBundle(
        root=root,
        clone_dir=clone_dir,
        home_dir=home_dir,
        artifact_dir=artifact_dir,
    )


def ensure_external(workspace: WorkspaceBundle, codestrata_root: Path) -> None:
    assert_outside_codestrata_tree(workspace.root, codestrata_root)


def cleanup_workspace(workspace: WorkspaceBundle, *, keep: bool = False) -> None:
    if keep:
        return
    shutil.rmtree(workspace.root, ignore_errors=True)
