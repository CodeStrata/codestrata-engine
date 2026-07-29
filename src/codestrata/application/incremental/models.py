"""Typed models for incremental assessment planning (Phase 2F.1)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.fingerprints import (
    AssessmentContentFingerprint,
    EngineCompatibilityFingerprint,
    PlanningFileFingerprint,
)
from codestrata.application.incremental.policies import IncrementalPlanningPolicy
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.domain.repository.manifests import RepositoryManifest


class FileChangeKind(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    METADATA_CHANGED = "metadata_changed"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class FileChangeDimensions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content_changed: bool = False
    structure_changed: bool = False
    dependencies_changed: bool = False
    metadata_changed: bool = False
    unknown: bool = False


class FileChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    previous_fingerprint: PlanningFileFingerprint | None = None
    current_fingerprint: PlanningFileFingerprint | None = None
    kind: FileChangeKind
    dimensions: FileChangeDimensions = Field(default_factory=FileChangeDimensions)
    role: RepositoryFileKind = RepositoryFileKind.UNKNOWN
    reasons: tuple[str, ...] = ()


class RepositoryChangeSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    previous_snapshot_id: str | None = None
    candidate_snapshot_id: str | None = None
    added: tuple[FileChange, ...] = ()
    modified: tuple[FileChange, ...] = ()
    deleted: tuple[FileChange, ...] = ()
    metadata_changed: tuple[FileChange, ...] = ()
    unchanged_count: int = Field(ge=0, default=0)
    unknown: tuple[FileChange, ...] = ()
    change_count: int = Field(ge=0, default=0)
    has_source_changes: bool = False
    has_build_changes: bool = False
    has_configuration_changes: bool = False
    has_dependency_manifest_changes: bool = False
    has_documentation_only_changes: bool = False


class ImpactEntityKind(StrEnum):
    FILE = "file"
    COMPONENT = "component"
    DEPENDENCY = "dependency"
    TECHNOLOGY = "technology"
    GRAPH_NODE = "graph_node"
    GRAPH_EDGE = "graph_edge"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    ROADMAP_PHASE = "roadmap_phase"
    ARTIFACT = "artifact"


class ImpactReason(StrEnum):
    FILE_ADDED = "file_added"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    DEPENDENCY_CHANGED = "dependency_changed"
    BUILD_CHANGED = "build_changed"
    CONFIGURATION_CHANGED = "configuration_changed"
    COMPONENT_DEPENDENCY = "component_dependency"
    FINDING_SOURCE = "finding_source"
    RECOMMENDATION_REFERENCE = "recommendation_reference"
    SCHEMA_INCOMPATIBLE = "schema_incompatible"
    ENGINE_INCOMPATIBLE = "engine_incompatible"
    UNKNOWN = "unknown"


class ImpactEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ImpactEntityKind
    entity_id: str
    display_name: str | None = None
    source_ids: tuple[str, ...] = ()
    reasons: tuple[ImpactReason, ...] = ()
    directly_impacted: bool = False
    confidence: str = "high"


class ImpactRelationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    target_id: str
    relationship_type: str
    reason: ImpactReason


class ImpactAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    directly_changed_files: tuple[str, ...] = ()
    impacted_components: tuple[ImpactEntity, ...] = ()
    impacted_graph_nodes: tuple[ImpactEntity, ...] = ()
    impacted_findings: tuple[ImpactEntity, ...] = ()
    impacted_recommendations: tuple[ImpactEntity, ...] = ()
    impacted_roadmap_phases: tuple[ImpactEntity, ...] = ()
    relationships: tuple[ImpactRelationship, ...] = ()
    unknown_impacts: tuple[str, ...] = ()
    truncated: bool = False
    requires_full_rebuild: bool = False
    full_rebuild_reasons: tuple[str, ...] = ()


class ReuseDecision(StrEnum):
    REUSABLE = "reusable"
    RECOMPUTE = "recompute"
    FULL_REBUILD = "full_rebuild"
    UNSUPPORTED = "unsupported"


class ReuseAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_kind: str
    subject_id: str
    decision: ReuseDecision
    reasons: tuple[str, ...] = ()
    required_fingerprints: tuple[str, ...] = ()
    missing_fingerprints: tuple[str, ...] = ()
    compatibility_failures: tuple[str, ...] = ()
    impacted_by: tuple[str, ...] = ()
    confidence: str = "high"


class CompatibilityIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    blocking: bool = True
    subject: str | None = None


class CompatibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    compatible: bool
    scanner_compatible: bool = True
    parser_compatible: bool = True
    graph_compatible: bool = True
    rule_compatible: bool = True
    recommendation_compatible: bool = True
    artifact_schema_compatible: bool = True
    tool_compatible: bool = True
    issues: tuple[CompatibilityIssue, ...] = ()
    blocking_reasons: tuple[str, ...] = ()


class IncrementalBaseEligibility(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    repository_id: str | None = None
    run_id: str | None = None
    snapshot_id: str | None = None
    reasons: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    incompatible_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class IncrementalPlanMode(StrEnum):
    NO_CHANGES = "no_changes"
    METADATA_ONLY = "metadata_only"
    INCREMENTAL_CANDIDATE = "incremental_candidate"
    FULL_REBUILD = "full_rebuild"


class IncrementalStepType(StrEnum):
    REUSE_INVENTORY = "reuse_inventory"
    RECOMPUTE_INVENTORY = "recompute_inventory"
    REUSE_TECHNOLOGY_DETECTION = "reuse_technology_detection"
    RECOMPUTE_TECHNOLOGY_DETECTION = "recompute_technology_detection"
    REUSE_REPOSITORY_GRAPH = "reuse_repository_graph"
    REBUILD_REPOSITORY_GRAPH = "rebuild_repository_graph"
    RECOMPUTE_IMPACTED_REPOSITORY_GRAPH = "recompute_impacted_repository_graph"
    REUSE_KNOWLEDGE_GRAPH = "reuse_knowledge_graph"
    REBUILD_KNOWLEDGE_GRAPH = "rebuild_knowledge_graph"
    RECOMPUTE_IMPACTED_KNOWLEDGE_GRAPH = "recompute_impacted_knowledge_graph"
    REUSE_ASSESSMENT_GRAPH = "reuse_assessment_graph"
    REBUILD_ASSESSMENT_GRAPH = "rebuild_assessment_graph"
    RECOMPUTE_IMPACTED_ASSESSMENT_GRAPH = "recompute_impacted_assessment_graph"
    REUSE_FINDINGS = "reuse_findings"
    RERUN_IMPACTED_RULES = "rerun_impacted_rules"
    RERUN_ALL_RULES = "rerun_all_rules"
    REUSE_RECOMMENDATIONS = "reuse_recommendations"
    REGENERATE_IMPACTED_RECOMMENDATIONS = "regenerate_impacted_recommendations"
    REGENERATE_ALL_RECOMMENDATIONS = "regenerate_all_recommendations"
    REUSE_AI_ENRICHMENT = "reuse_ai_enrichment"
    RERUN_AI_ENRICHMENT = "rerun_ai_enrichment"
    VALIDATE_INCREMENTAL_RESULT = "validate_incremental_result"
    PERSIST_RESULT = "persist_result"
    FULL_REBUILD = "full_rebuild"


class IncrementalPlanStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    step_type: IncrementalStepType
    status: str = "planned"
    subject_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    depends_on_steps: tuple[int, ...] = ()
    reusable_count: int = Field(ge=0, default=0)
    recompute_count: int = Field(ge=0, default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncrementalAssessmentPlan(BaseModel):
    """Deterministic plan only — Phase 2F.1 does not execute these steps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str
    mode: IncrementalPlanMode
    repository_id: str | None = None
    previous_run_id: str | None = None
    previous_snapshot_id: str | None = None
    candidate_snapshot_id: str | None = None
    compatibility: CompatibilityResult | None = None
    change_summary: dict[str, Any] = Field(default_factory=dict)
    impact_summary: dict[str, Any] = Field(default_factory=dict)
    reuse_summary: dict[str, Any] = Field(default_factory=dict)
    steps: tuple[IncrementalPlanStep, ...] = ()
    full_rebuild_required: bool = False
    full_rebuild_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: datetime


class CandidateRepositoryState(BaseModel):
    """Candidate inventory for planning (no absolute paths in public DTOs)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_key: str
    display_name: str
    branch: str | None = None
    revision_id: str | None = None
    manifest: RepositoryManifest
    content_fingerprint: AssessmentContentFingerprint
    engine: EngineCompatibilityFingerprint
    warnings: tuple[str, ...] = ()


class IncrementalPlanningRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_identifier: str
    previous_run_id: str | None = None
    branch: str | None = None
    candidate: CandidateRepositoryState | None = None
    policy: IncrementalPlanningPolicy | None = None
