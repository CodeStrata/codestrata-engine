"""Local knowledge-store health without HTTP or a database."""

from __future__ import annotations

from typing import Any

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.application.knowledge.ports import KnowledgeStore


def local_knowledge_health(store: KnowledgeStore) -> dict[str, Any]:
    """Return headless health/progress fields from a file store, or a safe stub."""

    health_fn = getattr(store, "health", None)
    if not callable(health_fn):
        try:
            _ = store.registry
            opened = True
        except KnowledgeStoreError:
            opened = False
        return {
            "backend": "unknown",
            "open": opened,
            "ok": opened,
            "http_service": False,
            "database": False,
        }
    health = health_fn()
    return {
        "backend": getattr(health, "backend", "file"),
        "schema_version": getattr(health, "schema_version", 0),
        "open": getattr(health, "open", False),
        "sqlite_present_untouched": getattr(health, "sqlite_present_untouched", False),
        "derived_index_present": getattr(health, "derived_index_present", False),
        "running_runs": getattr(health, "running_runs", 0),
        "completed_runs": getattr(health, "completed_runs", 0),
        "tmp_leftovers": getattr(health, "tmp_leftovers", 0),
        "ok": getattr(health, "ok", False),
        "issues": tuple(getattr(health, "issues", ())),
        "http_service": False,
        "database": False,
    }
