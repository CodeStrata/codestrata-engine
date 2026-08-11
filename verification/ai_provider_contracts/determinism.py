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


__all__ = [
    "canonical_json",
    "reports_are_identical",
    "stable_hash",
]
