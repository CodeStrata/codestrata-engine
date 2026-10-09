"""Safe Git revision observation for knowledge snapshots and E09.1 local state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.repository.enums import RepositoryRevisionType
from codestrata.repository_auth.git_runner import run_git
from codestrata.repository_auth.read_only_git import ReadOnlyGitError, run_readonly_git
from codestrata.security.redaction import Redactor


@dataclass(frozen=True, slots=True)
class ObservedRepositoryRevision:
    """Best-effort Git revision observation."""

    revision_type: RepositoryRevisionType
    revision_id: str
    branch: str | None
    dirty: bool = False


@dataclass(frozen=True, slots=True)
class LocalGitState:
    """Pinned local Git identities. Digests never require writing objects."""

    repository_root: str
    head_sha: str | None
    branch: str | None
    tree_oid: str | None
    index_digest: str
    working_tree_digest: str
    state_digest: str
    dirty: bool
    shallow: bool
    observed_commit_count: int | None
    shallow_boundary_shas: tuple[str, ...]
    submodule_paths: tuple[str, ...]
    limitations: tuple[str, ...]


def resolve_containing_git_root(start: Path) -> Path | None:
    """Walk upward from an assessment root to the containing Git directory.

    Source scanning stays at ``start``. Identity and history use this root.
    """

    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = candidate / ".git"
        if marker.exists() or marker.is_file():
            return candidate
    return None


def observe_repository_revision(
    repository_root: Path,
    *,
    configured_branch: str | None = None,
) -> ObservedRepositoryRevision:
    """Observe HEAD revision; fall back to working-tree on any Git failure."""

    root = resolve_containing_git_root(repository_root) or repository_root.expanduser()
    if not (root / ".git").exists() and not (root / ".git").is_file():
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


def observe_local_git_state(repository_root: Path) -> LocalGitState:
    """Read HEAD, tree, index and working-tree identity without mutating checkout."""

    requested = repository_root.expanduser().resolve()
    root = resolve_containing_git_root(requested) or requested
    limitations: list[str] = []
    if not (root / ".git").exists() and not (root / ".git").is_file():
        empty = digest_canonical({"kind": "not-a-git-repository", "root": str(root)})
        return LocalGitState(
            repository_root=str(root),
            head_sha=None,
            branch=None,
            tree_oid=None,
            index_digest=empty,
            working_tree_digest=empty,
            state_digest=empty,
            dirty=False,
            shallow=False,
            observed_commit_count=None,
            shallow_boundary_shas=(),
            submodule_paths=(),
            limitations=("not_a_git_repository",),
        )

    head_sha = _optional_text(root, ["rev-parse", "HEAD"], limitations, "head_unresolved")
    branch = _optional_text(root, ["rev-parse", "--abbrev-ref", "HEAD"], limitations, None)
    if branch == "HEAD":
        branch = None
        limitations.append("detached_head")
    tree_oid = _optional_text(root, ["rev-parse", "HEAD^{tree}"], limitations, "tree_unresolved")
    index_text = _optional_text(root, ["ls-files", "-s"], limitations, "index_unreadable") or ""
    porcelain = (
        _optional_text(root, ["status", "--porcelain=v1", "-z"], limitations, "status_unreadable")
        or ""
    )
    worktree_diff = _optional_text(root, ["diff", "HEAD"], limitations, "worktree_diff_unreadable")
    if worktree_diff is None:
        worktree_diff = ""
    index_digest = digest_canonical({"index": index_text})
    working_tree_digest = digest_canonical({"status": porcelain, "diff_head": worktree_diff})
    dirty = bool(porcelain.replace("\x00", "").strip())
    shallow = _is_shallow(root)
    commit_count = _optional_int(root, ["rev-list", "--count", "HEAD"], limitations)
    boundaries: tuple[str, ...] = ()
    if shallow:
        boundary_text = _optional_text(
            root,
            ["rev-list", "--max-parents=0", "HEAD"],
            limitations,
            "shallow_boundary_unresolved",
        )
        if boundary_text:
            boundaries = tuple(
                line.strip() for line in boundary_text.splitlines() if line.strip()
            )
        limitations.append("shallow_history")
    submodules = _submodule_paths(root, index_text)
    if submodules:
        limitations.append("submodules_present")
    state_digest = digest_canonical(
        {
            "head": head_sha,
            "branch": branch,
            "tree": tree_oid,
            "index_digest": index_digest,
            "working_tree_digest": working_tree_digest,
            "dirty": dirty,
            "shallow": shallow,
            "observed_commit_count": commit_count,
            "shallow_boundary_shas": list(boundaries),
            "submodule_paths": list(submodules),
        }
    )
    return LocalGitState(
        repository_root=str(root),
        head_sha=head_sha,
        branch=branch,
        tree_oid=tree_oid,
        index_digest=index_digest,
        working_tree_digest=working_tree_digest,
        state_digest=state_digest,
        dirty=dirty,
        shallow=shallow,
        observed_commit_count=commit_count,
        shallow_boundary_shas=boundaries,
        submodule_paths=submodules,
        limitations=tuple(dict.fromkeys(limitations)),
    )


def mailmap_present(repository_root: Path) -> bool:
    """True when the repository has a root ``.mailmap`` file."""

    return (repository_root.expanduser().resolve() / ".mailmap").is_file()


def read_reachable_commit_metadata(repository_root: Path, *, head: str) -> str:
    """Metadata for reachable non-merge commits. Never uses first-parent."""

    root = repository_root.expanduser().resolve()
    mailmap_flag = "--use-mailmap" if mailmap_present(root) else "--no-mailmap"
    return run_readonly_git(
        [
            "log",
            "--no-merges",
            mailmap_flag,
            "--pretty=format:%H%x00%P%x00%ct%x00%an%x00%ae%x00%aN%x00%aE%x00%s%x00%b%x1e",
            head,
        ],
        cwd=root,
        timeout_seconds=120,
    )


def read_reachable_commit_numstat(repository_root: Path, *, head: str) -> str:
    """Numstat plus rename mapping for reachable non-merge commits."""

    root = repository_root.expanduser().resolve()
    return run_readonly_git(
        [
            "log",
            "--no-merges",
            "--find-renames",
            "--numstat",
            "--pretty=format:%x1e%H",
            head,
        ],
        cwd=root,
        timeout_seconds=120,
    )


def read_reachable_commit_name_status(repository_root: Path, *, head: str) -> str:
    """Name-status plus rename mapping for reachable non-merge commits."""

    root = repository_root.expanduser().resolve()
    return run_readonly_git(
        [
            "log",
            "--no-merges",
            "--find-renames",
            "--name-status",
            "--pretty=format:%x1e%H",
            head,
        ],
        cwd=root,
        timeout_seconds=120,
    )


def read_merge_combined_numstat(repository_root: Path, *, head: str) -> str:
    """Combined diffs of merge commits (conflict-resolution disclosure only)."""

    root = repository_root.expanduser().resolve()
    return run_readonly_git(
        [
            "log",
            "--merges",
            "--cc",
            "--numstat",
            "--pretty=format:%x1e%H%x00%P",
            head,
        ],
        cwd=root,
        timeout_seconds=120,
    )


def object_exists(repository_root: Path, revision: str) -> bool:
    """True when ``revision`` is already present locally. Never fetches."""

    try:
        run_readonly_git(
            ["cat-file", "-e", revision],
            cwd=repository_root,
            timeout_seconds=15,
        )
    except ReadOnlyGitError:
        return False
    return True


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


def _optional_text(
    root: Path,
    args: list[str],
    limitations: list[str],
    limitation: str | None,
) -> str | None:
    try:
        return run_readonly_git(args, cwd=root).rstrip("\n")
    except ReadOnlyGitError:
        if limitation:
            limitations.append(limitation)
        return None


def _optional_int(root: Path, args: list[str], limitations: list[str]) -> int | None:
    text = _optional_text(root, args, limitations, "commit_count_unresolved")
    if text is None or not text.strip().isdigit():
        return None
    return int(text.strip())


def _is_shallow(root: Path) -> bool:
    try:
        text = run_readonly_git(["rev-parse", "--is-shallow-repository"], cwd=root)
    except ReadOnlyGitError:
        return (root / ".git" / "shallow").exists()
    return text.strip().lower() == "true"


def _submodule_paths(root: Path, index_text: str) -> tuple[str, ...]:
    paths: list[str] = []
    for line in index_text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "160000":
            paths.append(parts[3])
    gitmodules = root / ".gitmodules"
    if gitmodules.is_file():
        try:
            raw = gitmodules.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("path") and "=" in stripped:
                path = stripped.split("=", 1)[1].strip()
                if path and path not in paths:
                    paths.append(path)
    return tuple(sorted(set(paths)))
