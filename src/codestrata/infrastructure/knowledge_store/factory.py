"""Compose concrete knowledge-store implementations for application callers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.application.knowledge.queries.service import KnowledgeQueryService
from codestrata.config.settings import CodestrataSettings, KnowledgeSettings
from codestrata.infrastructure.knowledge_store.defaults import DEFAULT_KNOWLEDGE_DIRECTORY
from codestrata.infrastructure.knowledge_store.sqlite.store import SqliteKnowledgeStore


def knowledge_directory_from_settings(settings: CodestrataSettings | None) -> Path:
    """Resolve the knowledge directory from settings or the default path."""

    if settings is None:
        return DEFAULT_KNOWLEDGE_DIRECTORY
    knowledge: KnowledgeSettings = settings.knowledge
    return Path(knowledge.directory)


def create_knowledge_store(
    directory: Path | None = None,
    *,
    settings: CodestrataSettings | None = None,
) -> SqliteKnowledgeStore:
    """Create an unopened SQLite knowledge store for application use."""

    resolved = directory if directory is not None else knowledge_directory_from_settings(settings)
    return SqliteKnowledgeStore(resolved)


def create_knowledge_query_service(
    store: KnowledgeStore | None = None,
    *,
    directory: Path | None = None,
    settings: CodestrataSettings | None = None,
) -> KnowledgeQueryService:
    """Compose a :class:`KnowledgeQueryService` over an open knowledge store.

    When ``store`` is omitted, a SQLite store is created from ``directory`` or
    settings and opened. Callers that inject a store retain ownership of its
    lifecycle.
    """

    if store is not None:
        return KnowledgeQueryService(store)

    concrete = create_knowledge_store(directory=directory, settings=settings)
    concrete.open()
    return KnowledgeQueryService(cast(KnowledgeStore, concrete))
