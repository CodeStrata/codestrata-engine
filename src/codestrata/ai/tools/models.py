"""Typed contracts for the CodeStrata tool layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMTechnologyEvidence,
)


class CodeStrataToolDefinition(BaseModel):
    """Metadata describing a registered CodeStrata tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_model: str = Field(min_length=1)
    output_model: str = Field(min_length=1)


class CodeStrataToolResult(BaseModel):
    """Normalized result returned by tool execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(min_length=1)
    success: bool
    data: Any | None = None
    error: str | None = None


class EmptyToolInput(BaseModel):
    """Input contract for tools that require no parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RepositoryContextOutput(BaseModel):
    """Repository details from an LLMAnalysisContext."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: LLMRepositoryContext


class TechnologiesOutput(BaseModel):
    """Detected technology evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    technologies: list[LLMTechnologyEvidence] = Field(default_factory=list)
    count: int = Field(ge=0)


class MetricsOutput(BaseModel):
    """Repository metrics from an LLMAnalysisContext."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metrics: LLMMetricsContext


class ListFindingsInput(BaseModel):
    """Optional filters for listing findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: str | None = None
    category: str | None = None
    rule_id: str | None = None
    limit: int | None = Field(default=None, ge=1)


class ListFindingsOutput(BaseModel):
    """Filtered finding list with truncation metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: list[LLMFindingEvidence] = Field(default_factory=list)
    total_matched: int = Field(ge=0)
    returned: int = Field(ge=0)
    truncated: bool = False


class GetFindingDetailsInput(BaseModel):
    """Lookup findings by rule identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)


class GetFindingDetailsOutput(BaseModel):
    """All findings matching a rule identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    findings: list[LLMFindingEvidence] = Field(default_factory=list)
    found: bool


class AnalysisEvidenceCoverageOutput(BaseModel):
    """Finding and evidence availability summary for an analysis context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_count: int = Field(ge=0)
    findings_included: int = Field(ge=0)
    findings_original_count: int = Field(ge=0)
    findings_truncated: bool
    findings_with_evidence: int = Field(ge=0)
    total_evidence_locations: int = Field(ge=0)


class LLMAnalysisContextOutput(BaseModel):
    """Complete serialized LLMAnalysisContext wrapper."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: LLMAnalysisContext
