"""Pre-existing working-tree inventory.

E00.2 must inspect dirty files without ``git reset``. Paths listed in
``preexisting-working-tree-inventory.json`` were already dirty when the story
started. If they sit outside ``engine/``, the guard reports them as ignored
instead of FAIL so unrelated work is not blamed on this change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InventoryEntry:
    status: str
    path: str
    source_path: str | None = None
    dest_path: str | None = None


@dataclass(frozen=True)
class WorkingTreeInventory:
    recorded_at: str
    checkout_sha: str
    branch: str
    entries: tuple[InventoryEntry, ...]

    def preexisting_paths(self) -> frozenset[str]:
        paths: set[str] = set()
        for entry in self.entries:
            paths.add(entry.path)
            if entry.source_path:
                paths.add(entry.source_path)
            if entry.dest_path:
                paths.add(entry.dest_path)
        return frozenset(paths)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def load_inventory(path: Path) -> WorkingTreeInventory:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    entries = tuple(
        InventoryEntry(
            status=str(item["status"]),
            path=str(item["path"]),
            source_path=_optional_str(item.get("source_path")),
            dest_path=_optional_str(item.get("dest_path")),
        )
        for item in raw.get("entries", [])
    )
    return WorkingTreeInventory(
        recorded_at=str(raw["recorded_at"]),
        checkout_sha=str(raw["checkout_sha"]),
        branch=str(raw["branch"]),
        entries=entries,
    )


# Default file: preexisting-working-tree-inventory.json next to this package.
