"""R2-P05 first-parent source-state selection and immutable tree materialization.

This module extracts committed trees only. It does not assess, compare, or
register ``trend``.

Unsupported / safe behavior (not expanded here):
- Submodule gitlink objects are not recursively materialized. The superproject
  records the gitlink; contents of another repository are not checked out.
- Absolute or escaping symlinks are skipped. Relative in-tree symlinks are
  created as recorded in the commit.
- Hardlinks are skipped.
- ``git checkout``, index mutation, hooks, builds, and tests are never used.
- ``git archive`` is not used because it applies ``export-ignore`` and would
  not match commit-tree bytes.

Extraction uses allow-listed ``rev-list`` / ``rev-parse`` / ``ls-tree`` /
``cat-file`` through the read-only Git runner.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType

from codestrata.infrastructure.knowledge_store.git_revision import (
    LocalGitState,
    observe_local_git_state,
    resolve_containing_git_root,
)
from codestrata.repository_auth.read_only_git import (
    ReadOnlyGitError,
    run_readonly_git,
    run_readonly_git_bytes,
)

SERIES_SLOT_COUNT = 5
SERIES_HEAD_SLOT = 5

GITLINK_MODE = "160000"
SYMLINK_MODE = "120000"

UNSUPPORTED_SOURCE_STATE_BEHAVIOR = (
    "submodule_contents_not_materialized",
    "escaping_symlinks_skipped",
    "hardlinks_skipped",
    "hooks_not_executed",
    "archive_export_ignore_not_used",
)


class SourceStateUnavailableReason(StrEnum):
    MISSING_GIT = "missing_git"
    HEAD_UNRESOLVED = "head_unresolved"
    INSUFFICIENT_HISTORY = "insufficient_history"
    MATERIALIZE_FAILED = "materialize_failed"


@dataclass(frozen=True, slots=True)
class SourceStateSlot:
    """One requested slot in the fixed five-slot series. S1 oldest, S5 HEAD."""

    slot: int
    sha: str | None
    available: bool
    unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class SourceStateSeries:
    """Committed HEAD plus up to four first-parent predecessors, oldest→newest."""

    requested_root: Path
    git_root: Path | None
    assessment_relpath: str
    head_sha: str | None
    slots: tuple[SourceStateSlot, ...]
    limitations: tuple[str, ...]

    def available_slots(self) -> tuple[SourceStateSlot, ...]:
        return tuple(slot for slot in self.slots if slot.available and slot.sha)


@dataclass(frozen=True, slots=True)
class MaterializedSnapshot:
    slot: SourceStateSlot
    root: Path | None
    file_count: int
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorktreeFingerprint:
    """Read-only identity used to prove the user checkout was not mutated."""

    head_sha: str | None
    tree_oid: str | None
    index_digest: str
    working_tree_digest: str
    dirty: bool
    state_digest: str


@dataclass(frozen=True, slots=True)
class _TreeEntry:
    mode: str
    object_type: str
    object_id: str
    path: str


def capture_worktree_fingerprint(repository_root: Path) -> WorktreeFingerprint:
    """Observe HEAD/index/worktree without writing objects or mutating files."""

    state: LocalGitState = observe_local_git_state(repository_root)
    return WorktreeFingerprint(
        head_sha=state.head_sha,
        tree_oid=state.tree_oid,
        index_digest=state.index_digest,
        working_tree_digest=state.working_tree_digest,
        dirty=state.dirty,
        state_digest=state.state_digest,
    )


def select_first_parent_series(repository_root: Path) -> SourceStateSeries:
    """Resolve committed HEAD and fill the five-slot first-parent model.

    ``rev-list --first-parent --max-count=5 HEAD`` is newest-first. Slots are
    returned oldest→newest. Missing older predecessors stay explicit empty
    slots rather than shifting newer commits left.
    """

    requested = repository_root.expanduser().resolve()
    git_root = resolve_containing_git_root(requested)
    if git_root is None:
        return _empty_series(
            requested,
            git_root=None,
            head_sha=None,
            reason=SourceStateUnavailableReason.MISSING_GIT,
            limitations=("missing_git",),
        )

    try:
        head_sha = run_readonly_git(["rev-parse", "HEAD"], cwd=git_root).strip()
    except ReadOnlyGitError:
        return _empty_series(
            requested,
            git_root=git_root,
            head_sha=None,
            reason=SourceStateUnavailableReason.HEAD_UNRESOLVED,
            limitations=("head_unresolved",),
        )
    if not _is_commit_sha(head_sha):
        return _empty_series(
            requested,
            git_root=git_root,
            head_sha=None,
            reason=SourceStateUnavailableReason.HEAD_UNRESOLVED,
            limitations=("head_unresolved",),
        )

    try:
        listed = run_readonly_git(
            ["rev-list", "--first-parent", f"--max-count={SERIES_SLOT_COUNT}", "HEAD"],
            cwd=git_root,
        )
    except ReadOnlyGitError:
        return _empty_series(
            requested,
            git_root=git_root,
            head_sha=head_sha,
            reason=SourceStateUnavailableReason.HEAD_UNRESOLVED,
            limitations=("rev_list_failed",),
        )

    newest_first = [line.strip() for line in listed.splitlines() if _is_commit_sha(line.strip())]
    if not newest_first:
        return _empty_series(
            requested,
            git_root=git_root,
            head_sha=head_sha,
            reason=SourceStateUnavailableReason.INSUFFICIENT_HISTORY,
            limitations=("insufficient_history",),
        )
    if newest_first[0] != head_sha:
        newest_first = [head_sha, *[sha for sha in newest_first if sha != head_sha]]
        newest_first = newest_first[:SERIES_SLOT_COUNT]

    oldest_first = list(reversed(newest_first))
    missing = SERIES_SLOT_COUNT - len(oldest_first)
    slots: list[SourceStateSlot] = []
    for index in range(SERIES_SLOT_COUNT):
        slot_number = index + 1
        if index < missing:
            slots.append(
                SourceStateSlot(
                    slot=slot_number,
                    sha=None,
                    available=False,
                    unavailable_reason=SourceStateUnavailableReason.INSUFFICIENT_HISTORY.value,
                )
            )
            continue
        slots.append(
            SourceStateSlot(
                slot=slot_number,
                sha=oldest_first[index - missing],
                available=True,
                unavailable_reason=None,
            )
        )
    limitations: list[str] = []
    if missing:
        limitations.append("insufficient_history")
    return SourceStateSeries(
        requested_root=requested,
        git_root=git_root,
        assessment_relpath=relative_assessment_path(requested, git_root),
        head_sha=head_sha,
        slots=tuple(slots),
        limitations=tuple(limitations),
    )


def materialize_commit_tree(git_root: Path, sha: str, destination: Path) -> MaterializedSnapshot:
    """Write the commit tree at ``sha`` into ``destination``. Never touches ``git_root``."""

    if not _is_commit_sha(sha):
        return MaterializedSnapshot(
            slot=SourceStateSlot(
                slot=0,
                sha=sha,
                available=False,
                unavailable_reason=SourceStateUnavailableReason.MATERIALIZE_FAILED.value,
            ),
            root=None,
            file_count=0,
            limitations=("invalid_sha",),
        )
    destination.mkdir(parents=True, exist_ok=True)
    dest = destination.resolve()
    limitations: list[str] = []
    written = 0
    try:
        entries, path_limitations = _list_tree(git_root, sha)
        limitations.extend(path_limitations)
    except ReadOnlyGitError as error:
        return MaterializedSnapshot(
            slot=SourceStateSlot(
                slot=0,
                sha=sha,
                available=False,
                unavailable_reason=SourceStateUnavailableReason.MATERIALIZE_FAILED.value,
            ),
            root=None,
            file_count=0,
            limitations=(f"ls_tree_failed:{error}",),
        )

    for entry in entries:
        relative = _safe_relative_path(entry.path)
        if relative is None:
            limitations.append(f"skipped_unsafe_path:{entry.path}")
            continue
        target = dest.joinpath(*relative.parts)
        if not _is_within(target, dest):
            limitations.append(f"skipped_unsafe_path:{entry.path}")
            continue
        if entry.object_type == "commit" or entry.mode == GITLINK_MODE:
            limitations.append(f"skipped_submodule:{entry.path}")
            continue
        if entry.object_type != "blob":
            limitations.append(f"skipped_object_type:{entry.path}:{entry.object_type}")
            continue
        try:
            payload = run_readonly_git_bytes(["cat-file", "blob", entry.object_id], cwd=git_root)
        except ReadOnlyGitError as error:
            limitations.append(f"skipped_blob:{entry.path}:{error}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.mode == SYMLINK_MODE:
            if not _safe_symlink_target(payload, dest, target):
                limitations.append(f"skipped_escaping_symlink:{entry.path}")
                continue
            target.symlink_to(os.fsdecode(payload))
            written += 1
            continue
        target.write_bytes(payload)
        if entry.mode.endswith("755"):
            target.chmod(target.stat().st_mode | 0o111)
        written += 1

    return MaterializedSnapshot(
        slot=SourceStateSlot(slot=0, sha=sha, available=True, unavailable_reason=None),
        root=dest,
        file_count=written,
        limitations=tuple(dict.fromkeys(limitations)),
    )


class SnapshotWorkspace:
    """Materialize available slots under an isolated temp root and clean it up."""

    def __init__(self, series: SourceStateSeries) -> None:
        self.series = series
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self.snapshots: tuple[MaterializedSnapshot, ...] = ()

    def __enter__(self) -> SnapshotWorkspace:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="codestrata-r2-source-")
        base = Path(self._tmpdir.name)
        realized: list[MaterializedSnapshot] = []
        try:
            git_root = self.series.git_root
            for slot in self.series.slots:
                dest = base / f"s{slot.slot}"
                if not slot.available or slot.sha is None or git_root is None:
                    realized.append(
                        MaterializedSnapshot(
                            slot=slot,
                            root=None,
                            file_count=0,
                            limitations=(() if slot.unavailable_reason else ("slot_unavailable",)),
                        )
                    )
                    continue
                snapshot = materialize_commit_tree(git_root, slot.sha, dest)
                realized.append(
                    MaterializedSnapshot(
                        slot=slot,
                        root=snapshot.root,
                        file_count=snapshot.file_count,
                        limitations=snapshot.limitations,
                    )
                )
        except Exception:
            self.close()
            raise
        self.snapshots = tuple(realized)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None


def _empty_series(
    requested: Path,
    *,
    git_root: Path | None,
    head_sha: str | None,
    reason: SourceStateUnavailableReason,
    limitations: tuple[str, ...],
) -> SourceStateSeries:
    slots = tuple(
        SourceStateSlot(
            slot=index,
            sha=None,
            available=False,
            unavailable_reason=reason.value,
        )
        for index in range(1, SERIES_SLOT_COUNT + 1)
    )
    return SourceStateSeries(
        requested_root=requested,
        git_root=git_root,
        assessment_relpath=relative_assessment_path(requested, git_root),
        head_sha=head_sha,
        slots=slots,
        limitations=limitations,
    )


def relative_assessment_path(requested_root: Path, git_root: Path | None) -> str:
    """Return the requested assess root relative to the containing Git root.

    Git identity stays on the containing repository. An empty string means the
    requested path is the Git root and the whole tree is assessed.
    """

    if git_root is None:
        return ""
    requested = requested_root.expanduser().resolve()
    root = git_root.expanduser().resolve()
    if requested == root:
        return ""
    try:
        relative = requested.relative_to(root)
    except ValueError:
        return ""
    if not relative.parts or relative.parts == (".",):
        return ""
    return relative.as_posix()


def snapshot_assessment_root(snapshot_root: Path, assessment_relpath: str) -> Path:
    """Return the historical equivalent of the requested assess root."""

    if not assessment_relpath:
        return snapshot_root
    return snapshot_root.joinpath(*Path(assessment_relpath).parts)


def attach_readonly_gitdir(snapshot_root: Path, git_root: Path) -> Path:
    """Point an extracted tree at the real object store without mutating it.

    Writes only ``snapshot_root/.git`` (a gitdir file). The user's repository
    is not modified.
    """

    git_dir = run_readonly_git(["rev-parse", "--absolute-git-dir"], cwd=git_root).strip()
    marker = snapshot_root / ".git"
    marker.write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    return marker


def _list_tree(git_root: Path, sha: str) -> tuple[tuple[_TreeEntry, ...], tuple[str, ...]]:
    output = run_readonly_git_bytes(["ls-tree", "-z", "-r", sha], cwd=git_root)
    entries: list[_TreeEntry] = []
    limitations: list[str] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        meta, separator, path_bytes = record.partition(b"\t")
        if not separator:
            continue
        try:
            path = path_bytes.decode("utf-8")
            header = meta.decode("ascii")
        except UnicodeDecodeError:
            limitations.append("unsupported_non_utf8_path")
            continue
        mode, object_type, object_id = header.split(" ", 2)
        entries.append(
            _TreeEntry(mode=mode, object_type=object_type, object_id=object_id, path=path)
        )
    return tuple(entries), tuple(dict.fromkeys(limitations))


def _is_commit_sha(value: str) -> bool:
    if len(value) != 40:
        return False
    return all(char in "0123456789abcdef" for char in value.lower())


def _safe_relative_path(raw: str) -> Path | None:
    if not raw or raw.startswith("/") or raw.startswith("\\"):
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or path.parts[:1] == (".git",):
        return None
    if any(part == ".git" for part in path.parts):
        return None
    return path


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _safe_symlink_target(payload: bytes, dest: Path, link_path: Path) -> bool:
    try:
        text = os.fsdecode(payload)
    except Exception:  # noqa: BLE001 - refuse undecodable link targets
        return False
    if not text or Path(text).is_absolute():
        return False
    candidate = Path(text)
    if ".." in candidate.parts:
        # Allow relative hops only when the resolved location stays in dest.
        resolved = (link_path.parent / candidate).resolve()
        return _is_within(resolved, dest)
    resolved = (link_path.parent / candidate).resolve()
    return _is_within(resolved, dest)


def iter_available_shas(series: SourceStateSeries) -> Iterator[str]:
    for slot in series.available_slots():
        if slot.sha:
            yield slot.sha
