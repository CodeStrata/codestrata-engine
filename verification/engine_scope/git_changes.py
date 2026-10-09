"""Inspect git working tree, index, and cumulative release diffs.

Uses the system ``git`` executable. Never runs ``git reset`` or otherwise
mutates the inspected worktree.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from verification.engine_scope.inventory import InventoryEntry
from verification.engine_scope.models import ChangeKind, ChangeOrigin, PathChange
from verification.engine_scope.paths import posix_relpath

_STATUS_KIND: dict[str, ChangeKind] = {
    "A": ChangeKind.ADDED,
    "C": ChangeKind.COPIED,
    "D": ChangeKind.DELETED,
    "M": ChangeKind.MODIFIED,
    "R": ChangeKind.RENAMED,
    "T": ChangeKind.TYPECHANGE,
    "U": ChangeKind.UNKNOWN,
    "?": ChangeKind.UNTRACKED,
}


class GitError(RuntimeError):
    """Git is missing, the directory is not a repo, or a ref cannot be resolved."""


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_OPTIONAL_LOCKS", "0")
    return env


def run_git(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=_git_env(),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitError(f"git {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed.stdout


def kind_from_status_code(code: str) -> ChangeKind:
    if not code:
        return ChangeKind.UNKNOWN
    return _STATUS_KIND.get(code[0], ChangeKind.UNKNOWN)


def parse_name_status_z(payload: str, origin: ChangeOrigin) -> tuple[PathChange, ...]:
    """Parse NUL-separated ``git diff -z --name-status``.

    Ordinary records are ``STATUS\\0path\\0``. Renames/copies are
    ``R100\\0old\\0new\\0`` — both paths are kept so the guard can reject a
    move that crosses ``engine/``.
    """

    if not payload:
        return ()
    tokens = payload.split("\0")
    changes: list[PathChange] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token:
            index += 1
            continue
        status = token
        score: str | None = None
        code = status[0]
        if len(status) > 1 and status[1:].isdigit():
            score = status[1:]
        index += 1
        if code in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise GitError("truncated rename/copy name-status record")
            old_path = posix_relpath(tokens[index])
            new_path = posix_relpath(tokens[index + 1])
            index += 2
            changes.append(
                PathChange(
                    path=new_path,
                    kind=kind_from_status_code(code),
                    origin=origin,
                    old_path=old_path,
                    score=score,
                    staged=origin is ChangeOrigin.INDEX,
                    unstaged=origin is ChangeOrigin.WORKING_TREE,
                )
            )
            continue
        if index >= len(tokens):
            raise GitError("truncated name-status record")
        path = posix_relpath(tokens[index])
        index += 1
        changes.append(
            PathChange(
                path=path,
                kind=kind_from_status_code(code),
                origin=origin,
                staged=origin is ChangeOrigin.INDEX,
                unstaged=origin is ChangeOrigin.WORKING_TREE,
            )
        )
    return tuple(changes)


def parse_porcelain_v1(payload: str) -> tuple[PathChange, ...]:
    """Parse ``git status --porcelain=v1``.

    Column X is the index, column Y is the worktree. ``??`` is untracked.
    Renames look like ``R  old -> new``; both sides are stored on PathChange.
    """

    changes: list[PathChange] = []
    for raw_line in payload.splitlines():
        if len(raw_line) < 4:
            continue
        # porcelain v1: XY<space>path  (X=index, Y=worktree)
        x_status, y_status = raw_line[0], raw_line[1]
        rest = raw_line[3:]
        old_path: str | None = None
        path = rest
        if " -> " in rest and (x_status in {"R", "C"} or y_status in {"R", "C"}):
            left, right = rest.split(" -> ", 1)
            old_path = posix_relpath(left)
            path = posix_relpath(right)
        else:
            path = posix_relpath(rest)
        staged = x_status not in {" ", "?"}
        unstaged = y_status not in {" ", "?"} or x_status == "?"
        if x_status == "?" and y_status == "?":
            kind = ChangeKind.UNTRACKED
            origin = ChangeOrigin.WORKING_TREE
            code = "?"
        elif x_status in {"R", "C"}:
            kind = kind_from_status_code(x_status)
            origin = ChangeOrigin.INDEX
            code = x_status
        elif y_status in {"R", "C"}:
            kind = kind_from_status_code(y_status)
            origin = ChangeOrigin.WORKING_TREE
            code = y_status
        elif x_status not in {" ", "?"}:
            kind = kind_from_status_code(x_status)
            origin = ChangeOrigin.INDEX
            code = x_status
        else:
            kind = kind_from_status_code(y_status)
            origin = ChangeOrigin.WORKING_TREE
            code = y_status
        del code
        changes.append(
            PathChange(
                path=path,
                kind=kind,
                origin=origin,
                old_path=old_path,
                staged=staged,
                unstaged=unstaged,
            )
        )
    return tuple(changes)


def porcelain_to_inventory(changes: tuple[PathChange, ...]) -> tuple[InventoryEntry, ...]:
    return tuple(
        InventoryEntry(
            path=change.path,
            kind=change.kind,
            old_path=change.old_path,
            status=f"{'S' if change.staged else ' '}{'U' if change.unstaged else ' '}",
        )
        for change in changes
    )


def collect_working_tree(repo_root: Path) -> tuple[PathChange, ...]:
    output = run_git(repo_root, ["status", "--porcelain=v1", "-uall"])
    return parse_porcelain_v1(output)


def collect_index_diff(repo_root: Path) -> tuple[PathChange, ...]:
    output = run_git(repo_root, ["diff", "-z", "--cached", "--name-status", "-M", "-C"])
    return parse_name_status_z(output, ChangeOrigin.INDEX)


def collect_unstaged_diff(repo_root: Path) -> tuple[PathChange, ...]:
    output = run_git(repo_root, ["diff", "-z", "--name-status", "-M", "-C"])
    return parse_name_status_z(output, ChangeOrigin.WORKING_TREE)


def collect_cumulative(repo_root: Path, baseline_ref: str) -> tuple[PathChange, ...]:
    """Committed-plus-index-plus-worktree names versus ``baseline_ref``.

    Uses ``git diff baseline`` (three trees merged by git) so staged, unstaged,
    and committed-since-baseline paths are all present. Callers still inspect
    porcelain separately for untracked files, which ``git diff`` omits.
    """

    output = run_git(repo_root, ["diff", "-z", "--name-status", "-M", "-C", baseline_ref])
    return parse_name_status_z(output, ChangeOrigin.CUMULATIVE)


def collect_committed_range(repo_root: Path, baseline_ref: str) -> tuple[PathChange, ...]:
    """Only commits reachable from HEAD since merge-base with baseline."""
    output = run_git(
        repo_root,
        ["diff", "-z", "--name-status", "-M", "-C", f"{baseline_ref}...HEAD"],
    )
    return parse_name_status_z(output, ChangeOrigin.CUMULATIVE)
