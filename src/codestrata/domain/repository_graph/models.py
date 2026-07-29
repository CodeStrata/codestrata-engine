"""Lightweight Repository Graph aggregate over a validated ``GraphSnapshot``."""

from __future__ import annotations

from codestrata.domain.graph.models import (
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
)
from codestrata.domain.repository_graph.schema import RepositoryGraphSchema


class RepositoryGraph:
    """Read-only Repository Graph view that preserves a single ``GraphSnapshot``.

    Construction requires ``GraphType.REPOSITORY`` and successful
    :class:`RepositoryGraphSchema` validation. The wrapper does not copy node
    or relationship data into parallel structures.
    """

    def __init__(self, snapshot: GraphSnapshot) -> None:
        self._snapshot = RepositoryGraphSchema.validate(snapshot)

    @property
    def snapshot(self) -> GraphSnapshot:
        return self._snapshot

    @property
    def metadata(self) -> GraphMetadata:
        return self._snapshot.metadata

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        return self._snapshot.nodes

    @property
    def relationships(self) -> tuple[GraphRelationship, ...]:
        return self._snapshot.relationships
