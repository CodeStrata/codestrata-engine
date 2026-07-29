"""Infrastructure adapters for durable engineering knowledge."""

from codestrata.infrastructure.knowledge_store.defaults import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_KNOWLEDGE_DIRECTORY,
)
from codestrata.infrastructure.knowledge_store.factory import (
    create_knowledge_query_service,
    create_knowledge_store,
    knowledge_directory_from_settings,
)
from codestrata.infrastructure.knowledge_store.sqlite import (
    SqliteKnowledgeStore,
    SqliteRepositoryRegistry,
    open_knowledge_store,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_KNOWLEDGE_DIRECTORY",
    "SqliteKnowledgeStore",
    "SqliteRepositoryRegistry",
    "create_knowledge_query_service",
    "create_knowledge_store",
    "knowledge_directory_from_settings",
    "open_knowledge_store",
]
