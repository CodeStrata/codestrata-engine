"""Typed property models for Assessment Graph reference nodes and bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.models import EvidenceReference, Provenance
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.knowledge_binding.enums import (
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
)


class _AssessmentPropertyModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def to_properties(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def properties_mapping(model: _AssessmentPropertyModel) -> Mapping[str, Any]:
    """Serialize a property model for ``GraphNode`` / ``GraphRelationship``."""

    return model.to_properties()


class RepositoryEntityReferenceProperties(_AssessmentPropertyModel):
    """Lightweight pointer to a Repository Graph entity."""

    source_repository_graph_id: str
    source_repository_node_id: str
    repository_node_type: str | None = None

    @field_validator(
        "source_repository_graph_id",
        "source_repository_node_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository reference field")

    @field_validator("repository_node_type", mode="before")
    @classmethod
    def normalize_optional_type(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="repository_node_type")


class KnowledgeConceptReferenceProperties(_AssessmentPropertyModel):
    """Lightweight pointer to an Engineering Knowledge Graph concept."""

    source_knowledge_graph_id: str
    source_knowledge_node_id: str
    knowledge_node_type: str | None = None
    canonical_key: str | None = None

    @field_validator(
        "source_knowledge_graph_id",
        "source_knowledge_node_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="knowledge reference field")

    @field_validator("knowledge_node_type", "canonical_key", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="knowledge reference optional field")


class AssessmentBindingProperties(_AssessmentPropertyModel):
    """Properties carried on a ``binds_to_knowledge`` relationship."""

    binding_id: str
    binding_type: KnowledgeBindingType
    confidence: float = Field(ge=0.0, le=1.0)
    matching_strategy: KnowledgeMatchingStrategy
    matched_key: str
    observation_kind: KnowledgeObservationKind
    evidence_references: tuple[EvidenceReference, ...] = ()
    binding_provenance: tuple[Provenance, ...] = ()

    @field_validator("binding_id", "matched_key", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="binding property field")

    @field_validator("evidence_references", "binding_provenance", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
