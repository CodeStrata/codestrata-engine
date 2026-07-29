"""Immutable knowledge-binding result models.

``KnowledgeBindingResult`` is the Knowledge Pipeline output and the intended
input contract for the Assessment Graph. It never embeds repository identity
into the Engineering Knowledge Graph.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.graph.ids import GraphId, NodeId
from codestrata.domain.graph.models import EvidenceReference, Provenance
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.knowledge_binding.enums import (
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
)
from codestrata.domain.knowledge_binding.ids import build_knowledge_binding_id

KNOWLEDGE_BINDING_RESULT_VERSION = "1.2.0"


class KnowledgeBinding(BaseModel):
    """One deterministic link from a repository observation to a knowledge concept."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binding_id: str
    repository_node_id: NodeId
    knowledge_node_id: NodeId
    binding_type: KnowledgeBindingType
    confidence: float = Field(ge=0.0, le=1.0)
    matching_strategy: KnowledgeMatchingStrategy
    matched_key: str
    observation_kind: KnowledgeObservationKind
    repository_node_type: str
    knowledge_node_type: str
    evidence: tuple[EvidenceReference, ...] = ()
    provenance: tuple[Provenance, ...] = ()

    @field_validator("binding_id", "repository_node_type", "knowledge_node_type", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        return require_nonblank(str(value), label="binding field")

    @field_validator("matched_key", mode="before")
    @classmethod
    def normalize_matched_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))

    @field_validator("evidence", "provenance", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @classmethod
    def create(
        cls,
        *,
        repository_node_id: NodeId,
        knowledge_node_id: NodeId,
        binding_type: KnowledgeBindingType,
        confidence: float,
        matching_strategy: KnowledgeMatchingStrategy,
        matched_key: str,
        observation_kind: KnowledgeObservationKind,
        repository_node_type: str,
        knowledge_node_type: str,
        evidence: tuple[EvidenceReference, ...] = (),
        provenance: tuple[Provenance, ...] = (),
    ) -> KnowledgeBinding:
        """Construct a binding with a deterministic ``binding_id``."""

        binding_id = build_knowledge_binding_id(
            repository_node_id=repository_node_id,
            knowledge_node_id=knowledge_node_id,
            matching_strategy=matching_strategy,
            matched_key=matched_key,
        )
        return cls(
            binding_id=binding_id,
            repository_node_id=repository_node_id,
            knowledge_node_id=knowledge_node_id,
            binding_type=binding_type,
            confidence=confidence,
            matching_strategy=matching_strategy,
            matched_key=matched_key,
            observation_kind=observation_kind,
            repository_node_type=repository_node_type,
            knowledge_node_type=knowledge_node_type,
            evidence=evidence,
            provenance=provenance,
        )


class UnmatchedKnowledgeObservation(BaseModel):
    """A repository observation that did not bind to any knowledge concept.

    Informational only: not a finding, risk, or recommendation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_node_id: NodeId
    observation_kind: KnowledgeObservationKind
    candidate_key: str
    repository_node_type: str
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("candidate_key", mode="before")
    @classmethod
    def normalize_candidate_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))

    @field_validator("repository_node_type", mode="before")
    @classmethod
    def normalize_node_type(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_node_type")

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class KnowledgeBindingResult(BaseModel):
    """Immutable pipeline output: sorted bindings plus match coverage metadata.

    Identifies the exact Repository Graph and Engineering Knowledge Graph inputs
    by graph ID and source fingerprint so Assessment Graph construction can
    fail closed on mismatched inputs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    result_version: str = KNOWLEDGE_BINDING_RESULT_VERSION
    repository_graph_id: GraphId
    repository_source_fingerprint: str
    knowledge_graph_id: GraphId
    knowledge_source_fingerprint: str
    matching_strategy: KnowledgeMatchingStrategy
    bindings: tuple[KnowledgeBinding, ...] = ()
    considered_repository_node_ids: tuple[NodeId, ...] = ()
    unmatched_repository_node_ids: tuple[NodeId, ...] = ()
    unmatched_observations: tuple[UnmatchedKnowledgeObservation, ...] = ()

    @field_validator("result_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_nonblank(str(value), label="result_version")

    @field_validator(
        "repository_source_fingerprint",
        "knowledge_source_fingerprint",
        mode="before",
    )
    @classmethod
    def normalize_fingerprints(cls, value: object) -> str:
        return require_nonblank(str(value), label="source_fingerprint")

    @field_validator(
        "bindings",
        "considered_repository_node_ids",
        "unmatched_repository_node_ids",
        "unmatched_observations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
