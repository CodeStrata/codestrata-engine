"""Canonicalization for deterministic report comparisons (Phase 5.12)."""

from __future__ import annotations

import copy
from typing import Any

from codestrata.reporting.contract.constants import VOLATILE_JSON_PATHS


def _delete_path(payload: dict[str, Any], dotted: str) -> None:
    parts = dotted.split(".")
    cursor: Any = payload
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return
        cursor = cursor[part]
    if isinstance(cursor, dict):
        cursor.pop(parts[-1], None)


def strip_volatile_fields(
    document: dict[str, Any],
    *,
    extra_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return a deep copy of ``document`` with volatile fields removed."""

    cloned = copy.deepcopy(document)
    for path in (*VOLATILE_JSON_PATHS, *extra_paths):
        _delete_path(cloned, path)
    # Duration fields nested under static_analysis providers.
    static = cloned.get("assessment", {}).get("static_analysis")
    if isinstance(static, dict):
        for key, value in list(static.items()):
            if isinstance(value, dict):
                value.pop("duration_ms", None)
                value.pop("latency_ms", None)
            if key.endswith("_ms"):
                static.pop(key, None)
    return cloned


def reports_structurally_equal(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    """Compare two report documents ignoring volatile metadata."""

    return strip_volatile_fields(left) == strip_volatile_fields(right)
