"""Git working-tree and cumulative-diff inspection.

``collect_events`` unions four git views so a leak cannot hide in one of them:

* ``cumulative`` — commits on this branch vs ``release/engine-next`` (``A...B``)
* ``staged``     — index vs HEAD
* ``unstaged``   — worktree vs index
* ``untracked``  — files git does not track yet

``-M`` reports renames. ``-z`` is NUL-separated so paths with spaces stay one record.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# Hard stop if a huge diff would otherwise be silently truncated.
DEFAULT_MAX_EVENTS = 10_000


class GitUnsupportedError(RuntimeError):
    """Repository is missing or git cannot inspect it."""


@dataclass(frozen=True)
class PathEvent:
    """One inspected path change.

    ``origin`` is which git view produced it (cumulative/staged/unstaged/untracked).
    For renames, ``source_path`` is the old path and ``dest_path`` / ``path`` the new one.
    """

    origin: str
    status: str
    path: str
    source_path: str | None = None
    dest_path: str | None = None

    @property
    def rename_source(self) -> str | None:
        return self.source_path

    @property
    def rename_dest(self) -> str | None:
        return self.dest_path


def _run_git(repo: Path, args: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise GitUnsupportedError("git executable is not available") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GitUnsupportedError(stderr or f"git {' '.join(args)} failed")
    return completed.stdout


def is_git_repository(repo: Path) -> bool:
    if not repo.is_dir():
        return False
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def parse_name_status_z(payload: bytes) -> tuple[tuple[str, str, str | None], ...]:
    """Parse ``git diff -z --name-status`` output.

    Each record is ``STATUS\\0PATH\\0`` or ``Rxxx\\0OLD\\0NEW\\0``.
    The returned tuple is ``(status, path, source_or_none)``; *path* is the
    destination for a rename.
    """
    if not payload:
        return ()
    parts = payload.split(b"\0")
    records: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(parts):
        token = parts[index].decode("utf-8", errors="replace")
        if token == "":
            index += 1
            continue
        status = token
        if status.startswith(("R", "C")):
            if index + 2 >= len(parts):
                break
            source = parts[index + 1].decode("utf-8", errors="replace").replace("\\", "/")
            dest = parts[index + 2].decode("utf-8", errors="replace").replace("\\", "/")
            records.append((status, dest, source))
            index += 3
            continue
        if index + 1 >= len(parts):
            break
        path = parts[index + 1].decode("utf-8", errors="replace").replace("\\", "/")
        records.append((status, path, None))
        index += 2
    return tuple(records)


def _events_from_name_status(origin: str, payload: bytes) -> tuple[PathEvent, ...]:
    events: list[PathEvent] = []
    for status, path, source in parse_name_status_z(payload):
        if source is not None:
            events.append(
                PathEvent(
                    origin=origin,
                    status="renamed",
                    path=path,
                    source_path=source,
                    dest_path=path,
                )
            )
        elif status.startswith("D"):
            events.append(PathEvent(origin=origin, status="deleted", path=path))
        elif status.startswith("A"):
            events.append(PathEvent(origin=origin, status="added", path=path))
        else:
            events.append(PathEvent(origin=origin, status="modified", path=path))
    return tuple(events)


def untracked_events(repo: Path) -> tuple[PathEvent, ...]:
    payload = _run_git(repo, ["ls-files", "-z", "--others", "--exclude-standard"])
    events: list[PathEvent] = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", errors="replace").replace("\\", "/")
        events.append(PathEvent(origin="untracked", status="untracked", path=path))
    return tuple(events)


def collect_events(repo: Path, base_ref: str | None) -> tuple[PathEvent, ...]:
    """Return every path event the scope guard must inspect."""
    if not is_git_repository(repo):
        raise GitUnsupportedError(f"{repo} is not a git work tree")
    events: list[PathEvent] = []
    if base_ref:
        events.extend(
            _events_from_name_status(
                "cumulative",
                _run_git(repo, ["diff", "-z", "--name-status", "-M", f"{base_ref}...HEAD"]),
            )
        )
    events.extend(
        _events_from_name_status(
            "staged",
            _run_git(repo, ["diff", "-z", "--cached", "--name-status", "-M"]),
        )
    )
    events.extend(
        _events_from_name_status(
            "unstaged",
            _run_git(repo, ["diff", "-z", "--name-status", "-M"]),
        )
    )
    events.extend(untracked_events(repo))
    return tuple(events)


def resolve_default_base(repo: Path) -> str | None:
    """Prefer the local integration branch, then the origin copy."""
    for candidate in ("release/engine-next", "origin/release/engine-next"):
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            cwd=repo,
            check=False,
            capture_output=True,
        )
        if completed.returncode == 0:
            return candidate
    return None


# Next: scope_guard.evaluate_events / evaluate_repository.
