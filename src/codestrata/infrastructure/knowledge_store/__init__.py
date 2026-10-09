"""Infrastructure adapters for durable engineering knowledge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codestrata.infrastructure.knowledge_store.defaults import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_KNOWLEDGE_DIRECTORY,
)
from codestrata.infrastructure.knowledge_store.factory import (
    create_knowledge_query_service,
    create_knowledge_store,
    knowledge_directory_from_settings,
)
from codestrata.infrastructure.knowledge_store.file import (
    FileKnowledgeHealth,
    FileKnowledgeStore,
    open_file_knowledge_store,
)

if TYPE_CHECKING:
    from codestrata.infrastructure.knowledge_store.sqlite import (
        SqliteKnowledgeStore,
        SqliteRepositoryRegistry,
        open_knowledge_store,
    )


def __getattr__(name: str) -> Any:
    """Compatibility projection for Platform/tests. Community factory does not use it."""

    if name in {"SqliteKnowledgeStore", "SqliteRepositoryRegistry", "open_knowledge_store"}:
        from codestrata.infrastructure.knowledge_store import sqlite

        return getattr(sqlite, name)
    raise AttributeError(name)


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_KNOWLEDGE_DIRECTORY",
    "FileKnowledgeHealth",
    "FileKnowledgeStore",
    "SqliteKnowledgeStore",
    "SqliteRepositoryRegistry",
    "create_knowledge_query_service",
    "create_knowledge_store",
    "knowledge_directory_from_settings",
    "open_file_knowledge_store",
    "open_knowledge_store",
]
