"""MCP-facing response models for CodeStrata."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BoundedListResponse(BaseModel):
    """Collection response with explicit truncation metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[Any]
    returned_count: int = Field(ge=0)
    truncated: bool
    limit: int = Field(ge=1)


class AbsentArtifactResponse(BaseModel):
    """Clear absent result for optional AI artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    present: bool = False
    artifact: str
    message: str


class AssessmentExecutionResponse(BaseModel):
    """Concise MCP response for assessment execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    repository_id: str | None = None
    snapshot_id: str | None = None
    status: str
    repository_display_name: str
    branch: str | None = None
    revision_type: str | None = None
    revision_id: str | None = None
    findings_count: int = Field(ge=0)
    recommendations_count: int = Field(ge=0)
    phase3_findings_count: int | None = None
    phase3_recommendations_count: int | None = None
    ai_requested: bool
    ai_status: str
    report_generated: bool
    output_reference: str | None = None
    duration_ms: float | None = None
    completed_at: str | None = None
    warnings: tuple[str, ...] = ()
    suggested_follow_ups: tuple[str, ...] = ()
