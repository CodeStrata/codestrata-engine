"""Observed/declared structural edges at supported confidence and depth.

Call edges are admitted only for resolved callable-to-callable observations.
Cross-repository and runtime-topology inferences are never admitted.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.repository_graph.enums import (
    OBSERVED_STRUCTURAL_EDGE_TYPES,
    RepositoryNodeType,
    RepositoryRelationshipType,
)
from codestrata.domain.repository_graph.schema import allowed_relationship_endpoints

FAN_OUT_THRESHOLD_DEFAULT = 10
MODULE_COUPLING_EDGE_TYPES: frozenset[str] = frozenset(
    {
        RepositoryRelationshipType.IMPORTS.value,
        RepositoryRelationshipType.DEPENDS_ON.value,
    }
)


class StructuralConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StructuralDepth(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"


class StructuralView(StrEnum):
    DECLARED = "declared"
    RESOLVED = "resolved"
    BOTH = "both"


class StructuralDropReason(StrEnum):
    CROSS_REPOSITORY = "cross_repository"
    RUNTIME_TOPOLOGY = "runtime_topology"
    UNSUPPORTED_CONFIDENCE = "unsupported_confidence"
    UNSUPPORTED_DEPTH = "unsupported_depth"
    UNRELIABLE_CALL = "unreliable_call"
    INVALID_ENDPOINTS = "invalid_endpoints"
    UNKNOWN_EDGE_TYPE = "unknown_edge_type"
    ABSOLUTE_EVIDENCE_PATH = "absolute_evidence_path"
    BLANK_ENDPOINT = "blank_endpoint"


_SUPPORTED_CONFIDENCE: dict[str, frozenset[StructuralConfidence]] = {
    RepositoryRelationshipType.IMPORTS.value: frozenset(
        {StructuralConfidence.HIGH, StructuralConfidence.MEDIUM}
    ),
    RepositoryRelationshipType.DEPENDS_ON.value: frozenset(
        {StructuralConfidence.HIGH, StructuralConfidence.MEDIUM}
    ),
    RepositoryRelationshipType.IMPLEMENTS.value: frozenset({StructuralConfidence.HIGH}),
    RepositoryRelationshipType.EXPOSES_API.value: frozenset({StructuralConfidence.HIGH}),
    RepositoryRelationshipType.USES_DEPENDENCY.value: frozenset(
        {StructuralConfidence.HIGH, StructuralConfidence.MEDIUM}
    ),
    RepositoryRelationshipType.CALLS.value: frozenset({StructuralConfidence.HIGH}),
}


class StructuralEdgeObservation(BaseModel):
    """One observed or declared structural edge before admission."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_type: str
    source_id: str
    target_id: str
    source_type: RepositoryNodeType
    target_type: RepositoryNodeType
    confidence: StructuralConfidence
    depth: StructuralDepth = StructuralDepth.DIRECT
    view: StructuralView = StructuralView.RESOLVED
    unknown: bool = False
    resolved: bool = True
    cross_repository: bool = False
    runtime_topology: bool = False
    evidence_path: str | None = None
    source_root: str | None = None

    @field_validator("edge_type", "source_id", "target_id", mode="before")
    @classmethod
    def require_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="structural edge")

    @field_validator("evidence_path", "source_root", mode="before")
    @classmethod
    def optional_relative(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="structural path")


class AdmittedStructuralEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_id: str
    edge_type: str
    source_id: str
    target_id: str
    source_type: RepositoryNodeType
    target_type: RepositoryNodeType
    view: StructuralView
    unknown: bool
    evidence_path: str | None = None
    source_root: str | None = None


class DroppedStructuralEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation: StructuralEdgeObservation
    reason: StructuralDropReason


def looks_absolute_path(value: str | None) -> bool:
    if not value:
        return False
    if value.startswith("/") and not value.startswith("./"):
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in (":\\", ":/", "\\\\"))


def admit_structural_edge(
    observation: StructuralEdgeObservation,
) -> StructuralDropReason | None:
    """Return a drop reason, or None when the observation may be stored."""

    if not observation.source_id.strip() or not observation.target_id.strip():
        return StructuralDropReason.BLANK_ENDPOINT
    if observation.cross_repository:
        return StructuralDropReason.CROSS_REPOSITORY
    if observation.runtime_topology:
        return StructuralDropReason.RUNTIME_TOPOLOGY
    if looks_absolute_path(observation.evidence_path) or looks_absolute_path(
        observation.source_root
    ):
        return StructuralDropReason.ABSOLUTE_EVIDENCE_PATH
    try:
        rel_type = RepositoryRelationshipType(observation.edge_type)
    except ValueError:
        return StructuralDropReason.UNKNOWN_EDGE_TYPE
    if rel_type not in OBSERVED_STRUCTURAL_EDGE_TYPES:
        return StructuralDropReason.UNKNOWN_EDGE_TYPE
    allowed_confidence = _SUPPORTED_CONFIDENCE.get(rel_type.value)
    if allowed_confidence is None or observation.confidence not in allowed_confidence:
        return StructuralDropReason.UNSUPPORTED_CONFIDENCE
    if observation.depth is not StructuralDepth.DIRECT:
        return StructuralDropReason.UNSUPPORTED_DEPTH
    endpoints = allowed_relationship_endpoints(rel_type)
    if (observation.source_type, observation.target_type) not in endpoints:
        return StructuralDropReason.INVALID_ENDPOINTS
    if rel_type is RepositoryRelationshipType.CALLS:
        reliable = (
            observation.resolved
            and not observation.unknown
            and observation.confidence is StructuralConfidence.HIGH
            and observation.source_type is RepositoryNodeType.CALLABLE
            and observation.target_type is RepositoryNodeType.CALLABLE
        )
        if not reliable:
            return StructuralDropReason.UNRELIABLE_CALL
    return None
