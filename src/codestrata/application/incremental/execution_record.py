"""Incremental execution record DTO (primary CLI/MCP inspection payload)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionStatus,
)
from codestrata.application.incremental.explainability import IncrementalExplanation
from codestrata.application.incremental.metrics import IncrementalExecutionMetrics
from codestrata.application.incremental.models import IncrementalPlanMode
from codestrata.application.incremental.validation_models import IncrementalValidationResult


class IncrementalExecutionRecord(BaseModel):
    """Operational record returned to CLI and MCP inspection flows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: str
    plan_id: str | None = None
    repository_id: str | None = None
    base_run_id: str | None = None
    base_snapshot_id: str | None = None
    run_id: str | None = None
    snapshot_id: str | None = None
    requested_strategy: IncrementalPlanMode | str | None = None
    actual_mode: IncrementalExecutionMode
    status: IncrementalExecutionStatus
    fallback_used: bool = False
    fallback_reasons: tuple[str, ...] = ()
    compatibility_summary: dict[str, Any] = Field(default_factory=dict)
    change_summary: dict[str, Any] = Field(default_factory=dict)
    impact_summary: dict[str, Any] = Field(default_factory=dict)
    reuse_summary: dict[str, Any] = Field(default_factory=dict)
    recompute_summary: dict[str, Any] = Field(default_factory=dict)
    metrics: IncrementalExecutionMetrics | None = None
    validation: IncrementalValidationResult | None = None
    explanations: tuple[IncrementalExplanation, ...] = ()
    warnings: tuple[str, ...] = ()
    trusted: bool = True
    started_at: datetime
    completed_at: datetime | None = None
