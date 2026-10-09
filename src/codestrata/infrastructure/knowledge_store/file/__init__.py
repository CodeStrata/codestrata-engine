"""File knowledge-store adapter package."""

from codestrata.infrastructure.knowledge_store.file.health import FileKnowledgeHealth
from codestrata.infrastructure.knowledge_store.file.store import (
    FileKnowledgeStore,
    open_file_knowledge_store,
)

__all__ = [
    "FileKnowledgeHealth",
    "FileKnowledgeStore",
    "open_file_knowledge_store",
]
