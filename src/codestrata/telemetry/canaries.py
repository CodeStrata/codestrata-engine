"""Prohibited-data scanners for logs, retry queues, and serialization (E13.1).

These helpers never transmit. They detect forbidden field names and value
markers so local adapters can drop a payload instead of queuing or logging it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from typing import Any

from codestrata.telemetry.constants import FORBIDDEN_SUBSTRINGS
from codestrata.telemetry.privacy import FORBIDDEN_FIELD_NAMES
from codestrata.telemetry.runtime_policy import DEFAULT_MAX_EVENT_SIZE_BYTES

# Evidence/graph identity that must never ride telemetry serialization.
_EVIDENCE_GRAPH_MARKERS: frozenset[str] = frozenset(
    {
        "codegraph",
        "finding_id",
        "graph-node",
        "repository_name",
        "source_code",
        "snippet",
    }
)

PROHIBITED_VALUE_MARKERS: frozenset[str] = frozenset(
    str(item).lower() for item in (FORBIDDEN_SUBSTRINGS | _EVIDENCE_GRAPH_MARKERS)
)


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def iter_field_names(obj: object) -> Iterable[str]:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield str(key)
            yield from iter_field_names(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_field_names(item)


def prohibited_value_matches(blob: str) -> tuple[str, ...]:
    lowered = blob.lower()
    return tuple(sorted(marker for marker in PROHIBITED_VALUE_MARKERS if marker in lowered))


def prohibited_field_matches(obj: object) -> tuple[str, ...]:
    hits = {name for name in iter_field_names(obj) if name in FORBIDDEN_FIELD_NAMES}
    return tuple(sorted(hits))


def serialized_size_bytes(obj: object) -> int:
    try:
        return len(canonical_json(obj).encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_MAX_EVENT_SIZE_BYTES + 1


def exceeds_serialization_budget(
    obj: object,
    *,
    max_bytes: int = DEFAULT_MAX_EVENT_SIZE_BYTES,
) -> bool:
    return serialized_size_bytes(obj) > max_bytes


def collection_surface_violations(obj: object) -> tuple[str, ...]:
    """Return prohibited field names and value markers found in ``obj``."""

    try:
        blob = canonical_json(obj)
    except (TypeError, ValueError, OverflowError):
        return ("non_serializable",)
    fields = prohibited_field_matches(obj)
    values = prohibited_value_matches(blob)
    return tuple(sorted(set(fields) | set(values)))


def log_records_contain_prohibited(
    records: Iterable[logging.LogRecord],
    *,
    extra_needles: Iterable[str] = (),
) -> tuple[str, ...]:
    """Scan captured log records for prohibited markers and explicit canaries."""

    needles = tuple(extra_needles)
    hits: set[str] = set()
    for record in records:
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001
            rendered = str(record.msg)
        blob = f"{record.name} {rendered}"
        hits.update(prohibited_value_matches(blob))
        for needle in needles:
            if needle and needle in blob:
                hits.add(needle)
    return tuple(sorted(hits))


def drop_prohibited_queue_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only queue items that serialize without prohibited markers."""

    kept: list[dict[str, Any]] = []
    for item in items:
        if collection_surface_violations(item):
            continue
        kept.append(item)
    return kept


__all__ = [
    "PROHIBITED_VALUE_MARKERS",
    "canonical_json",
    "collection_surface_violations",
    "drop_prohibited_queue_items",
    "exceeds_serialization_budget",
    "iter_field_names",
    "log_records_contain_prohibited",
    "prohibited_field_matches",
    "prohibited_value_matches",
    "serialized_size_bytes",
]
