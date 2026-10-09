"""SQLite implementation of the engineering knowledge store."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from codestrata.infrastructure.knowledge_store.sqlite.locking import (
        repository_file_lock,
        safe_lock_filename,
    )
    from codestrata.infrastructure.knowledge_store.sqlite.repository_registry import (
        SqliteRepositoryRegistry,
    )
    from codestrata.infrastructure.knowledge_store.sqlite.store import (
        SUPPORTED_SCHEMA_VERSION,
        SqliteKnowledgeStore,
        open_knowledge_store,
    )


def __getattr__(name: str) -> Any:
    """Keep the legacy adapter lazy so file-store imports do not load sqlite3."""

    if name in {"repository_file_lock", "safe_lock_filename"}:
        from codestrata.infrastructure.knowledge_store.sqlite import locking

        return getattr(locking, name)
    if name == "SqliteRepositoryRegistry":
        from codestrata.infrastructure.knowledge_store.sqlite.repository_registry import (
            SqliteRepositoryRegistry,
        )

        return SqliteRepositoryRegistry
    if name in {"SUPPORTED_SCHEMA_VERSION", "SqliteKnowledgeStore", "open_knowledge_store"}:
        from codestrata.infrastructure.knowledge_store.sqlite import store

        return getattr(store, name)
    raise AttributeError(name)

__all__ = [
    "SUPPORTED_SCHEMA_VERSION",
    "SqliteKnowledgeStore",
    "SqliteRepositoryRegistry",
    "open_knowledge_store",
    "repository_file_lock",
    "safe_lock_filename",
]
