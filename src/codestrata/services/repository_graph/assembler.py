"""Assemble ``RepositoryGraph`` from multiple extractor contributions.

The assembler is the only component that merges facts, reconciles duplicates,
builds ``GraphSnapshot``, and invokes ``RepositoryGraphSchema`` validation
(via ``RepositoryGraph`` construction).
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.graph.models import (
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
)
from codestrata.domain.repository_graph.models import RepositoryGraph
from codestrata.services.repository_graph.results import RepositoryExtractionResult


class RepositoryGraphAssemblyError(ValueError):
    """Raised when extractor contributions cannot be reconciled."""


class RepositoryGraphAssembler:
    """Merge extractor results into one validated ``RepositoryGraph``."""

    def assemble(
        self,
        results: Sequence[RepositoryExtractionResult],
        *,
        metadata: GraphMetadata,
    ) -> RepositoryGraph:
        """Merge results, reconcile duplicates, validate, and return the graph."""

        nodes = self._merge_nodes(results)
        relationships = self._merge_relationships(results)
        snapshot = GraphSnapshot(
            metadata=metadata,
            nodes=nodes,
            relationships=relationships,
        )
        return RepositoryGraph(snapshot)

    def _merge_nodes(
        self,
        results: Sequence[RepositoryExtractionResult],
    ) -> tuple[GraphNode, ...]:
        merged: dict[str, GraphNode] = {}
        for result in results:
            for node in result.nodes:
                key = node.id.root
                existing = merged.get(key)
                if existing is None:
                    merged[key] = node
                    continue
                if existing != node:
                    raise RepositoryGraphAssemblyError(
                        f"conflicting duplicate node id '{key}' from extractor "
                        f"'{result.extractor_id}'"
                    )
        return tuple(merged[key] for key in sorted(merged))

    def _merge_relationships(
        self,
        results: Sequence[RepositoryExtractionResult],
    ) -> tuple[GraphRelationship, ...]:
        merged: dict[str, GraphRelationship] = {}
        for result in results:
            for relationship in result.relationships:
                key = relationship.id
                existing = merged.get(key)
                if existing is None:
                    merged[key] = relationship
                    continue
                if existing != relationship:
                    raise RepositoryGraphAssemblyError(
                        f"conflicting duplicate relationship id '{key}' from extractor "
                        f"'{result.extractor_id}'"
                    )
        return tuple(merged[key] for key in sorted(merged))
