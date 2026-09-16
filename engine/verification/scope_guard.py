"""Engine-only cumulative scope guard.

``evaluate_repository(repo)`` is the public entry. It:

1. Refuses a non-git directory (ERROR, never PASS).
2. Collects git events (see ``git_changes``).
3. Drops exact duplicates across views.
4. Marks ``engine/`` paths in-scope.
5. Marks pre-inventory outside paths as ignored (not FAIL).
6. Fails any other outside path, including rename source or dest.

Statuses: PASS | FAIL | ERROR | BUDGET.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from verification.git_changes import (
    DEFAULT_MAX_EVENTS,
    GitUnsupportedError,
    PathEvent,
    collect_events,
    is_git_repository,
    resolve_default_base,
)
from verification.inventory import WorkingTreeInventory, load_inventory
from verification.paths import both_under_engine, is_under_engine, path_escapes_tree


@dataclass(frozen=True)
class OutOfScopeFinding:
    event: PathEvent
    reason: str


@dataclass(frozen=True)
class ScopeVerdict:
    status: str
    inspected_count: int
    findings: tuple[OutOfScopeFinding, ...]
    preexisting_ignored: tuple[PathEvent, ...]
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


def _event_paths(event: PathEvent) -> tuple[str, ...]:
    if event.source_path and event.dest_path:
        return (event.source_path, event.dest_path)
    return (event.path,)


def _in_scope(event: PathEvent) -> bool:
    if event.source_path and event.dest_path:
        return both_under_engine(event.source_path, event.dest_path)
    path = event.path
    if path_escapes_tree(path):
        return False
    return is_under_engine(path)


def _reason(event: PathEvent) -> str:
    if event.source_path and event.dest_path:
        return (
            "rename source or destination is outside engine/ "
            f"({event.source_path} -> {event.dest_path})"
        )
    if event.status == "deleted":
        return f"deletion outside engine/: {event.path}"
    if event.status == "untracked":
        return f"untracked path outside engine/: {event.path}"
    return f"{event.status} path outside engine/: {event.path}"


def evaluate_events(
    events: tuple[PathEvent, ...],
    *,
    inventory: WorkingTreeInventory | None = None,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> ScopeVerdict:
    if len(events) > max_events:
        return ScopeVerdict(
            status="BUDGET",
            inspected_count=len(events),
            findings=(),
            preexisting_ignored=(),
            message=(
                f"inspected {len(events)} path events, exceeding budget {max_events}; "
                "refusing to silently truncate"
            ),
        )
    allowed_preexisting = inventory.preexisting_paths() if inventory else frozenset()
    findings: list[OutOfScopeFinding] = []
    ignored: list[PathEvent] = []
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    unique_events: list[PathEvent] = []
    for event in events:
        key = (event.origin, event.status, event.path, event.source_path, event.dest_path)
        if key in seen:
            continue
        seen.add(key)
        unique_events.append(event)
    for event in unique_events:
        if _in_scope(event):
            continue
        if allowed_preexisting.intersection(_event_paths(event)):
            ignored.append(event)
            continue
        findings.append(OutOfScopeFinding(event=event, reason=_reason(event)))
    if findings:
        return ScopeVerdict(
            status="FAIL",
            inspected_count=len(unique_events),
            findings=tuple(findings),
            preexisting_ignored=tuple(ignored),
            message=f"{len(findings)} out-of-scope path event(s) under inspection",
        )
    return ScopeVerdict(
        status="PASS",
        inspected_count=len(unique_events),
        findings=(),
        preexisting_ignored=tuple(ignored),
        message="all inspected tracked/untracked/rename/delete events remain under engine/",
    )


def evaluate_repository(
    repo: Path,
    *,
    base_ref: str | None = None,
    inventory_path: Path | None = None,
    max_events: int = DEFAULT_MAX_EVENTS,
) -> ScopeVerdict:
    if not is_git_repository(repo):
        return ScopeVerdict(
            status="ERROR",
            inspected_count=0,
            findings=(),
            preexisting_ignored=(),
            message=f"unsupported git inspection: {repo} is not a git work tree",
        )
    try:
        resolved_base = base_ref if base_ref is not None else resolve_default_base(repo)
        events = collect_events(repo, resolved_base)
    except (GitUnsupportedError, FileNotFoundError, NotADirectoryError) as exc:
        return ScopeVerdict(
            status="ERROR",
            inspected_count=0,
            findings=(),
            preexisting_ignored=(),
            message=f"unsupported git inspection: {exc}",
        )
    inventory = load_inventory(inventory_path) if inventory_path else None
    verdict = evaluate_events(events, inventory=inventory, max_events=max_events)
    if verdict.status == "PASS" and resolved_base is None:
        return ScopeVerdict(
            status="PASS",
            inspected_count=verdict.inspected_count,
            findings=verdict.findings,
            preexisting_ignored=verdict.preexisting_ignored,
            message=(
                f"{verdict.message}; cumulative base ref was unavailable, "
                "so only working-tree staged/unstaged/untracked events were inspected"
            ),
        )
    return verdict
<<<<<<< HEAD


# CLI: python -m verification scope
# Tests: engine/tests/verification/test_scope_guard.py
=======
>>>>>>> d010c37ab4cbb356908141b7e5277e0c47ea0912
