"""Canonical serialization helpers for the pre-transport privacy gate."""

from __future__ import annotations

import json
from typing import Any


def canonical_event_bytes(payload: dict[str, Any]) -> bytes:
    """UTF-8 compact sorted JSON — exact form a future transport would use."""

    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return text.encode("utf-8")


def serialized_size_bucket(size_bytes: int) -> str:
    """Coarse size category for diagnostics — not an exact duration/size leak."""

    if size_bytes < 256:
        return "lt_256b"
    if size_bytes < 1024:
        return "b_256_1k"
    if size_bytes < 2048:
        return "b_1k_2k"
    if size_bytes < 4096:
        return "b_2k_4k"
    return "gte_4k"


__all__ = [
    "canonical_event_bytes",
    "serialized_size_bucket",
]
