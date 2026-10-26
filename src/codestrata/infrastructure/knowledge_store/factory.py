"""Compose concrete knowledge-store implementations for application callers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.application.knowledge.queries.service import KnowledgeQueryService
from codestrata.config.settings import CodestrataSettings, KnowledgeSettings
from codestrata.infrastructure.knowledge_store.defaults import (
    DEFAULT_KNOWLEDGE_DIRECTORY,
    default_knowledge_directory,
)
from codestrata.infrastructure.knowledge_store.file.store import FileKnowledgeStore
from codestrata.infrastructure.knowledge_store.io import DEFAULT_MAX_JSON_BYTES


def knowledge_directory_from_settings(settings: CodestrataSettings | None) -> Path:
    """Resolve the knowledge directory from settings or the default path."""

    if settings is None:
        return default_knowledge_directory()
    knowledge: KnowledgeSettings = settings.knowledge
    resolved = Path(knowledge.directory)
    if resolved == DEFAULT_KNOWLEDGE_DIRECTORY:
        return default_knowledge_directory()
    return resolved


def max_json_bytes_from_settings(settings: CodestrataSettings | None) -> int:
    """Return configured knowledge JSON bound (default 16 MiB when settings omitted)."""

    if settings is None:
        return DEFAULT_MAX_JSON_BYTES
    return int(settings.knowledge.max_json_bytes)


def create_knowledge_store(
    directory: Path | None = None,
    *,
    settings: CodestrataSettings | None = None,
) -> FileKnowledgeStore:
    """Create an unopened file knowledge store for application use."""

    resolved = directory if directory is not None else knowledge_directory_from_settings(settings)
    return FileKnowledgeStore(resolved, max_json_bytes=max_json_bytes_from_settings(settings))


def create_knowledge_query_service(
    store: KnowledgeStore | None = None,
    *,
    directory: Path | None = None,
    settings: CodestrataSettings | None = None,
) -> KnowledgeQueryService:
    """Compose a :class:`KnowledgeQueryService` over an open knowledge store.

    When ``store`` is omitted, a file store is created from ``directory`` or
    settings and opened. Callers that inject a store retain ownership of its
    lifecycle.
    """

    if store is not None:
        return KnowledgeQueryService(store)

    concrete = create_knowledge_store(directory=directory, settings=settings)
    concrete.open()
    return KnowledgeQueryService(cast(KnowledgeStore, concrete))
