"""Cross-rule Finding correlation contracts (Epic 5 Slice 5.12).

Correlated Findings remain independently valid. This is not duplicate
consolidation, title similarity, severity calibration, or AI inference.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids


class FindingCorrelationType(StrEnum):
    SHARED_SUBJECT = "shared_subject"
    SHARED_EVIDENCE = "shared_evidence"
    SHARED_LOCATION = "shared_location"
    SHARED_MEASUREMENT_SCOPE = "shared_measurement_scope"
    SHARED_GRAPH_SUBJECT = "shared_graph_subject"
    CONFIGURATION_CLUSTER = "configuration_cluster"
    DEPENDENCY_CLUSTER = "dependency_cluster"
    ARCHITECTURE_CLUSTER = "architecture_cluster"
    COMPLEXITY_CLUSTER = "complexity_cluster"
    DEPLOYMENT_CLUSTER = "deployment_cluster"
    AI_INTEGRATION_CLUSTER = "ai_integration_cluster"
    CAUSE_AND_EFFECT = "cause_and_effect"
    CONTRIBUTING_CONDITIONS = "contributing_conditions"
    CROSS_HEAD_MODERNIZATION = "cross_head_modernization"
    OTHER = "other"


class FindingCorrelationBasis(StrEnum):
    SAME_EVIDENCE_ID = "same_evidence_id"
    SAME_PARENT_EVIDENCE = "same_parent_evidence"
    SAME_PATH = "same_path"
    SAME_SYMBOLIC_REFERENCE = "same_symbolic_reference"
    SAME_CONFIGURATION_KEY = "same_configuration_key"
    SAME_DEPENDENCY_IDENTITY = "same_dependency_identity"
    SAME_MEASUREMENT_SCOPE_REF = "same_measurement_scope_ref"
    SAME_GRAPH_NODE = "same_graph_node"
    SAME_GRAPH_EDGE = "same_graph_edge"
    SAME_GRAPH_CYCLE = "same_graph_cycle"
    SAME_REPOSITORY_ARTIFACT = "same_repository_artifact"
    EXPLICIT_RULE_RELATIONSHIP = "explicit_rule_relationship"
    REVIEWED_CROSS_HEAD_POLICY = "reviewed_cross_head_policy"


class CorrelationDirection(StrEnum):
    UNDIRECTED = "undirected"
    SOURCE_TO_TARGET = "source_to_target"
    CAUSE_TO_EFFECT = "cause_to_effect"
    CONTRIBUTOR_TO_OUTCOME = "contributor_to_outcome"


class CorrelationConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


_CONFIDENCE_RANK: dict[CorrelationConfidenceLevel, int] = {
    CorrelationConfidenceLevel.HIGH: 3,
    CorrelationConfidenceLevel.MODERATE: 2,
    CorrelationConfidenceLevel.LIMITED: 1,
    CorrelationConfidenceLevel.UNAVAILABLE: 0,
}


class CorrelationConfidence(BaseModel):
    """How strongly deterministic identities support a Finding relationship."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: CorrelationConfidenceLevel
    basis: tuple[FindingCorrelationBasis, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[Any, ...]:
        return tuple(as_tuple(value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)


def min_correlation_confidence(
    *levels: CorrelationConfidenceLevel,
) -> CorrelationConfidenceLevel:
    if not levels:
        return CorrelationConfidenceLevel.UNAVAILABLE
    return min(levels, key=lambda item: _CONFIDENCE_RANK[item])


_HIGH_BASES: frozenset[FindingCorrelationBasis] = frozenset(
    {
        FindingCorrelationBasis.SAME_EVIDENCE_ID,
        FindingCorrelationBasis.SAME_CONFIGURATION_KEY,
        FindingCorrelationBasis.SAME_DEPENDENCY_IDENTITY,
        FindingCorrelationBasis.SAME_GRAPH_NODE,
        FindingCorrelationBasis.SAME_GRAPH_EDGE,
        FindingCorrelationBasis.SAME_GRAPH_CYCLE,
        FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        FindingCorrelationBasis.REVIEWED_CROSS_HEAD_POLICY,
    }
)


def build_correlation_id(
    *,
    correlation_type: FindingCorrelationType | str,
    finding_ids: tuple[str, ...],
    direction: CorrelationDirection | str = CorrelationDirection.UNDIRECTED,
    shared_identity: str = "",
    policy_id: str = "",
) -> str:
    """Stable ``correlation:{sha256[:24]}`` identity."""

    ctype = (
        correlation_type.value
        if isinstance(correlation_type, FindingCorrelationType)
        else str(correlation_type)
    )
    dir_value = (
        direction.value if isinstance(direction, CorrelationDirection) else str(direction)
    )
    ids = tuple(require_nonblank(str(item), label="finding_id") for item in finding_ids)
    if dir_value == CorrelationDirection.UNDIRECTED.value:
        ordered = tuple(sorted(ids))
    else:
        ordered = ids
    material = "\n".join(
        [
            ctype.strip().lower(),
            dir_value.strip().lower(),
            *ordered,
            (shared_identity or "").strip().lower(),
            (policy_id or "").strip().lower(),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"correlation:{digest}"


class FindingCorrelation(BaseModel):
    """One typed relationship between distinct Findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: str
    correlation_type: FindingCorrelationType
    finding_ids: tuple[str, ...]
    primary_finding_id: str
    assessment_head_ids: tuple[str, ...] = ()
    shared_evidence_ids: tuple[str, ...] = ()
    shared_location_refs: tuple[EvidenceLocation, ...] = ()
    shared_subject_ids: tuple[str, ...] = ()
    confidence: CorrelationConfidence
    basis: tuple[FindingCorrelationBasis, ...]
    direction: CorrelationDirection = CorrelationDirection.UNDIRECTED
    limitations: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("correlation_id", "primary_finding_id", mode="before")
    @classmethod
    def require_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="correlation field")

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_finding_ids(cls, value: object) -> tuple[str, ...]:
        # Preserve caller order for directional correlations; undirected
        # relationships are validated as sorted in validate_correlation.
        items = tuple(as_tuple(value))
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            text = require_nonblank(str(item), label="finding_id")
            if text in seen:
                continue
            seen.add(text)
            out.append(text)
        return tuple(out)

    @field_validator(
        "assessment_head_ids",
        "shared_evidence_ids",
        "shared_subject_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="correlation id ref")

    @field_validator("shared_location_refs", "basis", mode="before")
    @classmethod
    def normalize_tuples(cls, value: object) -> tuple[Any, ...]:
        return tuple(as_tuple(value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        # JSON-scalar values only.
        out: dict[str, Any] = {}
        for key, item in dict(value).items():
            if isinstance(item, (str, int, float, bool)) or item is None:
                out[str(key)] = item
            else:
                out[str(key)] = json.dumps(item, sort_keys=True, separators=(",", ":"))
        return dict(sorted(out.items()))

    @model_validator(mode="after")
    def validate_correlation(self) -> FindingCorrelation:
        if not self.correlation_id.startswith("correlation:"):
            raise ValueError("correlation_id must use correlation: prefix")
        if len(self.finding_ids) < 2:
            raise ValueError("correlation requires at least two distinct Findings")
        if self.primary_finding_id not in self.finding_ids:
            raise ValueError("primary_finding_id must be a member of finding_ids")
        if self.primary_finding_id in set(self.finding_ids) and len(self.finding_ids) != len(
            set(self.finding_ids)
        ):
            raise ValueError("finding_ids must be unique")
        if not self.basis:
            raise ValueError("correlation requires at least one basis")
        if (
            self.confidence.level is CorrelationConfidenceLevel.HIGH
            and not set(self.basis).intersection(_HIGH_BASES)
        ):
            raise ValueError(
                "High Correlation Confidence requires exact identity or explicit policy basis"
            )
        if self.direction is CorrelationDirection.UNDIRECTED:
            if tuple(sorted(self.finding_ids)) != self.finding_ids:
                raise ValueError("undirected finding_ids must be sorted")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class FindingCorrelationCluster(BaseModel):
    """Connected component of compatible correlations (edges preserved)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    finding_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    primary_finding_id: str
    assessment_head_ids: tuple[str, ...] = ()
    cluster_type: str = "compatible_component"
    limitations: tuple[str, ...] = ()

    @field_validator(
        "cluster_id",
        "primary_finding_id",
        "cluster_type",
        mode="before",
    )
    @classmethod
    def require_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="cluster field")

    @field_validator(
        "finding_ids",
        "correlation_ids",
        "assessment_head_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="cluster id ref")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @model_validator(mode="after")
    def validate_cluster(self) -> FindingCorrelationCluster:
        if len(self.finding_ids) < 2:
            raise ValueError("cluster requires at least two Findings")
        if self.primary_finding_id not in self.finding_ids:
            raise ValueError("primary_finding_id must be a cluster member")
        if not self.correlation_ids:
            raise ValueError("cluster requires at least one correlation_id")
        return self


class FindingCorrelationDiagnostics(BaseModel):
    """Internal correlation summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_count: int = Field(default=0, ge=0)
    correlation_count: int = Field(default=0, ge=0)
    correlated_finding_count: int = Field(default=0, ge=0)
    correlations_by_type: dict[str, int] = Field(default_factory=dict)
    cross_head_correlation_count: int = Field(default=0, ge=0)
    unresolved_reference_count: int = Field(default=0, ge=0)
    policy_match_count: int = Field(default=0, ge=0)
    rejected_candidate_count: int = Field(default=0, ge=0)


class FindingCorrelationResult(BaseModel):
    """Result of correlating a consolidated Finding collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Any, ...] = ()
    correlations: tuple[FindingCorrelation, ...] = ()
    clusters: tuple[FindingCorrelationCluster, ...] = ()
    diagnostics: FindingCorrelationDiagnostics = Field(
        default_factory=FindingCorrelationDiagnostics
    )
    limitations: tuple[str, ...] = ()

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)
