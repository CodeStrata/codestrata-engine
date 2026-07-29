"""Immutable models for Phase 2F.2 incremental execution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.execution_policies import IncrementalExecutionPolicy
from codestrata.application.incremental.models import (
    CandidateRepositoryState,
    IncrementalAssessmentPlan,
)


class IncrementalExecutionMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL_REBUILD_FALLBACK = "full_rebuild_fallback"


class IncrementalExecutionStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    FALLBACK_COMPLETED = "fallback_completed"


class IncrementalExecutionStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    REUSED = "reused"
    RECOMPUTED = "recomputed"
    MERGED = "merged"
    SKIPPED = "skipped"
    COMPLETED = "completed"
    FAILED = "failed"


class IncrementalReuseCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files: int = Field(ge=0, default=0)
    repository_graph_nodes: int = Field(ge=0, default=0)
    repository_graph_edges: int = Field(ge=0, default=0)
    knowledge_graph_nodes: int = Field(ge=0, default=0)
    knowledge_graph_edges: int = Field(ge=0, default=0)
    assessment_graph_nodes: int = Field(ge=0, default=0)
    assessment_graph_edges: int = Field(ge=0, default=0)
    findings: int = Field(ge=0, default=0)
    recommendations: int = Field(ge=0, default=0)
    roadmap_phases: int = Field(ge=0, default=0)
    ai_artifacts: int = Field(ge=0, default=0)


class IncrementalRecomputeCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files: int = Field(ge=0, default=0)
    repository_graph_nodes: int = Field(ge=0, default=0)
    repository_graph_edges: int = Field(ge=0, default=0)
    knowledge_graph_nodes: int = Field(ge=0, default=0)
    knowledge_graph_edges: int = Field(ge=0, default=0)
    assessment_graph_nodes: int = Field(ge=0, default=0)
    assessment_graph_edges: int = Field(ge=0, default=0)
    findings: int = Field(ge=0, default=0)
    recommendations: int = Field(ge=0, default=0)
    roadmap_phases: int = Field(ge=0, default=0)
    ai_artifacts: int = Field(ge=0, default=0)


class IncrementalExecutionStepResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    step_type: str
    status: IncrementalExecutionStepStatus
    reasons: tuple[str, ...] = ()
    subject_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncrementalExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: str
    output_directory: str
    branch: str | None = None
    plan: IncrementalAssessmentPlan | None = None
    previous_run_id: str | None = None
    with_ai: bool = False
    candidate: CandidateRepositoryState | None = None
    policy: IncrementalExecutionPolicy | None = None
    config_path: str | None = None


class IncrementalExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    plan_id: str | None
    mode: IncrementalExecutionMode
    status: IncrementalExecutionStatus
    repository_id: str | None = None
    previous_run_id: str | None = None
    previous_snapshot_id: str | None = None
    run_id: str | None = None
    snapshot_id: str | None = None
    reused_counts: IncrementalReuseCounts = Field(default_factory=IncrementalReuseCounts)
    recomputed_counts: IncrementalRecomputeCounts = Field(
        default_factory=IncrementalRecomputeCounts
    )
    fallback_used: bool = False
    fallback_reasons: tuple[str, ...] = ()
    steps: tuple[IncrementalExecutionStepResult, ...] = ()
    warnings: tuple[str, ...] = ()
    started_at: datetime
    completed_at: datetime | None = None
    assessment_result: Any | None = None
