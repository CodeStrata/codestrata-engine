"""Models for Engine-only scope inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ChangeKind(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNTRACKED = "untracked"
    TYPECHANGE = "typechange"
    UNKNOWN = "unknown"


class ChangeOrigin(StrEnum):
    """Where git reported the change.

    WORKING_TREE / INDEX come from ``git status`` (includes untracked).
    CUMULATIVE comes from ``git diff <baseline>`` / ``<baseline>...HEAD``.
    Only working-tree/index hits can be grandfathered via inventory.
    """

    WORKING_TREE = "working_tree"
    INDEX = "index"
    CUMULATIVE = "cumulative"


@dataclass(frozen=True, slots=True)
class PathChange:
    """One inspected path mutation (working tree, index, or cumulative diff)."""

    path: str
    kind: ChangeKind
    origin: ChangeOrigin
    old_path: str | None = None
    staged: bool = False
    unstaged: bool = False
    score: str | None = None

    def involved_paths(self) -> tuple[str, ...]:
        """Rename/copy must keep *both* old and new paths under engine/."""

        if self.old_path:
            return (self.old_path, self.path)
        return (self.path,)


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    """A pre-existing dirty/untracked path captured before this story's work."""

    path: str
    kind: ChangeKind
    old_path: str | None = None
    status: str = ""


@dataclass(frozen=True, slots=True)
class ScopeViolation:
    change: PathChange
    reason: str
    named_surface: str | None = None
    grandfathered: bool = False


@dataclass(frozen=True, slots=True)
class ScopeReport:
    ok: bool
    baseline_ref: str
    inventory_size: int
    changes: tuple[PathChange, ...]
    violations: tuple[ScopeViolation, ...]
    grandfathered: tuple[PathChange, ...]
    notes: tuple[str, ...] = ()
    extra: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        if self.ok:
            return (
                f"PASS: {len(self.changes)} inspected path(s) remain under engine/; "
                f"{len(self.grandfathered)} pre-existing outside-Engine path(s) ignored"
            )
        return (
            f"FAIL: {len(self.violations)} outside-Engine path mutation(s) "
            f"(baseline {self.baseline_ref})"
        )
