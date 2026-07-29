"""Release readiness models (Phase 5.14)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReleaseCheckItem(BaseModel):
    """One release-readiness check result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ok: bool
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReleaseCheckResult(BaseModel):
    """Aggregate release-readiness result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "release-readiness"
    schema_version: str = "1.0.0"
    ok: bool
    codestrata_version: str
    checks: tuple[ReleaseCheckItem, ...] = ()
    failure_reason: str | None = None
    elapsed_ms: float = 0.0
    summary_path: str | None = None
