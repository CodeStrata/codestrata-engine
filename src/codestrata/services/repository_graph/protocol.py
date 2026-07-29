"""Protocol for Repository Graph extractors."""

from __future__ import annotations

from typing import Protocol

from codestrata.services.repository_graph.context import RepositoryExtractionContext
from codestrata.services.repository_graph.results import RepositoryExtractionResult


class RepositoryGraphExtractor(Protocol):
    """Contribute graph facts without assembling or validating the full graph.

    Extractors accept a ``RepositoryExtractionContext`` and return a
    ``RepositoryExtractionResult``. They must not:

    - scan the filesystem (use ``context.content_reader``)
    - construct ``RepositoryGraph`` / ``GraphSnapshot``
    - perform Repository Graph schema validation
    """

    @property
    def extractor_id(self) -> str:
        """Stable identifier for this extractor implementation."""

    def extract(self, context: RepositoryExtractionContext) -> RepositoryExtractionResult:
        """Extract nodes and relationships for the given context."""
