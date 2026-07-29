"""Lightweight Assessment Graph aggregate over a validated ``GraphSnapshot``."""

from __future__ import annotations

from codestrata.domain.assessment_graph.schema import AssessmentGraphSchema
from codestrata.domain.graph.models import (
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
)


class AssessmentGraph:
    """Read-only Assessment Graph view that preserves a single ``GraphSnapshot``.

    Construction requires ``GraphType.ASSESSMENT`` and successful schema
    validation. The wrapper does not copy node or relationship data into
    parallel structures.
    """

    def __init__(self, snapshot: GraphSnapshot) -> None:
        self._snapshot = AssessmentGraphSchema.validate(snapshot)

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
