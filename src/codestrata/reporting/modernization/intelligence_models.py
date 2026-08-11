"""Modernization Assessment Intelligence presentation models (Epic 3 Slice 3.9).

HTML/reporting-layer only. Synthesizes existing Findings → Recommendations →
Priority Actions → Roadmap Initiatives. Does not invent entities, sequencing,
effort, ROI, timelines, or modernization-ready claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

MODERNIZATION_INTELLIGENCE_SECTION_ID = "report.modernization_intelligence"
MODERNIZATION_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class ModernizationOverviewFact(BaseModel):
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


class ModernizationContributingHead(BaseModel):
    """Assessment head contribution summary — entities keep their original heads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    head_id: str
    title: str
    anchor: str
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    priority_action_count: int = Field(default=0, ge=0)

    @field_validator("head_id", "title", "anchor", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="contributing head field")


class ModernizationPriorityActionLink(BaseModel):
    """Compact Priority Action summary linking to the canonical PA detail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str
    title: str
    priority: str | None = None
    presentation_bucket: str | None = None
    effort: str | None = None
    supporting_recommendation_count: int = Field(default=0, ge=0)
    supporting_finding_count: int = Field(default=0, ge=0)
    evidence_completeness: str | None = None
    limitations: tuple[str, ...] = ()
    head_id: str | None = None
    head_title: str | None = None

    @field_validator("action_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="priority action link field")

    @field_validator(
        "priority",
        "presentation_bucket",
        "effort",
        "evidence_completeness",
        "head_id",
        "head_title",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="priority action optional field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ModernizationInitiativeLink(BaseModel):
    """Compact roadmap initiative summary linking to the canonical roadmap detail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initiative_id: str
    title: str
    sequence: int = Field(default=0, ge=0)
    priority: str | None = None
    effort: str | None = None
    supporting_priority_action_ids: tuple[str, ...] = ()
    depends_on_initiative_ids: tuple[str, ...] = ()
    evidence_completeness: str | None = None
    limitations: tuple[str, ...] = ()
    is_legacy: bool = False

    @field_validator("initiative_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="initiative link field")

    @field_validator(
        "priority",
        "effort",
        "evidence_completeness",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="initiative optional field")

    @field_validator(
        "supporting_priority_action_ids",
        "depends_on_initiative_ids",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ModernizationPhaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_id: str
    phase: str
    title: str
    sequence: int = Field(default=0, ge=0)
    initiative_count: int = Field(default=0, ge=0)
    initiatives: tuple[ModernizationInitiativeLink, ...] = ()
    has_legacy: bool = False

    @field_validator("phase_id", "phase", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="phase summary field")

    @field_validator("initiatives", mode="before")
    @classmethod
    def normalize_initiatives(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class ModernizationThemeSummary(BaseModel):
    """Bounded theme derived from assessment-head grouping — not free-form narrative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    head_id: str
    title: str
    anchor: str
    priority_action_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    top_titles: tuple[str, ...] = ()

    @field_validator("head_id", "title", "anchor", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme summary field")

    @field_validator("top_titles", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ModernizationCoverageRow(BaseModel):
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


class ModernizationIntelligenceSection(BaseModel):
    """Customer Modernization Assessment Intelligence section (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = MODERNIZATION_INTELLIGENCE_SECTION_ID
    section_version: str = MODERNIZATION_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[ModernizationOverviewFact, ...] = ()
    contributing_heads: tuple[ModernizationContributingHead, ...] = ()
    priority_actions: tuple[ModernizationPriorityActionLink, ...] = ()
    roadmap_phases: tuple[ModernizationPhaseSummary, ...] = ()
    themes: tuple[ModernizationThemeSummary, ...] = ()
    coverage_rows: tuple[ModernizationCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    supporting_finding_count: int = Field(default=0, ge=0)
    supporting_recommendation_count: int = Field(default=0, ge=0)
    priority_action_count: int = Field(default=0, ge=0)
    roadmap_initiative_count: int = Field(default=0, ge=0)
    empty_actions_message: str | None = None
    roadmap_is_legacy: bool = False
    uses_canonical_roadmap: bool = False

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
        return require_nonblank(str(value), label="modernization intelligence field")

    @field_validator(
        "overview_facts",
        "contributing_heads",
        "priority_actions",
        "roadmap_phases",
        "themes",
        "coverage_rows",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("empty_actions_message", mode="before")
    @classmethod
    def normalize_message(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="empty actions message")
