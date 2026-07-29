"""SQLite implementation of the engineering knowledge store."""

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

__all__ = [
    "SUPPORTED_SCHEMA_VERSION",
    "SqliteKnowledgeStore",
    "SqliteRepositoryRegistry",
    "open_knowledge_store",
    "repository_file_lock",
    "safe_lock_filename",
]
