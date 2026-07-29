"""Immutable extraction context shared by Repository Graph extractors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from codestrata.domain.repository.changes import RepositoryGraphChangeSet
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.services.inventory.content_reader import RepositoryContentReader
from codestrata.services.repository_graph.enums import RepositoryExtractionScope


def _empty_metadata() -> Mapping[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class RepositoryExtractionContext:
    """Inputs available to extractors during one extraction pass.

    Extractors read inventory and file bytes through this context. They never
    scan the filesystem themselves and never assemble ``RepositoryGraph``.
    """

    manifest: RepositoryManifest
    content_reader: RepositoryContentReader
    scope: RepositoryExtractionScope = RepositoryExtractionScope.FULL
    change_set: RepositoryGraphChangeSet | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        if self.scope is RepositoryExtractionScope.INCREMENTAL and self.change_set is None:
            raise ValueError("incremental extraction requires a change_set")
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
