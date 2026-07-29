"""Immutable catalog document contracts for curated engineering knowledge.

A catalog document is human-maintained seed data. The Engineering Knowledge
Graph domain owns graph semantic validation; this package only describes the
catalog file contract and converts it into domain nodes and relationships.

Catalog references use ``node_type:canonical_key`` so maintainers can link
concepts without embedding generated ``ekg:…`` node IDs. Rule
``condition_expression`` values are inert strings—never evaluated at load time.
"""

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

from codestrata.domain.engineering_knowledge.enums import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
)
from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.engineering_knowledge.properties import EngineeringKnowledgeCatalogMetadata
from codestrata.domain.graph.models import EvidenceReference, Provenance
from codestrata.domain.graph.validation import as_tuple, normalize_properties, require_nonblank

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list[Any] | dict[str, Any]

_FORBIDDEN_PROPERTY_KEYS = frozenset(
    {
        "repository_id",
        "repository_key",
        "repository_path",
        "workspace_path",
        "file_path",
        "absolute_path",
        "assessment_id",
        "scan_id",
        "commit_sha",
        "git_url",
    }
)


def _empty_properties() -> Mapping[str, JSONValue]:
    return MappingProxyType({})


def _reject_forbidden_keys(properties: Mapping[str, Any]) -> Mapping[str, Any]:
    forbidden = sorted(key for key in properties if key in _FORBIDDEN_PROPERTY_KEYS)
    if forbidden:
        raise ValueError(
            "catalog properties must not include repository- or assessment-specific "
            f"fields: {', '.join(forbidden)}"
        )
    return properties


class EngineeringKnowledgeCatalogReference(BaseModel):
    """Stable catalog pointer: node type plus normalized canonical key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_type: EngineeringKnowledgeNodeType
    canonical_key: str

    @field_validator("canonical_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))

    @classmethod
    def parse(cls, value: object) -> EngineeringKnowledgeCatalogReference:
        """Parse ``node_type:canonical_key`` or a mapping with those fields."""

        if isinstance(value, EngineeringKnowledgeCatalogReference):
            return value
        if isinstance(value, Mapping):
            return cls.model_validate(value)
        text = require_nonblank(str(value), label="catalog reference")
        if text.count(":") != 1:
            raise ValueError(
                "catalog reference must be 'node_type:canonical_key' "
                f"(exactly one ':'), got '{text}'"
            )
        node_type_raw, canonical_key = text.split(":", 1)
        return cls(
            node_type=EngineeringKnowledgeNodeType(node_type_raw),
            canonical_key=canonical_key,
        )

    def as_token(self) -> str:
        return f"{self.node_type.value}:{self.canonical_key}"


class EngineeringKnowledgeCatalogNode(BaseModel):
    """One curated knowledge concept entry in a catalog document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_type: EngineeringKnowledgeNodeType
    canonical_key: str
    properties: Mapping[str, JSONValue] = Field(default_factory=_empty_properties)
    provenance: tuple[Provenance, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("canonical_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_node_properties(cls, value: object) -> Mapping[str, Any]:
        if value is None:
            return _empty_properties()
        return _reject_forbidden_keys(normalize_properties(value))

    @field_validator("properties", mode="after")
    @classmethod
    def freeze_properties(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(value, MappingProxyType):
            return value
        return MappingProxyType(dict(value))

    @field_serializer("properties")
    def serialize_properties(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @field_validator("provenance", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    def reference(self) -> EngineeringKnowledgeCatalogReference:
        return EngineeringKnowledgeCatalogReference(
            node_type=self.node_type,
            canonical_key=self.canonical_key,
        )


class EngineeringKnowledgeCatalogRelationship(BaseModel):
    """One curated relationship between catalog concept references."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_type: EngineeringKnowledgeRelationshipType
    source: EngineeringKnowledgeCatalogReference
    target: EngineeringKnowledgeCatalogReference
    properties: Mapping[str, JSONValue] = Field(default_factory=_empty_properties)
    provenance: tuple[Provenance, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("source", "target", mode="before")
    @classmethod
    def parse_reference(cls, value: object) -> EngineeringKnowledgeCatalogReference:
        return EngineeringKnowledgeCatalogReference.parse(value)

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_relationship_properties(cls, value: object) -> Mapping[str, Any]:
        if value is None:
            return _empty_properties()
        return _reject_forbidden_keys(normalize_properties(value))

    @field_validator("properties", mode="after")
    @classmethod
    def freeze_properties(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(value, MappingProxyType):
            return value
        return MappingProxyType(dict(value))

    @field_serializer("properties")
    def serialize_properties(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @field_validator("provenance", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class EngineeringKnowledgeCatalogDocument(BaseModel):
    """Versioned curated catalog payload prior to graph construction.

    Loading is deterministic: identical documents produce identical graphs.
    Catalog loading never evaluates rule expressions or lifecycle dates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: EngineeringKnowledgeCatalogMetadata
    schema_version: str
    nodes: tuple[EngineeringKnowledgeCatalogNode, ...] = ()
    relationships: tuple[EngineeringKnowledgeCatalogRelationship, ...] = ()

    @field_validator("schema_version", mode="before")
    @classmethod
    def normalize_schema_version(cls, value: object) -> str:
        return require_nonblank(str(value), label="schema_version")

    @field_validator("nodes", "relationships", mode="before")
    @classmethod
    def normalize_collections(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @model_validator(mode="after")
    def order_collections(self) -> EngineeringKnowledgeCatalogDocument:
        """Sort entries when order has no semantic meaning (stable dumps)."""

        nodes = tuple(
            sorted(
                self.nodes,
                key=lambda item: (item.node_type.value, item.canonical_key),
            )
        )
        relationships = tuple(
            sorted(
                self.relationships,
                key=lambda item: (
                    item.relationship_type.value,
                    item.source.as_token(),
                    item.target.as_token(),
                ),
            )
        )
        if nodes != self.nodes:
            object.__setattr__(self, "nodes", nodes)
        if relationships != self.relationships:
            object.__setattr__(self, "relationships", relationships)
        return self
