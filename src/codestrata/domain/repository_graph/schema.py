"""Repository Graph schema validation over ``GraphSnapshot``.

This validator is intentionally separate from generic ``GraphSnapshot``
integrity checks (unique IDs, endpoint existence). It enforces Repository
Graph vocabulary and allowed relationship endpoint combinations only; it does
not infer or repair invalid graphs.
"""

from __future__ import annotations

from codestrata.domain.graph.enums import GraphType
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot
from codestrata.domain.repository_graph.enums import (
    RepositoryNodeType,
    RepositoryRelationshipType,
)

_ALLOWED_ENDPOINTS: dict[
    RepositoryRelationshipType, frozenset[tuple[RepositoryNodeType, RepositoryNodeType]]
] = {
    RepositoryRelationshipType.CONTAINS: frozenset(
        {
            (RepositoryNodeType.REPOSITORY, RepositoryNodeType.MODULE),
            (RepositoryNodeType.REPOSITORY, RepositoryNodeType.FILE),
            (RepositoryNodeType.MODULE, RepositoryNodeType.MODULE),
            (RepositoryNodeType.MODULE, RepositoryNodeType.FILE),
        }
    ),
    RepositoryRelationshipType.DECLARES: frozenset(
        {
            (RepositoryNodeType.FILE, RepositoryNodeType.NAMESPACE),
            (RepositoryNodeType.FILE, RepositoryNodeType.TYPE),
            (RepositoryNodeType.FILE, RepositoryNodeType.CALLABLE),
            (RepositoryNodeType.NAMESPACE, RepositoryNodeType.TYPE),
            (RepositoryNodeType.NAMESPACE, RepositoryNodeType.CALLABLE),
            (RepositoryNodeType.TYPE, RepositoryNodeType.CALLABLE),
        }
    ),
    RepositoryRelationshipType.DEPENDS_ON: frozenset(
        {
            (RepositoryNodeType.REPOSITORY, RepositoryNodeType.DEPENDENCY),
            (RepositoryNodeType.MODULE, RepositoryNodeType.DEPENDENCY),
            (RepositoryNodeType.TYPE, RepositoryNodeType.DEPENDENCY),
            (RepositoryNodeType.CALLABLE, RepositoryNodeType.DEPENDENCY),
            (RepositoryNodeType.DEPENDENCY, RepositoryNodeType.DEPENDENCY),
        }
    ),
    RepositoryRelationshipType.CALLS: frozenset(
        {
            (RepositoryNodeType.CALLABLE, RepositoryNodeType.CALLABLE),
        }
    ),
}


class RepositoryGraphSchemaError(ValueError):
    """Raised when a snapshot violates Repository Graph schema rules."""


class RepositoryGraphSchema:
    """Validate Repository Graph vocabulary and relationship endpoint rules."""

    @classmethod
    def validate(cls, snapshot: GraphSnapshot) -> GraphSnapshot:
        """Validate ``snapshot`` and return it unchanged on success."""

        if snapshot.metadata.graph_type is not GraphType.REPOSITORY:
            raise RepositoryGraphSchemaError(
                f"graph_type must be '{GraphType.REPOSITORY}', got '{snapshot.metadata.graph_type}'"
            )

        nodes_by_id = {node.id.root: node for node in snapshot.nodes}
        for node in snapshot.nodes:
            cls._require_known_node_type(node)

        for relationship in snapshot.relationships:
            cls._validate_relationship(relationship, nodes_by_id)

        return snapshot

    @classmethod
    def _require_known_node_type(cls, node: GraphNode) -> RepositoryNodeType:
        try:
            return RepositoryNodeType(node.node_type)
        except ValueError as exc:
            raise RepositoryGraphSchemaError(
                f"unknown Repository Graph node_type '{node.node_type}'"
            ) from exc

    @classmethod
    def _require_known_relationship_type(
        cls, relationship: GraphRelationship
    ) -> RepositoryRelationshipType:
        try:
            return RepositoryRelationshipType(relationship.relationship_type)
        except ValueError as exc:
            raise RepositoryGraphSchemaError(
                f"unknown Repository Graph relationship_type '{relationship.relationship_type}'"
            ) from exc

    @classmethod
    def _validate_relationship(
        cls,
        relationship: GraphRelationship,
        nodes_by_id: dict[str, GraphNode],
    ) -> None:
        rel_type = cls._require_known_relationship_type(relationship)
        source = nodes_by_id[relationship.source_node_id.root]
        target = nodes_by_id[relationship.target_node_id.root]
        source_type = cls._require_known_node_type(source)
        target_type = cls._require_known_node_type(target)
        allowed = _ALLOWED_ENDPOINTS[rel_type]
        if (source_type, target_type) not in allowed:
            raise RepositoryGraphSchemaError(
                f"invalid {rel_type} endpoints: {source_type} -> {target_type}"
            )
