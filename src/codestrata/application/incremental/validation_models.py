"""Validation models for Phase 2F.3 incremental post-execution checks."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.execution_models import IncrementalExecutionResult
from codestrata.application.incremental.models import (
    CandidateRepositoryState,
    IncrementalAssessmentPlan,
)


class IncrementalValidationStatus(StrEnum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    SKIPPED = "skipped"


class IncrementalValidationCheckKind(StrEnum):
    EXECUTION_INTEGRITY = "execution_integrity"
    PLAN_CONFORMANCE = "plan_conformance"
    INVENTORY_INTEGRITY = "inventory_integrity"
    REPOSITORY_GRAPH_INTEGRITY = "repository_graph_integrity"
    KNOWLEDGE_GRAPH_INTEGRITY = "knowledge_graph_integrity"
    ASSESSMENT_GRAPH_INTEGRITY = "assessment_graph_integrity"
    FINDING_GROUNDING = "finding_grounding"
    RECOMMENDATION_GROUNDING = "recommendation_grounding"
    ROADMAP_GROUNDING = "roadmap_grounding"
    REUSE_INTEGRITY = "reuse_integrity"
    RECOMPUTATION_INTEGRITY = "recomputation_integrity"
    DELETION_INTEGRITY = "deletion_integrity"
    PROVENANCE_INTEGRITY = "provenance_integrity"
    FALLBACK_INTEGRITY = "fallback_integrity"
    SEMANTIC_EQUIVALENCE = "semantic_equivalence"
    AI_ARTIFACT_INTEGRITY = "ai_artifact_integrity"


class IncrementalValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    check_kind: IncrementalValidationCheckKind
    severity: str = "error"
    safe_message: str
    subject_kind: str | None = None
    subject_id: str | None = None
    related_ids: tuple[str, ...] = ()
    blocking: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncrementalValidationCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: IncrementalValidationCheckKind
    status: IncrementalValidationStatus
    issues: tuple[IncrementalValidationIssue, ...] = ()
    checked_count: int = Field(ge=0, default=0)
    duration_ms: int = Field(ge=0, default=0)


class IncrementalValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    validation_id: str
    execution_id: str | None = None
    plan_id: str | None = None
    repository_id: str | None = None
    run_id: str | None = None
    status: IncrementalValidationStatus
    checks: tuple[IncrementalValidationCheck, ...] = ()
    blocking_issues: tuple[IncrementalValidationIssue, ...] = ()
    warnings: tuple[IncrementalValidationIssue, ...] = ()
    equivalent_to_full: bool | None = None
    equivalence_summary: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime


class IncrementalValidationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution: IncrementalExecutionResult
    plan: IncrementalAssessmentPlan | None = None
    candidate: CandidateRepositoryState | None = None
    enable_equivalence_check: bool = False
    full_reference: Any | None = None
    max_issues: int = Field(default=200, ge=1, le=5_000)
