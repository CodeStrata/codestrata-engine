"""Determinism helpers: two runs of this suite must produce identical JSON."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def reports_are_identical(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return canonical_json(first) == canonical_json(second)


def diff_keys(first: dict[str, Any], second: dict[str, Any], *, prefix: str = "") -> list[str]:
    """Return dotted key paths whose values differ between two report dicts."""

    differences: list[str] = []
    keys = sorted(set(first) | set(second))
    for key in keys:
        path = f"{prefix}.{key}" if prefix else key
        if key not in first or key not in second:
            differences.append(path)
            continue
        left, right = first[key], second[key]
        if isinstance(left, dict) and isinstance(right, dict):
            differences.extend(diff_keys(left, right, prefix=path))
        elif left != right:
            differences.append(path)
    return differences


__all__ = [
    "canonical_json",
    "diff_keys",
    "reports_are_identical",
    "stable_hash",
]
