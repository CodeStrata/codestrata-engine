"""Modernization roadmap domain models (Phase 5.10)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.roadmap.enums import (
    RoadmapConfidence,
    RoadmapEffort,
    RoadmapInitiativeType,
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
from codestrata.domain.traceability import EvidenceCompleteness, TraceabilityValidationError
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids


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
    # Additive Epic 2 Slice 2.5 — Priority Action → Roadmap traceability.
    # Not part of initiative ID material (build_initiative_id uses phase/category/recs).
    supporting_priority_action_ids: tuple[str, ...] = ()
    primary_priority_action_id: str | None = None
    initiative_type: RoadmapInitiativeType = RoadmapInitiativeType.LEGACY
    evidence_completeness: EvidenceCompleteness = EvidenceCompleteness.LEGACY
    limitations: tuple[str, ...] = ()
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
        "supporting_priority_action_ids",
        "evidence_references",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator(
        "supporting_finding_ids",
        "supporting_recommendation_ids",
        "supporting_priority_action_ids",
        mode="after",
    )
    @classmethod
    def sort_traceability_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="roadmap_traceability_id")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("primary_priority_action_id", mode="before")
    @classmethod
    def normalize_primary(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="primary_priority_action_id")

    @model_validator(mode="after")
    def validate_traceability(self) -> RoadmapInitiative:
        supporting = self.supporting_priority_action_ids
        primary = self.primary_priority_action_id
        if primary is not None and primary not in supporting:
            raise TraceabilityValidationError(
                "primary_priority_action_id must reference a "
                "supporting_priority_action_ids entry"
            )
        if primary is None and len(supporting) == 1:
            primary = supporting[0]
        if (
            self.initiative_type is RoadmapInitiativeType.PRIORITY_ACTION_BACKED
            or self.initiative_type is RoadmapInitiativeType.MERGED
        ) and not supporting:
            raise TraceabilityValidationError(
                "priority-action-backed Roadmap Initiatives require "
                "supporting_priority_action_ids"
            )
        if primary != self.primary_priority_action_id:
            return self.model_copy(update={"primary_priority_action_id": primary})
        return self


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
    """Deterministic modernization roadmap derived from Priority Actions (Slice 2.5).

    Legacy recommendation-grouped generation may still emit sections marked with
    ``initiative_type=legacy`` for CLI compatibility; those are not the
    authoritative Priority Action–backed assessment roadmap.
    """

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
                "Roadmap initiatives are derived from Priority Actions backed by "
                "Recommendations and Findings.",
            ),
            limitations=tuple(limitations)
            or (
                "No Priority Actions were available for roadmap generation.",
            ),
            confidence=RoadmapConfidence.NONE,
            metadata={"initiative_count": "0", "phase_count": "0"},
        )
