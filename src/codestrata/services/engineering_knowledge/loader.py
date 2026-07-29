"""Load curated Engineering Knowledge Catalog documents into validated graphs.

The loader owns safe parsing and catalog-level validation. Domain factories and
``EngineeringKnowledgeGraph`` own node construction and schema semantics.
Catalog loading is deterministic and never evaluates rule expressions, lifecycle
dates, or repository-specific behavior.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from codestrata.domain.engineering_knowledge import (
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeGraph,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeRelationshipFactory,
    build_engineering_knowledge_metadata,
)
from codestrata.domain.engineering_knowledge.ids import EngineeringKnowledgeNodeIdFactory
from codestrata.domain.graph.enums import ProvenanceSource
from codestrata.domain.graph.models import (
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
    Provenance,
)
from codestrata.services.engineering_knowledge.catalog_models import (
    EngineeringKnowledgeCatalogDocument,
    EngineeringKnowledgeCatalogNode,
    EngineeringKnowledgeCatalogRelationship,
)
from codestrata.services.engineering_knowledge.exceptions import (
    EngineeringKnowledgeCatalogParseError,
    EngineeringKnowledgeCatalogValidationError,
)
from codestrata.services.engineering_knowledge.property_dispatch import validate_node_properties
from codestrata.services.engineering_knowledge.validation import validate_catalog_document

_CATALOG_LOADER_ID = "engineering-knowledge-catalog-loader"


class EngineeringKnowledgeCatalogLoader:
    """Parse and validate a curated catalog into an EngineeringKnowledgeGraph."""

    def __init__(
        self,
        *,
        node_factory: EngineeringKnowledgeNodeFactory | None = None,
        relationship_factory: EngineeringKnowledgeRelationshipFactory | None = None,
    ) -> None:
        self._nodes = node_factory or EngineeringKnowledgeNodeFactory()
        self._relationships = relationship_factory or EngineeringKnowledgeRelationshipFactory()

    def load_path(self, path: Path) -> EngineeringKnowledgeGraph:
        """Load a catalog file from a supplied path (thin filesystem adapter)."""

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise EngineeringKnowledgeCatalogParseError(
                f"unable to read catalog path '{path}': {exc}"
            ) from exc
        return self.load_text(text)

    def load_bytes(self, data: bytes) -> EngineeringKnowledgeGraph:
        """Load catalog bytes as UTF-8 text."""

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EngineeringKnowledgeCatalogParseError(
                f"catalog bytes are not valid UTF-8: {exc}"
            ) from exc
        return self.load_text(text)

    def load_text(self, text: str) -> EngineeringKnowledgeGraph:
        """Safely parse catalog text and construct a validated knowledge graph."""

        document = self.parse_document(text)
        return self.load_document(document)

    def parse_document(self, text: str) -> EngineeringKnowledgeCatalogDocument:
        """Parse and validate catalog text into an immutable document model."""

        raw = self._safe_load_mapping(text)
        return self._document_from_mapping(raw)

    def load_document(
        self,
        document: EngineeringKnowledgeCatalogDocument,
    ) -> EngineeringKnowledgeGraph:
        """Construct a validated EngineeringKnowledgeGraph from a typed document."""

        validate_catalog_document(document)
        default_provenance = self._default_provenance(document.metadata)
        nodes = self._build_nodes(document.nodes, default_provenance)
        relationships = self._build_relationships(
            document.relationships,
            default_provenance,
        )
        nodes_sorted = tuple(sorted(nodes, key=lambda node: node.id.root))
        relationships_sorted = tuple(
            sorted(relationships, key=lambda item: item.id),
        )
        metadata = build_engineering_knowledge_metadata(document.metadata)
        snapshot = GraphSnapshot(
            metadata=metadata,
            nodes=nodes_sorted,
            relationships=relationships_sorted,
        )
        try:
            return EngineeringKnowledgeGraph(snapshot)
        except Exception as exc:
            raise EngineeringKnowledgeCatalogValidationError(
                f"engineering knowledge graph schema validation failed: {exc}"
            ) from exc

    def _safe_load_mapping(self, text: str) -> Mapping[str, Any]:
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise EngineeringKnowledgeCatalogParseError(
                f"catalog YAML/JSON parse failed: {exc}"
            ) from exc
        if not isinstance(loaded, Mapping):
            raise EngineeringKnowledgeCatalogParseError(
                "catalog document must be a top-level mapping"
            )
        return loaded

    def _document_from_mapping(
        self,
        raw: Mapping[str, Any],
    ) -> EngineeringKnowledgeCatalogDocument:
        try:
            metadata = EngineeringKnowledgeCatalogMetadata.model_validate(
                {
                    "catalog_id": raw.get("catalog_id"),
                    "catalog_version": raw.get("catalog_version"),
                    "name": raw.get("name"),
                    "description": raw.get("description"),
                    "published_at": raw.get("published_at"),
                    "source": raw.get("source"),
                }
            )
            nodes_raw = raw.get("nodes", ())
            relationships_raw = raw.get("relationships", ())
            if not isinstance(nodes_raw, list | tuple):
                raise EngineeringKnowledgeCatalogValidationError("catalog 'nodes' must be a list")
            if not isinstance(relationships_raw, list | tuple):
                raise EngineeringKnowledgeCatalogValidationError(
                    "catalog 'relationships' must be a list"
                )
            nodes = tuple(
                EngineeringKnowledgeCatalogNode.model_validate(item) for item in nodes_raw
            )
            relationships = tuple(
                EngineeringKnowledgeCatalogRelationship.model_validate(item)
                for item in relationships_raw
            )
            return EngineeringKnowledgeCatalogDocument(
                metadata=metadata,
                schema_version=str(raw.get("schema_version", "")),
                nodes=nodes,
                relationships=relationships,
            )
        except EngineeringKnowledgeCatalogValidationError:
            raise
        except (ValidationError, ValueError, TypeError) as exc:
            raise EngineeringKnowledgeCatalogValidationError(
                f"invalid catalog document: {exc}"
            ) from exc

    def _default_provenance(
        self,
        metadata: EngineeringKnowledgeCatalogMetadata,
    ) -> Provenance:
        return Provenance(
            source_type=ProvenanceSource.ENGINEERING_KNOWLEDGE_PACK,
            source_id=f"catalog:{metadata.catalog_id}:{metadata.catalog_version}",
            extractor_id=_CATALOG_LOADER_ID,
            extractor_version=metadata.catalog_version,
            confidence=1.0,
        )

    def _resolve_provenance(
        self,
        entry_provenance: Sequence[Provenance],
        default: Provenance,
    ) -> tuple[Provenance, ...]:
        if entry_provenance:
            return tuple(entry_provenance)
        return (default,)

    def _build_nodes(
        self,
        entries: Sequence[EngineeringKnowledgeCatalogNode],
        default_provenance: Provenance,
    ) -> list[GraphNode]:
        nodes: list[GraphNode] = []
        for entry in entries:
            properties = validate_node_properties(
                node_type=entry.node_type,
                canonical_key=entry.canonical_key,
                properties=entry.properties,
            )
            provenance = self._resolve_provenance(entry.provenance, default_provenance)
            evidence = tuple(entry.evidence)
            nodes.append(
                self._nodes.create(
                    node_type=entry.node_type,
                    properties=properties,
                    provenance=provenance,
                    evidence=evidence,
                )
            )
        return nodes

    def _build_relationships(
        self,
        entries: Sequence[EngineeringKnowledgeCatalogRelationship],
        default_provenance: Provenance,
    ) -> list[GraphRelationship]:
        ids = EngineeringKnowledgeNodeIdFactory()
        relationships: list[GraphRelationship] = []
        for entry in entries:
            source = ids.create(
                node_type=entry.source.node_type,
                canonical_key=entry.source.canonical_key,
            )
            target = ids.create(
                node_type=entry.target.node_type,
                canonical_key=entry.target.canonical_key,
            )
            provenance = self._resolve_provenance(entry.provenance, default_provenance)
            relationships.append(
                self._relationships.create(
                    relationship_type=entry.relationship_type,
                    source_node_id=source,
                    target_node_id=target,
                    properties=dict(entry.properties),
                    provenance=provenance,
                    evidence=tuple(entry.evidence),
                )
            )
        return relationships
