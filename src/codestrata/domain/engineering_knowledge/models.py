"""Lightweight Engineering Knowledge Graph aggregate over ``GraphSnapshot``."""

from __future__ import annotations

from codestrata.domain.engineering_knowledge.schema import EngineeringKnowledgeGraphSchema
from codestrata.domain.graph.models import (
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
)


class EngineeringKnowledgeGraph:
    """Read-only Engineering Knowledge Graph view over one ``GraphSnapshot``.

    Construction requires ``GraphType.ENGINEERING_KNOWLEDGE`` and successful
    schema validation. The wrapper does not duplicate node or relationship data.
    """

    def __init__(self, snapshot: GraphSnapshot) -> None:
        self._snapshot = EngineeringKnowledgeGraphSchema.validate(snapshot)

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
