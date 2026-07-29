"""Engineering Knowledge Graph schema validation over ``GraphSnapshot``.

Validates vocabulary and allowed endpoint combinations only. It does not infer
or repair invalid graphs and is separate from generic ``GraphSnapshot`` integrity.
"""

from __future__ import annotations

from codestrata.domain.engineering_knowledge.enums import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
)
from codestrata.domain.graph.enums import GraphType
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot

_N = EngineeringKnowledgeNodeType
_R = EngineeringKnowledgeRelationshipType

_ALLOWED_ENDPOINTS: dict[
    EngineeringKnowledgeRelationshipType,
    frozenset[tuple[EngineeringKnowledgeNodeType, EngineeringKnowledgeNodeType]],
] = {
    _R.IS_A: frozenset(
        {
            (_N.TECHNOLOGY, _N.TECHNOLOGY),
            (_N.FRAMEWORK, _N.TECHNOLOGY),
            (_N.LIBRARY, _N.TECHNOLOGY),
            (_N.LANGUAGE, _N.TECHNOLOGY),
            (_N.RUNTIME, _N.TECHNOLOGY),
            (_N.BUILD_TOOL, _N.TECHNOLOGY),
            (_N.PLATFORM_CAPABILITY, _N.PLATFORM),
            (_N.DESIGN_PATTERN, _N.DESIGN_PATTERN),
            (_N.ANTI_PATTERN, _N.ANTI_PATTERN),
            (_N.MODERNIZATION_STRATEGY, _N.MODERNIZATION_STRATEGY),
            (_N.RISK_TYPE, _N.RISK_TYPE),
            (_N.ENGINEERING_PRACTICE, _N.ENGINEERING_PRACTICE),
        }
    ),
    _R.PART_OF: frozenset(
        {
            (_N.FRAMEWORK, _N.PLATFORM),
            (_N.LIBRARY, _N.FRAMEWORK),
            (_N.PLATFORM_CAPABILITY, _N.PLATFORM),
            (_N.RULE, _N.ENGINEERING_PRACTICE),
            (_N.CONSTRAINT, _N.PLATFORM),
            (_N.CONSTRAINT, _N.FRAMEWORK),
            (_N.CONSTRAINT, _N.TECHNOLOGY),
        }
    ),
    _R.DEPENDS_ON: frozenset(
        {
            (_N.FRAMEWORK, _N.LANGUAGE),
            (_N.FRAMEWORK, _N.RUNTIME),
            (_N.FRAMEWORK, _N.LIBRARY),
            (_N.LIBRARY, _N.LANGUAGE),
            (_N.BUILD_TOOL, _N.LANGUAGE),
            (_N.PLATFORM_CAPABILITY, _N.PLATFORM_CAPABILITY),
            (_N.MODERNIZATION_STRATEGY, _N.ENGINEERING_PRACTICE),
        }
    ),
    _R.COMPATIBLE_WITH: frozenset(
        {
            (_N.TECHNOLOGY, _N.TECHNOLOGY),
            (_N.FRAMEWORK, _N.FRAMEWORK),
            (_N.FRAMEWORK, _N.LANGUAGE),
            (_N.FRAMEWORK, _N.RUNTIME),
            (_N.LIBRARY, _N.FRAMEWORK),
            (_N.PLATFORM, _N.TECHNOLOGY),
            (_N.PLATFORM_CAPABILITY, _N.TECHNOLOGY),
        }
    ),
    _R.CONFLICTS_WITH: frozenset(
        {
            (_N.TECHNOLOGY, _N.TECHNOLOGY),
            (_N.FRAMEWORK, _N.FRAMEWORK),
            (_N.DESIGN_PATTERN, _N.ANTI_PATTERN),
            (_N.ENGINEERING_PRACTICE, _N.ANTI_PATTERN),
            (_N.MODERNIZATION_STRATEGY, _N.CONSTRAINT),
        }
    ),
    _R.SUPERSEDES: frozenset(
        {
            (_N.TECHNOLOGY, _N.TECHNOLOGY),
            (_N.FRAMEWORK, _N.FRAMEWORK),
            (_N.DESIGN_PATTERN, _N.DESIGN_PATTERN),
            (_N.ENGINEERING_PRACTICE, _N.ENGINEERING_PRACTICE),
            (_N.MODERNIZATION_STRATEGY, _N.MODERNIZATION_STRATEGY),
            (_N.RULE, _N.RULE),
        }
    ),
    _R.SUPPORTS: frozenset(
        {
            (_N.FRAMEWORK, _N.ARCHITECTURE_STYLE),
            (_N.PLATFORM, _N.ARCHITECTURE_STYLE),
            (_N.PLATFORM_CAPABILITY, _N.QUALITY_ATTRIBUTE),
            (_N.DESIGN_PATTERN, _N.QUALITY_ATTRIBUTE),
            (_N.ENGINEERING_PRACTICE, _N.QUALITY_ATTRIBUTE),
            (_N.MODERNIZATION_STRATEGY, _N.QUALITY_ATTRIBUTE),
        }
    ),
    _R.IMPACTS: frozenset(
        {
            (_N.TECHNOLOGY, _N.QUALITY_ATTRIBUTE),
            (_N.FRAMEWORK, _N.QUALITY_ATTRIBUTE),
            (_N.ARCHITECTURE_STYLE, _N.QUALITY_ATTRIBUTE),
            (_N.DESIGN_PATTERN, _N.QUALITY_ATTRIBUTE),
            (_N.ANTI_PATTERN, _N.QUALITY_ATTRIBUTE),
            (_N.ENGINEERING_PRACTICE, _N.QUALITY_ATTRIBUTE),
            (_N.CONSTRAINT, _N.QUALITY_ATTRIBUTE),
        }
    ),
    _R.MITIGATES: frozenset(
        {
            (_N.DESIGN_PATTERN, _N.RISK_TYPE),
            (_N.ENGINEERING_PRACTICE, _N.RISK_TYPE),
            (_N.MODERNIZATION_STRATEGY, _N.RISK_TYPE),
            (_N.RULE, _N.RISK_TYPE),
            (_N.PLATFORM_CAPABILITY, _N.RISK_TYPE),
        }
    ),
    _R.INCREASES_RISK: frozenset(
        {
            (_N.ANTI_PATTERN, _N.RISK_TYPE),
            (_N.CONSTRAINT, _N.RISK_TYPE),
            (_N.TECHNOLOGY, _N.RISK_TYPE),
            (_N.FRAMEWORK, _N.RISK_TYPE),
            (_N.ARCHITECTURE_STYLE, _N.RISK_TYPE),
        }
    ),
    _R.ADDRESSES: frozenset(
        {
            (_N.MODERNIZATION_STRATEGY, _N.ANTI_PATTERN),
            (_N.MODERNIZATION_STRATEGY, _N.RISK_TYPE),
            (_N.ENGINEERING_PRACTICE, _N.ANTI_PATTERN),
            (_N.ENGINEERING_PRACTICE, _N.RISK_TYPE),
            (_N.RULE, _N.ANTI_PATTERN),
            (_N.RULE, _N.RISK_TYPE),
            (_N.PLATFORM_CAPABILITY, _N.CONSTRAINT),
        }
    ),
    _R.RECOMMENDS: frozenset(
        {
            (_N.RULE, _N.MODERNIZATION_STRATEGY),
            (_N.RULE, _N.ENGINEERING_PRACTICE),
            (_N.RULE, _N.DESIGN_PATTERN),
            (_N.RULE, _N.PLATFORM_CAPABILITY),
        }
    ),
    _R.REQUIRES: frozenset(
        {
            (_N.FRAMEWORK, _N.RUNTIME),
            (_N.FRAMEWORK, _N.LANGUAGE),
            (_N.MODERNIZATION_STRATEGY, _N.ENGINEERING_PRACTICE),
            (_N.MODERNIZATION_STRATEGY, _N.PLATFORM_CAPABILITY),
            (_N.ENGINEERING_PRACTICE, _N.PLATFORM_CAPABILITY),
            (_N.RULE, _N.CONSTRAINT),
        }
    ),
    _R.GOVERNED_BY: frozenset(
        {
            (_N.TECHNOLOGY, _N.RULE),
            (_N.FRAMEWORK, _N.RULE),
            (_N.PLATFORM, _N.RULE),
            (_N.PLATFORM_CAPABILITY, _N.RULE),
            (_N.ARCHITECTURE_STYLE, _N.RULE),
            (_N.ENGINEERING_PRACTICE, _N.RULE),
            (_N.MODERNIZATION_STRATEGY, _N.RULE),
        }
    ),
    _R.RELATED_TO: frozenset({(source, target) for source in _N for target in _N}),
}


