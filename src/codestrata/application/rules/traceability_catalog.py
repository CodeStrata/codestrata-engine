"""Read-only catalog crosswalk for Engineering Intelligence traceability.

Phase 8.9.4 — metadata only. Does not participate in rule evaluation.

Canonical human docs: ``knowledge/RULE_CATALOG.md`` and ``knowledge/TRACEABILITY.md``.
This module ships a packaged JSON mirror so the Engine can resolve Catalog /
Concept IDs without importing Knowledge documents.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Final, TypedDict


class CatalogEntry(TypedDict):
    catalog_id: str
    concept_id: str
    domain: str
    status: str


def _load_entries() -> tuple[dict[str, CatalogEntry], dict[str, CatalogEntry]]:
    payload = json.loads(
        files("codestrata.application.rules.data")
        .joinpath("traceability_catalog.json")
        .read_text(encoding="utf-8")
    )
    shared: dict[str, CatalogEntry] = {}
    legacy: dict[str, CatalogEntry] = {}
    for row in payload["rules"]:
        entry: CatalogEntry = {
            "catalog_id": row["catalog_id"],
            "concept_id": row["concept_id"],
            "domain": row["domain"],
            "status": row["status"],
        }
        runtime_id = row["runtime_id"]
        if row["status"] == "implemented-legacy":
            legacy[runtime_id] = entry
        elif row["status"] == "implemented":
            shared[runtime_id] = entry
    return shared, legacy


@lru_cache(maxsize=1)
def _maps() -> tuple[dict[str, CatalogEntry], dict[str, CatalogEntry]]:
    return _load_entries()


def _shared() -> dict[str, CatalogEntry]:
    return _maps()[0]


def _legacy() -> dict[str, CatalogEntry]:
    return _maps()[1]


# Public mapping views (lazy-filled on first access via helpers / properties).
RUNTIME_TO_CATALOG: Final[dict[str, CatalogEntry]] = {}
LEGACY_RUNTIME_TO_CATALOG: Final[dict[str, CatalogEntry]] = {}


def _ensure_maps_populated() -> None:
    if RUNTIME_TO_CATALOG:
        return
    shared, legacy = _maps()
    RUNTIME_TO_CATALOG.update(shared)
    LEGACY_RUNTIME_TO_CATALOG.update(legacy)


def catalog_id_for_runtime(runtime_rule_id: str) -> str | None:
    """Return Catalog Rule ID for a runtime rule id, if mapped."""

    _ensure_maps_populated()
    entry = RUNTIME_TO_CATALOG.get(runtime_rule_id) or LEGACY_RUNTIME_TO_CATALOG.get(
        runtime_rule_id
    )
    return None if entry is None else entry["catalog_id"]


def concept_id_for_runtime(runtime_rule_id: str) -> str | None:
    """Return Concept ID for a runtime rule id, if mapped."""

    _ensure_maps_populated()
    entry = RUNTIME_TO_CATALOG.get(runtime_rule_id) or LEGACY_RUNTIME_TO_CATALOG.get(
        runtime_rule_id
    )
    return None if entry is None else entry["concept_id"]


# Populate on import so ``RUNTIME_TO_CATALOG`` is usable as a mapping.
_ensure_maps_populated()
