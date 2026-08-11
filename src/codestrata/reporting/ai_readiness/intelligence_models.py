"""AI Readiness Intelligence presentation models (Epic 3 Slice 3.8).

HTML/reporting-layer only. Projects existing AiReadinessReportSection and
ai-readiness findings — does not invent AI-ready, agent-ready, RAG-ready,
or production-AI claims.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

AI_READINESS_INTELLIGENCE_SECTION_ID = "report.ai_readiness_intelligence"
AI_READINESS_INTELLIGENCE_SECTION_VERSION = "1.0.0"

AiReadinessSignalFamily = Literal[
    "api_boundaries",
    "documentation_metadata",
    "data_retrieval",
    "ai_integrations",
    "tool_mcp",
    "workflow_agents",
    "observability_governance",
    "other",
]


class AiReadinessOverviewFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    note: str | None = None

    @field_validator("label", "value", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="overview fact field")

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="overview note")


class AiReadinessSignalRow(BaseModel):
    """Repository-observable AI-enablement signal — never a readiness verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    family: AiReadinessSignalFamily
    path: str | None = None
    evidence_ids: tuple[str, ...] = ()
    finding_id: str | None = None
    note: str | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("label", "family", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="signal row field")

    @field_validator("path", "finding_id", "note", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="signal optional field")

    @field_validator("evidence_ids", "limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class AiReadinessSignalGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: str
    title: str
    signals: tuple[AiReadinessSignalRow, ...] = ()

    @field_validator("group_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="signal group field")

    @field_validator("signals", mode="before")
    @classmethod
    def normalize_signals(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class AiReadinessFindingLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    title: str
    severity: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    path: str | None = None
    rule_id: str
    evidence_completeness: str | None = None

    @field_validator(
        "finding_id",
        "title",
        "severity",
        "confidence",
        "rule_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding link field")

    @field_validator("path", "evidence_completeness", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="finding optional field")

    @field_validator("evidence_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class AiReadinessRecommendationLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    priority: str | None = None
    finding_ids: tuple[str, ...] = ()
    objective: str | None = None

    @field_validator("recommendation_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation link field")

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("priority", "objective", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="recommendation optional field")


class AiReadinessCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    status: str
    display: str
    note: str | None = None

    @field_validator("label", "status", "display", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage row field")

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="coverage note")


class AiReadinessIntelligenceSection(BaseModel):
    """Customer AI Readiness Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = AI_READINESS_INTELLIGENCE_SECTION_ID
    section_version: str = AI_READINESS_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[AiReadinessOverviewFact, ...] = ()
    signal_groups: tuple[AiReadinessSignalGroup, ...] = ()
    findings: tuple[AiReadinessFindingLink, ...] = ()
    recommendations: tuple[AiReadinessRecommendationLink, ...] = ()
    coverage_rows: tuple[AiReadinessCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    empty_findings_message: str | None = None

    @field_validator(
        "section_id",
        "section_version",
        "status",
        "status_label",
        "status_summary",
        "confidence",
        "confidence_label",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="ai readiness intelligence field")

    @field_validator(
        "overview_facts",
        "signal_groups",
        "findings",
        "recommendations",
        "coverage_rows",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("empty_findings_message", mode="before")
    @classmethod
    def normalize_message(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="empty findings message")