class EngineeringKnowledgeGraphSchemaError(ValueError):
    """Raised when a snapshot violates Engineering Knowledge Graph schema rules."""


class EngineeringKnowledgeGraphSchema:
    """Validate Engineering Knowledge vocabulary and relationship endpoints."""

    @classmethod
    def validate(cls, snapshot: GraphSnapshot) -> GraphSnapshot:
        if snapshot.metadata.graph_type is not GraphType.ENGINEERING_KNOWLEDGE:
            raise EngineeringKnowledgeGraphSchemaError(
                "graph_type must be "
                f"'{GraphType.ENGINEERING_KNOWLEDGE}', "
                f"got '{snapshot.metadata.graph_type}'"
            )

        nodes_by_id = {node.id.root: node for node in snapshot.nodes}
        for node in snapshot.nodes:
            cls._require_known_node_type(node)

        for relationship in snapshot.relationships:
            cls._validate_relationship(relationship, nodes_by_id)

        return snapshot

    @classmethod
    def _require_known_node_type(cls, node: GraphNode) -> EngineeringKnowledgeNodeType:
        try:
            return EngineeringKnowledgeNodeType(node.node_type)
        except ValueError as exc:
            raise EngineeringKnowledgeGraphSchemaError(
                f"unknown Engineering Knowledge node_type '{node.node_type}'"
            ) from exc

    @classmethod
    def _require_known_relationship_type(
        cls, relationship: GraphRelationship
    ) -> EngineeringKnowledgeRelationshipType:
        try:
            return EngineeringKnowledgeRelationshipType(relationship.relationship_type)
        except ValueError as exc:
            raise EngineeringKnowledgeGraphSchemaError(
                "unknown Engineering Knowledge relationship_type "
                f"'{relationship.relationship_type}'"
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
            raise EngineeringKnowledgeGraphSchemaError(
                f"invalid {rel_type} endpoints: {source_type} -> {target_type}"
            )
