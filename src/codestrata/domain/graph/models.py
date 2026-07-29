"""Immutable storage-independent graph kernel models."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from codestrata.domain.graph.enums import (
    GraphGenerationMode,
    GraphStatus,
    GraphType,
    ProvenanceSource,
)
from codestrata.domain.graph.ids import GraphId, NodeId
from codestrata.domain.graph.validation import (
    as_tuple,
    normalize_properties,
    optional_nonblank,
    require_nonblank,
)

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list[Any] | dict[str, Any]


def _empty_properties() -> Mapping[str, JSONValue]:
    return MappingProxyType({})


class Provenance(BaseModel):
    """Origin metadata for a node or relationship contribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: ProvenanceSource
    source_id: str
    extractor_id: str | None = None
    extractor_version: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("source_id", mode="before")
    @classmethod
    def normalize_source_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="source_id")

    @field_validator("extractor_id", "extractor_version", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional provenance field")


class EvidenceReference(BaseModel):
    """Pointer to supporting evidence for a graph element."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    symbol_id: NodeId | None = None
    content_hash: str | None = None
    excerpt: str | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence field")

    @field_validator("path", "content_hash", "excerpt", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional evidence field")

    @model_validator(mode="after")
    def validate_line_range(self) -> EvidenceReference:
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError("end_line cannot be earlier than start_line")
        return self


class GraphNode(BaseModel):
    """A typed node in a storage-independent graph snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NodeId
    node_type: str
    schema_version: str
    properties: Mapping[str, JSONValue] = Field(default_factory=_empty_properties)
    provenance: tuple[Provenance, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("node_type", "schema_version", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="node field")

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_node_properties(cls, value: object) -> Mapping[str, Any]:
        if value is None:
            return _empty_properties()
        return normalize_properties(value)

    @field_validator("properties", mode="after")
    @classmethod
    def freeze_node_properties(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(value, MappingProxyType):
            return value
        return MappingProxyType(dict(value))

    @field_serializer("properties")
    def serialize_node_properties(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @field_validator("provenance", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class GraphRelationship(BaseModel):
    """A typed directed relationship between graph nodes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    relationship_type: str
    source_node_id: NodeId
    target_node_id: NodeId
    properties: Mapping[str, JSONValue] = Field(default_factory=_empty_properties)
    provenance: tuple[Provenance, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("id", "relationship_type", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="relationship field")

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_relationship_properties(cls, value: object) -> Mapping[str, Any]:
        if value is None:
            return _empty_properties()
        return normalize_properties(value)

    @field_validator("properties", mode="after")
    @classmethod
    def freeze_relationship_properties(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(value, MappingProxyType):
            return value
        return MappingProxyType(dict(value))

    @field_serializer("properties")
    def serialize_relationship_properties(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @field_validator("provenance", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class GraphMetadata(BaseModel):
    """Identity and generation metadata for a graph snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_id: GraphId
    graph_type: GraphType
    schema_version: str
    generator_version: str
    source_fingerprint: str
    generation_mode: GraphGenerationMode
    status: GraphStatus

    @field_validator("schema_version", "generator_version", "source_fingerprint", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="metadata field")


class GraphSnapshot(BaseModel):
    """Immutable validated view of a complete graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: GraphMetadata
    nodes: tuple[GraphNode, ...] = ()
    relationships: tuple[GraphRelationship, ...] = ()

    @field_validator("nodes", "relationships", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> GraphSnapshot:
        node_ids = [node.id.root for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node IDs must be unique")

        relationship_ids = [item.id for item in self.relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise ValueError("relationship IDs must be unique")

        known = set(node_ids)
        for relationship in self.relationships:
            if relationship.source_node_id.root not in known:
                raise ValueError(
                    "relationship source_node_id "
                    f"'{relationship.source_node_id}' is not present in nodes"
                )
            if relationship.target_node_id.root not in known:
                raise ValueError(
                    "relationship target_node_id "
                    f"'{relationship.target_node_id}' is not present in nodes"
                )
        return self
