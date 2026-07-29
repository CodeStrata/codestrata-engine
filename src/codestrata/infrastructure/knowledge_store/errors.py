"""Infrastructure-level knowledge store errors (translated at the boundary)."""

from __future__ import annotations


class SqliteKnowledgeStoreInternalError(Exception):
    """Internal SQLite adapter failure before translation to application errors."""
