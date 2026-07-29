"""Typed models for Agent Framework requests, steps, and results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.agents.evidence import AgentEvidence
from codestrata.application.knowledge.queries.models import (
    AssessmentRunSummary,
    FindingView,
    RecommendationView,
    RepositorySummary,
    SnapshotComparison,
    SnapshotSummary,
)


class WorkflowType(StrEnum):
    """Supported deterministic agent workflows."""

    REPOSITORY_REVIEW = "repository_review"
    REPOSITORY_ASSESSMENT = "repository_assessment"
    SNAPSHOT_REVIEW = "snapshot_review"
    ASSESSMENT_VALIDATION = "assessment_validation"
    MODERNIZATION_REVIEW = "modernization_review"


class AgentStatus(StrEnum):
    """Lifecycle status for a workflow or step."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AgentName(StrEnum):
    """Known agent identities."""

    KNOWLEDGE = "knowledge"
    ASSESSMENT = "assessment"
    VALIDATION = "validation"
    ORCHESTRATOR = "orchestrator"


class ValidationSeverity(StrEnum):
    """Severity for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class AgentStep(BaseModel):
    """One recorded workflow step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    agent: AgentName
    status: AgentStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    message: str | None = None
    warnings: tuple[str, ...] = ()


class AgentDecision(BaseModel):
    """A concise decision produced during a workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_type: str
    outcome: str
    reason: str
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ValidationIssue(BaseModel):
    """One validation finding about a persisted assessment or review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: ValidationSeverity
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    related_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class AssessmentValidationResult(BaseModel):
    """Typed validation outcome for a persisted assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    blocking: bool
    issues: tuple[ValidationIssue, ...] = ()
    checked_artifacts: tuple[str, ...] = ()
    checked_findings: int = Field(ge=0, default=0)
    checked_recommendations: int = Field(ge=0, default=0)
    checked_components: int = Field(ge=0, default=0)
    ai_validation_status: str = "not_applicable"


class RepositoryReviewRequest(BaseModel):
    """Request a grounded repository review from persisted knowledge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_identifier: str
    branch: str | None = None
    include_snapshot_comparison: bool = True


class RepositoryAssessmentRequest(BaseModel):
    """Request a new assessment through AssessmentApplicationService."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: str
    branch: str | None = None
    with_ai: bool = False
    config_path: str | None = None
    output_directory: str | None = None


class AssessmentValidationRequest(BaseModel):
    """Request validation of a persisted assessment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    repository_id: str | None = None


class SnapshotReviewRequest(BaseModel):
    """Request historical snapshot comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    previous_snapshot_id: str
    current_snapshot_id: str


class ModernizationReviewRequest(BaseModel):
    """Request a grounded modernization review package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_identifier: str
    run_id: str | None = None


class FindingSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)


class RecommendationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)


class ComponentSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)


class RepositoryReviewResult(BaseModel):
    """Grounded repository review assembled from persisted DTOs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.REPOSITORY_REVIEW
    status: AgentStatus
    repository: RepositorySummary | None = None
    latest_run: AssessmentRunSummary | None = None
    latest_snapshot: SnapshotSummary | None = None
    previous_run: AssessmentRunSummary | None = None
    previous_snapshot: SnapshotSummary | None = None
    snapshot_changes: SnapshotComparison | None = None
    finding_summary: FindingSummary | None = None
    recommendation_summary: RecommendationSummary | None = None
    top_findings: tuple[FindingView, ...] = ()
    top_recommendations: tuple[RecommendationView, ...] = ()
    component_summary: ComponentSummary | None = None
    dependency_summary: dict[str, Any] = Field(default_factory=dict)
    ai_status: str = "unknown"
    validation: AssessmentValidationResult | None = None
    evidence: tuple[AgentEvidence, ...] = ()
    decisions: tuple[AgentDecision, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    warnings: tuple[str, ...] = ()


class RepositoryAssessmentResult(BaseModel):
    """Result of an assessment workflow through AssessmentAgent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.REPOSITORY_ASSESSMENT
    status: AgentStatus
    repository_id: str | None = None
    snapshot_id: str | None = None
    run_id: str | None = None
    repository_display_name: str | None = None
    branch: str | None = None
    findings_count: int | None = None
    recommendations_count: int | None = None
    phase3_findings_count: int | None = None
    phase3_recommendations_count: int | None = None
    ai_requested: bool = False
    ai_status: str = "not_requested"
    prior_run_id: str | None = None
    prior_snapshot_id: str | None = None
    assessment: AssessmentRunSummary | None = None
    validation: AssessmentValidationResult | None = None
    evidence: tuple[AgentEvidence, ...] = ()
    decisions: tuple[AgentDecision, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    warnings: tuple[str, ...] = ()


class SnapshotReviewResult(BaseModel):
    """Result of comparing two persisted snapshots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.SNAPSHOT_REVIEW
    status: AgentStatus
    comparison: SnapshotComparison | None = None
    evidence: tuple[AgentEvidence, ...] = ()
    decisions: tuple[AgentDecision, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    warnings: tuple[str, ...] = ()


class AssessmentValidationWorkflowResult(BaseModel):
    """Result of validating a persisted assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.ASSESSMENT_VALIDATION
    status: AgentStatus
    run_id: str
    repository_id: str | None = None
    snapshot_id: str | None = None
    validation: AssessmentValidationResult
    evidence: tuple[AgentEvidence, ...] = ()
    decisions: tuple[AgentDecision, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    warnings: tuple[str, ...] = ()


class RecommendationGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    priority: str | None = None
    category: str | None = None
    roadmap_phase: str | None = None
    recommendation_ids: tuple[str, ...] = ()


class ModernizationReviewResult(BaseModel):
    """Grounded modernization review package from persisted recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.MODERNIZATION_REVIEW
    status: AgentStatus
    repository_id: str | None = None
    run_id: str | None = None
    snapshot_id: str | None = None
    risk_summary: FindingSummary | None = None
    recommendation_groups: tuple[RecommendationGroup, ...] = ()
    roadmap_phases: tuple[str, ...] = ()
    recommendation_summary: RecommendationSummary | None = None
    top_recommendations: tuple[RecommendationView, ...] = ()
    unresolved_recommendation_ids: tuple[str, ...] = ()
    validation: AssessmentValidationResult | None = None
    evidence: tuple[AgentEvidence, ...] = ()
    decisions: tuple[AgentDecision, ...] = ()
    steps: tuple[AgentStep, ...] = ()
    warnings: tuple[str, ...] = ()
