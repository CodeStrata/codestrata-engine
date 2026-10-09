"""Streaming query helpers over derived JSONL indexes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from codestrata.application.knowledge.errors import KnowledgeStoreError
from codestrata.application.knowledge.ports import KnowledgeStore
from codestrata.infrastructure.knowledge_store.io import iter_jsonl


def stream_derived_index(store: KnowledgeStore, name: str) -> Iterator[dict[str, Any]]:
    """Stream a rebuilt JSONL index. File stores only; others raise."""

    directory = getattr(store, "directory", None)
    if directory is None:
        raise KnowledgeStoreError("Knowledge store does not expose a file directory")
    root = directory
    index_dir = root / "indexes" / name
    for row in iter_jsonl(index_dir, root=root):
        if isinstance(row, dict):
            yield row
