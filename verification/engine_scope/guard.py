"""Decide whether a checkout stays inside ``engine/``.

Flow:
1. Collect porcelain (untracked + staged + unstaged), worktree-vs-baseline,
   and committed ``baseline...HEAD``.
2. Any involved path not under ``engine/`` is a violation.
3. Inventory may grandfather *dirty* outside-Engine files so unrelated local
   work is not reset or failed. Committed diffs are never grandfathered.
"""

from __future__ import annotations

from pathlib import Path

from verification.engine_scope.git_changes import (
    GitError,
    collect_committed_range,
    collect_cumulative,
    collect_working_tree,
)
from verification.engine_scope.inventory import InventoryEntry, in_inventory
from verification.engine_scope.models import (
    ChangeKind,
    ChangeOrigin,
    PathChange,
    ScopeReport,
    ScopeViolation,
)
from verification.engine_scope.paths import is_engine_owned, named_outside_surface, posix_relpath


def _dedupe(changes: tuple[PathChange, ...]) -> tuple[PathChange, ...]:
    seen: set[tuple[object, ...]] = set()
    unique: list[PathChange] = []
    for change in changes:
        key = (
            change.path,
            change.kind,
            change.origin,
            change.old_path,
            change.staged,
            change.unstaged,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(change)
    return tuple(unique)


def _violation_for(change: PathChange) -> ScopeViolation | None:
    """First non-engine path on this change wins (rename reports both ends)."""

    for involved in change.involved_paths():
        if is_engine_owned(involved):
            continue
        surface = named_outside_surface(involved)
        reason = f"{change.kind.value} path '{posix_relpath(involved)}' is outside engine/"
        if surface:
            reason = f"{reason} (named surface {surface})"
        if change.kind is ChangeKind.RENAMED and change.old_path:
            reason = f"rename '{change.old_path}' -> '{change.path}' crosses the engine/ boundary"
        return ScopeViolation(change=change, reason=reason, named_surface=surface)
    return None


def classify_changes(
    changes: tuple[PathChange, ...],
    inventory: tuple[InventoryEntry, ...],
) -> tuple[tuple[ScopeViolation, ...], tuple[PathChange, ...]]:
    """Return (violations, grandfathered working-tree changes)."""

    violations: list[ScopeViolation] = []
    grandfathered: list[PathChange] = []
    for change in changes:
        candidate = _violation_for(change)
        if candidate is None:
            continue
        # Inventory applies only to live dirty state, not to commits on the
        # release branch — those must stay Engine-only.
        working = change.origin is not ChangeOrigin.CUMULATIVE
        if working and in_inventory(inventory, change.path, change.old_path):
            grandfathered.append(change)
            continue
        violations.append(candidate)
    return tuple(violations), tuple(grandfathered)


def evaluate_scope(
    *,
    repo_root: Path,
    baseline_ref: str,
    inventory: tuple[InventoryEntry, ...] = (),
) -> ScopeReport:
    """Inspect git only. A git failure is FAIL, never an implied PASS."""

    notes: list[str] = []
    extra: dict[str, str] = {"repo_root": str(repo_root)}
    try:
        working = collect_working_tree(repo_root)
        cumulative_worktree = collect_cumulative(repo_root, baseline_ref)
        committed = collect_committed_range(repo_root, baseline_ref)
    except GitError as exc:
        return ScopeReport(
            ok=False,
            baseline_ref=baseline_ref,
            inventory_size=len(inventory),
            changes=(),
            violations=(
                ScopeViolation(
                    change=PathChange(
                        path=".",
                        kind=ChangeKind.UNKNOWN,
                        origin=ChangeOrigin.WORKING_TREE,
                    ),
                    reason=str(exc),
                ),
            ),
            grandfathered=(),
            notes=("git inspection failed; no mutation of the worktree was attempted",),
            extra=extra,
        )

    inspected = _dedupe(working + cumulative_worktree + committed)
    working_violations, grandfathered = classify_changes(working, inventory)
    # Cumulative committed range is never grandfathered from a dirty inventory.
    committed_violations, _ = classify_changes(committed, ())
    # Cumulative worktree-vs-baseline includes dirty files; grandfather those.
    cumulative_violations, extra_grand = classify_changes(cumulative_worktree, inventory)

    violations = _dedupe_violations(
        working_violations + committed_violations + cumulative_violations
    )
    all_grand = _dedupe(grandfathered + extra_grand)
    if all_grand:
        notes.append(
            f"{len(all_grand)} pre-existing outside-Engine path(s) ignored; worktree was not reset"
        )
    notes.append("root engine-tests job is pytest-only and does not prove lint/type/coverage")
    return ScopeReport(
        ok=len(violations) == 0,
        baseline_ref=baseline_ref,
        inventory_size=len(inventory),
        changes=inspected,
        violations=violations,
        grandfathered=all_grand,
        notes=tuple(notes),
        extra=extra,
    )


def _dedupe_violations(violations: tuple[ScopeViolation, ...]) -> tuple[ScopeViolation, ...]:
    seen: set[tuple[object, ...]] = set()
    unique: list[ScopeViolation] = []
    for item in violations:
        key = (
            item.change.path,
            item.change.old_path,
            item.change.kind,
            item.reason,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)
