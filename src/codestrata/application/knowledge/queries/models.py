"""Transport-neutral DTOs for knowledge query services."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.knowledge.models import (
    AssessmentRunStatus,
    KnowledgeArtifactKind,
)
from codestrata.domain.repository.enums import RepositoryRevisionType, RepositorySourceType


class DependencyDirection(StrEnum):
    """Direction for component dependency traversal."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


class RepositorySummary(BaseModel):
    """Public repository discovery record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    canonical_key: str
    display_name: str
    source_type: RepositorySourceType
    latest_completed_run_id: str | None = None
    latest_snapshot_id: str | None = None
    latest_assessed_at: datetime | None = None


class AssessmentRunSummary(BaseModel):
    """Assessment run summary for history queries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    repository_id: str
    snapshot_id: str | None = None
    status: AssessmentRunStatus
    mode: str
    branch: str | None = None
    revision_type: RepositoryRevisionType | None = None
    revision_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error_code: str | None = None
    artifact_kinds: tuple[KnowledgeArtifactKind, ...] = ()
    codestrata_version: str
    ruleset_version: str


class SnapshotSummary(BaseModel):
    """Repository content snapshot summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    repository_id: str
    branch: str | None = None
    revision_type: RepositoryRevisionType
    revision_id: str
    content_fingerprint: str
    captured_at: datetime


class SnapshotFileChangeView(BaseModel):
    """One file-level change between two historical manifests."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    change_type: str
    previous_size_bytes: int | None = None
    current_size_bytes: int | None = None
    previous_content_digest: str | None = None
    current_content_digest: str | None = None


class SnapshotComparisonCounts(BaseModel):
    """Aggregate counts for a snapshot comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    added: int = Field(ge=0)
    modified: int = Field(ge=0)
    deleted: int = Field(ge=0)
    metadata_changed: int = Field(ge=0)
    renamed: int = Field(ge=0, default=0)


class SnapshotComparison(BaseModel):
    """Historical comparison of two persisted repository manifests.

    Renames are not detected in this increment and remain empty; a rename appears
    as one deleted path and one added path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    previous_snapshot_id: str
    current_snapshot_id: str
    previous_content_fingerprint: str
    current_content_fingerprint: str
    added_files: tuple[SnapshotFileChangeView, ...] = ()
    modified_files: tuple[SnapshotFileChangeView, ...] = ()
    deleted_files: tuple[SnapshotFileChangeView, ...] = ()
    metadata_changed_files: tuple[SnapshotFileChangeView, ...] = ()
    renamed_files: tuple[SnapshotFileChangeView, ...] = ()
    counts: SnapshotComparisonCounts


class ArtifactSummary(BaseModel):
    """Artifact index entry without blob paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str
    artifact_kind: KnowledgeArtifactKind
    schema_version: str
    source_fingerprint: str | None = None
    created_at: datetime


class EvidenceView(BaseModel):
    """Bounded evidence excerpt from Phase 3 findings/recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None
    node_id: str | None = None


class FindingView(BaseModel):
    """Authoritative Phase 3 finding view for knowledge queries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    severity: str
    category: str
    title: str
    description: str
    subject_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Epic 2 Slice 2.8 — preserve domain EvidenceRef traceability (additive).
    evidence_refs: tuple[dict[str, Any], ...] = ()
    primary_evidence_id: str | None = None
    synthesized_from_evidence_ids: tuple[str, ...] = ()
    evidence_completeness: str = "legacy"
    limitations: tuple[str, ...] = ()


class RecommendationActionView(BaseModel):
    """Actionable step within a recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int
    title: str
    description: str
    command: str | None = None
    documentation_ref: str | None = None


class RecommendationView(BaseModel):
    """Authoritative Phase 3 recommendation view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    provider_id: str
    priority: str
    category: str
    title: str
    summary: str
    rationale: str
    related_finding_ids: tuple[str, ...] = ()
    affected_node_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    actions: tuple[RecommendationActionView, ...] = ()
    roadmap_phase: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Epic 2 Slice 2.8 — preserve finding traceability (additive).
    supporting_finding_ids: tuple[str, ...] = ()
    primary_finding_id: str | None = None
    recommendation_type: str = "legacy"
    evidence_completeness: str = "legacy"
    limitations: tuple[str, ...] = ()


class GraphNodeView(BaseModel):
    """Lightweight graph node projection for explanations and components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    node_type: str
    name: str | None = None
    path: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance_source_ids: tuple[str, ...] = ()


class FindingExplanation(BaseModel):
    """Deterministic explanation assembled from persisted knowledge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding: FindingView
    rule_id: str
    ruleset_version: str | None = None
    subjects: tuple[GraphNodeView, ...] = ()
    related_recommendations: tuple[RecommendationView, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    graph_references: tuple[str, ...] = ()


class RecommendationExplanation(BaseModel):
    """Deterministic recommendation explanation from persisted knowledge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation: RecommendationView
    related_findings: tuple[FindingView, ...] = ()
    affected_components: tuple[GraphNodeView, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    roadmap_phase: str | None = None
    provider_id: str


class ComponentView(BaseModel):
    """Repository Graph component/node view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str
    component_type: str
    name: str | None = None
    path: str | None = None
    technologies: tuple[str, ...] = ()
    incoming_dependency_count: int = Field(ge=0)
    outgoing_dependency_count: int = Field(ge=0)
    provenance_source_ids: tuple[str, ...] = ()
    properties: dict[str, Any] = Field(default_factory=dict)


class DependencyView(BaseModel):
    """Directed dependency edge between components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_component_id: str
    target_component_id: str
    relationship_type: str
    direction: str
    depth: int = Field(ge=1)
    provenance_source_ids: tuple[str, ...] = ()


class DependencyQueryResult(BaseModel):
    """Bounded dependency traversal result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str
    direction: str
    depth: int
    dependencies: tuple[DependencyView, ...] = ()
    truncated: bool = False
