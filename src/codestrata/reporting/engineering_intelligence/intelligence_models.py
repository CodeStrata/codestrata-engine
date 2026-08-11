"""Engineering Intelligence Summary presentation models (Epic 3 Slice 3.10).

HTML/reporting-layer only. Synthesizes existing assessment-head outputs,
Priority Actions, and roadmap counts. Does not invent findings,
recommendations, Priority Actions, scores, or maturity claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

ENGINEERING_INTELLIGENCE_SECTION_ID = "report.engineering_intelligence"
ENGINEERING_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class EngineeringOverviewFact(BaseModel):
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


class EngineeringHeadSummary(BaseModel):
    """Compact per-head rollup — links to the canonical assessment-head section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    head_id: str
    title: str
    anchor: str
    status: str
    status_label: str
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    confidence: str = "unavailable"
    confidence_label: str = "Confidence unavailable"
    coverage: str = "unavailable"
    priority_action_count: int = Field(default=0, ge=0)

    @field_validator(
        "head_id",
        "title",
        "anchor",
        "status",
        "status_label",
        "confidence",
        "confidence_label",
        "coverage",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="head summary field")


class EngineeringCountRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    count: int = Field(default=0, ge=0)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="count row label")


class EngineeringCoverageRow(BaseModel):
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


class EngineeringIntelligenceSection(BaseModel):
    """Customer Engineering Intelligence Summary (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = ENGINEERING_INTELLIGENCE_SECTION_ID
    section_version: str = ENGINEERING_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[EngineeringOverviewFact, ...] = ()
    head_summaries: tuple[EngineeringHeadSummary, ...] = ()
    observations: tuple[str, ...] = ()
    cross_head_facts: tuple[EngineeringOverviewFact, ...] = ()
    priority_action_total: int = Field(default=0, ge=0)
    priority_by_priority: tuple[EngineeringCountRow, ...] = ()
    priority_by_horizon: tuple[EngineeringCountRow, ...] = ()
    coverage_rows: tuple[EngineeringCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    total_findings: int = Field(default=0, ge=0)
    total_recommendations: int = Field(default=0, ge=0)
    roadmap_phase_count: int = Field(default=0, ge=0)
    roadmap_initiative_count: int = Field(default=0, ge=0)
    contributing_head_count: int = Field(default=0, ge=0)

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
        return require_nonblank(str(value), label="engineering intelligence field")

    @field_validator(
        "overview_facts",
        "head_summaries",
        "observations",
        "cross_head_facts",
        "priority_by_priority",
        "priority_by_horizon",
        "coverage_rows",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
