"""Factories for deterministic Repository Graph ``GraphRelationship`` values.

Extractors use this factory to build relationships. They do not assemble or
validate a full ``RepositoryGraph``; the assembler owns that responsibility.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.models import EvidenceReference, GraphRelationship, Provenance
from codestrata.domain.repository_graph.enums import RepositoryRelationshipType
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.domain.repository_graph.relationship_ids import RelationshipIdFactory


class RepositoryRelationshipFactory:
    """Create ``GraphRelationship`` instances with deterministic IDs."""

    def __init__(
        self,
        *,
        schema_version: str = REPOSITORY_GRAPH_SCHEMA_VERSION,
        id_factory: RelationshipIdFactory | None = None,
    ) -> None:
        self._schema_version = schema_version
        self._ids = id_factory or RelationshipIdFactory()

    @property
    def schema_version(self) -> str:
        return self._schema_version

    @property
    def ids(self) -> RelationshipIdFactory:
        return self._ids

    def create(
        self,
        *,
        relationship_type: RepositoryRelationshipType | str,
        source_node_id: NodeId | str,
        target_node_id: NodeId | str,
        properties: Mapping[str, Any] | None = None,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphRelationship:
        """Build one relationship without graph-level validation."""

        source = (
            source_node_id if isinstance(source_node_id, NodeId) else NodeId(str(source_node_id))
        )
        target = (
            target_node_id if isinstance(target_node_id, NodeId) else NodeId(str(target_node_id))
        )
        rel_type = (
            relationship_type.value
            if isinstance(relationship_type, RepositoryRelationshipType)
            else str(relationship_type)
        )
        relationship_id = self._ids.create(
            relationship_type=rel_type,
            source_node_id=source,
            target_node_id=target,
        )
        payload = dict(properties or {})
        payload.setdefault("schema_version", self._schema_version)
        return GraphRelationship(
            id=relationship_id,
            relationship_type=rel_type,
            source_node_id=source,
            target_node_id=target,
            properties=payload,
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )
