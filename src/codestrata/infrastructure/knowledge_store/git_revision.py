"""Safe Git revision observation for knowledge snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.repository_auth.git_runner import run_git
from codestrata.security.redaction import Redactor


@dataclass(frozen=True, slots=True)
class ObservedRepositoryRevision:
    """Best-effort Git revision observation."""

    revision_type: RepositoryRevisionType
    revision_id: str
    branch: str | None
    dirty: bool = False


def observe_repository_revision(
    repository_root: Path,
    *,
    configured_branch: str | None = None,
) -> ObservedRepositoryRevision:
    """Observe HEAD revision; fall back to working-tree on any Git failure."""

    root = repository_root.expanduser()
    if not (root / ".git").exists():
        return ObservedRepositoryRevision(
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            branch=configured_branch,
            dirty=False,
        )

    redactor = Redactor()
    try:
        sha = _git_text(root, ["rev-parse", "HEAD"], redactor=redactor)
        branch = _git_branch(root, redactor=redactor) or configured_branch
        dirty = _git_dirty(root, redactor=redactor)
        return ObservedRepositoryRevision(
            revision_type=RepositoryRevisionType.COMMIT,
            revision_id=sha,
            branch=branch,
            dirty=dirty,
        )
    except Exception:  # noqa: BLE001 - provenance must not fail assessment
        return ObservedRepositoryRevision(
            revision_type=RepositoryRevisionType.WORKING_TREE,
            revision_id="working-tree",
            branch=configured_branch,
            dirty=False,
        )


def _git_text(root: Path, args: list[str], *, redactor: Redactor) -> str:
    result = run_git(args, cwd=root, timeout_seconds=30, redactor=redactor)
    return (result.stdout or "").strip()


def _git_branch(root: Path, *, redactor: Redactor) -> str | None:
    try:
        name = _git_text(
            root,
            ["rev-parse", "--abbrev-ref", "HEAD"],
            redactor=redactor,
        )
    except Exception:  # noqa: BLE001
        return None
    if not name or name == "HEAD":
        return None
    return name


def _git_dirty(root: Path, *, redactor: Redactor) -> bool:
    try:
        result = run_git(
            ["status", "--porcelain"],
            cwd=root,
            timeout_seconds=30,
            redactor=redactor,
        )
    except Exception:  # noqa: BLE001
        return False
    return bool((result.stdout or "").strip())
