"""Modernization roadmap domain models (Phase 5.10)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.roadmap.enums import (
    RoadmapConfidence,
    RoadmapEffort,
    RoadmapPhaseName,
    RoadmapPriority,
    RoadmapRisk,
    RoadmapStatus,
)
from codestrata.domain.roadmap.identifiers import (
    ENGINE_VERSION,
    ROADMAP_SCHEMA_NAME,
    ROADMAP_SECTION_ID,
    ROADMAP_SECTION_VERSION,
)


class RoadmapEvidenceReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional roadmap evidence field")


class RoadmapInitiative(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    initiative_id: str
    title: str
    summary: str
    phase: RoadmapPhaseName
    priority: RoadmapPriority
    effort: RoadmapEffort
    risk: RoadmapRisk
    expected_outcome: str
    depends_on_initiative_ids: tuple[str, ...] = ()
    supporting_finding_ids: tuple[str, ...] = ()
    supporting_recommendation_ids: tuple[str, ...] = ()
    evidence_references: tuple[RoadmapEvidenceReference, ...] = ()
    confidence: RoadmapConfidence = RoadmapConfidence.MEDIUM
    category: str = "unknown"
    sequence: int = Field(default=0, ge=0)

    @field_validator(
        "initiative_id",
        "title",
        "summary",
        "expected_outcome",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap initiative field")

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


class RoadmapPhasePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_id: str
    phase: RoadmapPhaseName
    title: str
    objective: str
    sequence: int = Field(ge=0)
    initiative_ids: tuple[str, ...] = ()

    @field_validator("phase_id", "title", "objective", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap phase field")

    @field_validator("initiative_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item) for item in as_tuple(value))


class RoadmapAssessmentSection(BaseModel):
    """Deterministic modernization roadmap derived from existing findings/recs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = ROADMAP_SECTION_ID
    section_version: str = ROADMAP_SECTION_VERSION
    schema_name: str = ROADMAP_SCHEMA_NAME
    engine_version: str = ENGINE_VERSION
    status: RoadmapStatus = RoadmapStatus.SUCCEEDED
    summary: str
    phases: tuple[RoadmapPhasePlan, ...] = ()
    initiatives: tuple[RoadmapInitiative, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: RoadmapConfidence = RoadmapConfidence.MEDIUM
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("section_id", "section_version", "schema_name", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap section field")

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

    @classmethod
    def empty(
        cls,
        *,
        status: RoadmapStatus = RoadmapStatus.EMPTY,
        summary: str = "No modernization initiatives could be derived.",
        limitations: Sequence[str] = (),
    ) -> RoadmapAssessmentSection:
        return cls(
            status=status,
            summary=summary,
            phases=(),
            initiatives=(),
            assumptions=(
                "Roadmap initiatives are derived only from existing assessment "
                "findings and recommendations.",
            ),
            limitations=tuple(limitations)
            or (
                "No findings or recommendations were available for roadmap generation.",
            ),
            confidence=RoadmapConfidence.NONE,
            metadata={"initiative_count": "0", "phase_count": "0"},
        )
