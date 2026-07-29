"""Acceptance result models (Phase 5.13)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AcceptanceCheckResult(BaseModel):
    """One named check within a repository acceptance run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ok: bool
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryAcceptanceResult(BaseModel):
    """Acceptance outcome for one dogfood repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: str
    repository_path: str
    languages: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    onboarding_status: str = "not_run"
    findings: int = 0
    recommendations: int = 0
    roadmap_initiatives: int = 0
    chunks: int = 0
    report_validation: str = "not_run"
    question_answer: str = "not_run"
    mcp_health: str = "not_run"
    determinism: str = "not_run"
    elapsed_ms: float = 0.0
    ok: bool = False
    failure_reason: str | None = None
    checks: tuple[AcceptanceCheckResult, ...] = ()
    json_report_path: str | None = None
    html_report_path: str | None = None
    run_directory: str | None = None
    skipped: bool = False


class AcceptanceHarnessResult(BaseModel):
    """Aggregate MVP acceptance harness result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "mvp-acceptance"
    schema_version: str = "1.0.0"
    ok: bool
    repositories: tuple[RepositoryAcceptanceResult, ...]
    elapsed_ms: float = 0.0
    output_directory: str | None = None
    failure_reason: str | None = None
