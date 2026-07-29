"""Assessment Graph schema validation over ``GraphSnapshot``."""

from __future__ import annotations

from codestrata.domain.assessment_graph.enums import (
    AssessmentNodeType,
    AssessmentRelationshipType,
)
from codestrata.domain.graph.enums import GraphType
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot

_ALLOWED_ENDPOINTS: dict[
    AssessmentRelationshipType,
    frozenset[tuple[AssessmentNodeType, AssessmentNodeType]],
] = {
    AssessmentRelationshipType.BINDS_TO_KNOWLEDGE: frozenset(
        {
            (
                AssessmentNodeType.REPOSITORY_ENTITY_REFERENCE,
                AssessmentNodeType.KNOWLEDGE_CONCEPT_REFERENCE,
            ),
        }
    ),
}


class AssessmentGraphSchemaError(ValueError):
    """Raised when a snapshot violates Assessment Graph schema rules."""


class AssessmentGraphSchema:
    """Validate Assessment Graph vocabulary and relationship endpoints."""

    @classmethod
    def validate(cls, snapshot: GraphSnapshot) -> GraphSnapshot:
        if snapshot.metadata.graph_type is not GraphType.ASSESSMENT:
            raise AssessmentGraphSchemaError(
                f"graph_type must be '{GraphType.ASSESSMENT}', got '{snapshot.metadata.graph_type}'"
            )

        nodes_by_id = {node.id.root: node for node in snapshot.nodes}
        for node in snapshot.nodes:
            cls._require_known_node_type(node)

        for relationship in snapshot.relationships:
            cls._validate_relationship(relationship, nodes_by_id)

        return snapshot

    @classmethod
    def _require_known_node_type(cls, node: GraphNode) -> AssessmentNodeType:
        try:
            return AssessmentNodeType(node.node_type)
        except ValueError as exc:
            raise AssessmentGraphSchemaError(
                f"unknown Assessment Graph node_type '{node.node_type}'"
            ) from exc

    @classmethod
    def _require_known_relationship_type(
        cls,
        relationship: GraphRelationship,
    ) -> AssessmentRelationshipType:
        try:
            return AssessmentRelationshipType(relationship.relationship_type)
        except ValueError as exc:
            raise AssessmentGraphSchemaError(
                f"unknown Assessment Graph relationship_type '{relationship.relationship_type}'"
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
            raise AssessmentGraphSchemaError(
                f"invalid {rel_type} endpoints: {source_type} -> {target_type}"
            )
