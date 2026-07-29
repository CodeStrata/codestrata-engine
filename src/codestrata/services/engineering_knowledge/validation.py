"""Catalog-level duplicate and reference validation before graph construction."""

from __future__ import annotations

from codestrata.domain.engineering_knowledge.ids import (
    EngineeringKnowledgeNodeIdFactory,
    EngineeringKnowledgeRelationshipIdFactory,
)
from codestrata.services.engineering_knowledge.catalog_models import (
    EngineeringKnowledgeCatalogDocument,
    EngineeringKnowledgeCatalogReference,
)
from codestrata.services.engineering_knowledge.exceptions import (
    EngineeringKnowledgeCatalogValidationError,
)


def validate_catalog_document(document: EngineeringKnowledgeCatalogDocument) -> None:
    """Reject duplicate entries and relationships that cannot resolve."""

    node_ids = EngineeringKnowledgeNodeIdFactory()
    relationship_ids = EngineeringKnowledgeRelationshipIdFactory()

    seen_refs: set[str] = set()
    seen_node_ids: set[str] = set()
    known: dict[str, EngineeringKnowledgeCatalogReference] = {}

    for node in document.nodes:
        ref = node.reference()
        token = ref.as_token()
        if token in seen_refs:
            raise EngineeringKnowledgeCatalogValidationError(
                f"duplicate catalog node reference '{token}'"
            )
        seen_refs.add(token)

        node_id = str(node_ids.create(node_type=node.node_type, canonical_key=node.canonical_key))
        if node_id in seen_node_ids:
            raise EngineeringKnowledgeCatalogValidationError(
                f"duplicate generated node ID '{node_id}'"
            )
        seen_node_ids.add(node_id)
        known[token] = ref

    seen_relationship_ids: set[str] = set()
    for relationship in document.relationships:
        source_token = relationship.source.as_token()
        target_token = relationship.target.as_token()
        if source_token not in known:
            raise EngineeringKnowledgeCatalogValidationError(
                f"relationship source '{source_token}' is not present in catalog nodes"
            )
        if target_token not in known:
            raise EngineeringKnowledgeCatalogValidationError(
                f"relationship target '{target_token}' is not present in catalog nodes"
            )

        source_id = node_ids.create(
            node_type=relationship.source.node_type,
            canonical_key=relationship.source.canonical_key,
        )
        target_id = node_ids.create(
            node_type=relationship.target.node_type,
            canonical_key=relationship.target.canonical_key,
        )
        rel_id = relationship_ids.create(
            relationship_type=relationship.relationship_type,
            source_node_id=source_id,
            target_node_id=target_id,
        )
        if rel_id in seen_relationship_ids:
            raise EngineeringKnowledgeCatalogValidationError(
                f"duplicate catalog relationship '{rel_id}'"
            )
        seen_relationship_ids.add(rel_id)
