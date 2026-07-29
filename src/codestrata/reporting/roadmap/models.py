"""Modernization roadmap report presentation models (Phase 5.10)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

ROADMAP_REPORT_SECTION_ID = "report.roadmap"
ROADMAP_REPORT_SECTION_VERSION = "1.0.0"
INITIATIVE_DISPLAY_LIMIT = 48
EVIDENCE_DISPLAY_LIMIT = 12
LIMITATION_DISPLAY_LIMIT = 12


class RoadmapReportEvidenceView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap report evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional roadmap report evidence")


class RoadmapReportInitiativeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    initiative_id: str
    title: str
    summary: str
    phase: str
    phase_label: str
    priority: str
    effort: str
    risk: str
    expected_outcome: str
    depends_on_initiative_ids: tuple[str, ...] = ()
    supporting_finding_ids: tuple[str, ...] = ()
    supporting_recommendation_ids: tuple[str, ...] = ()
    evidence_references: tuple[RoadmapReportEvidenceView, ...] = ()
    confidence: str
    category: str
    sequence: int = Field(default=0, ge=0)

    @field_validator(
        "initiative_id",
        "title",
        "summary",
        "phase",
        "phase_label",
        "priority",
        "effort",
        "risk",
        "expected_outcome",
        "confidence",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap report initiative field")

    @field_validator(
        "depends_on_initiative_ids",
        "supporting_finding_ids",
        "supporting_recommendation_ids",
        "evidence_references",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RoadmapReportPhaseView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_id: str
    phase: str
    title: str
    objective: str
    sequence: int = Field(ge=0)
    initiative_ids: tuple[str, ...] = ()
    initiatives: tuple[RoadmapReportInitiativeView, ...] = ()

    @field_validator("phase_id", "phase", "title", "objective", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap report phase field")

    @field_validator("initiative_ids", "initiatives", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RoadmapReportSection(BaseModel):
    """Presentation model for assessment.roadmap (additive under schema 1.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = ROADMAP_REPORT_SECTION_ID
    section_version: str = ROADMAP_REPORT_SECTION_VERSION
    schema_name: str = "modernization-roadmap"
    engine_version: str
    status: str
    status_label: str
    summary: str
    phases: tuple[RoadmapReportPhaseView, ...] = ()
    initiatives: tuple[RoadmapReportInitiativeView, ...] = ()
    initiatives_total: int = Field(default=0, ge=0)
    initiatives_displayed: int = Field(default=0, ge=0)
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "section_version",
        "schema_name",
        "engine_version",
        "status",
        "status_label",
        "summary",
        "confidence",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap report section field")

    @field_validator(
        "phases",
        "initiatives",
        "assumptions",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
