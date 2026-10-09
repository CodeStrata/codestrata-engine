"""Capture and compare a pre-existing working-tree inventory.

The guard never resets unrelated work. Paths recorded here are excluded from
*working-tree* violations so a dirty checkout of other packages does not fail
an Engine-only story. Committed cumulative diffs are not grandfathered.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from verification.engine_scope.models import ChangeKind, InventoryEntry
from verification.engine_scope.paths import posix_relpath

INVENTORY_SCHEMA = "codestrata.engine_scope.inventory.v1"


def inventory_key(path: str, old_path: str | None = None) -> tuple[str, str]:
    return (posix_relpath(path), posix_relpath(old_path) if old_path else "")


def entries_from_mapping(payload: object) -> tuple[InventoryEntry, ...]:
    if not isinstance(payload, dict):
        raise ValueError("inventory payload must be an object")
    raw_entries = payload.get("entries", [])
    if not isinstance(raw_entries, list):
        raise ValueError("inventory.entries must be a list")
    entries: list[InventoryEntry] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            raise ValueError("inventory entry must be an object")
        path = posix_relpath(str(item.get("path", "")))
        if not path:
            raise ValueError("inventory entry is missing path")
        old = item.get("old_path")
        old_path = posix_relpath(str(old)) if old else None
        kind_raw = str(item.get("kind", ChangeKind.UNKNOWN.value))
        try:
            kind = ChangeKind(kind_raw)
        except ValueError:
            kind = ChangeKind.UNKNOWN
        entries.append(
            InventoryEntry(
                path=path,
                kind=kind,
                old_path=old_path,
                status=str(item.get("status", "")),
            )
        )
    return tuple(entries)


def load_inventory(path: Path) -> tuple[InventoryEntry, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return entries_from_mapping(payload)


def dump_inventory(
    entries: Iterable[InventoryEntry],
    *,
    baseline_ref: str = "",
    repo_root: str = "",
) -> dict[str, object]:
    serialized = [
        {
            "path": entry.path,
            "old_path": entry.old_path,
            "kind": entry.kind.value,
            "status": entry.status,
        }
        for entry in entries
    ]
    return {
        "schema": INVENTORY_SCHEMA,
        "baseline_ref": baseline_ref,
        "repo_root": repo_root,
        "entries": serialized,
    }


def write_inventory(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def in_inventory(entries: Iterable[InventoryEntry], path: str, old_path: str | None) -> bool:
    """True if this dirty path was already present when the story started."""
    wanted = {inventory_key(entry.path, entry.old_path) for entry in entries}
    current = inventory_key(path, old_path)
    if current in wanted:
        return True
    # Untracked/deleted inventory matches on the current path alone so a later
    # content edit of the same outside-Engine file stays grandfathered.
    path_only = {inventory_key(entry.path, None)[0] for entry in entries}
    return posix_relpath(path) in path_only or (
        old_path is not None and posix_relpath(old_path) in path_only
    )
