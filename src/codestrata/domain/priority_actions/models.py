"""Canonical Priority Action models (Epic 2 Slice 2.4).

Priority Actions are recommendation-backed. They must not invent Finding
relationships independently of referenced Recommendations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.priority_actions.enums import PriorityActionType
from codestrata.domain.priority_actions.ids import build_priority_action_id
from codestrata.domain.traceability import EvidenceCompleteness, TraceabilityValidationError
from codestrata.domain.traceability.validators import normalize_limitations, sorted_unique_ids


class PriorityAction(BaseModel):
    """One deterministic Priority Action derived from Recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: str
    title: str
    summary: str
    priority: str
    priority_score: float = 0.0
    effort: str = "unknown"
    presentation_bucket: str = "future"
    action_type: PriorityActionType = PriorityActionType.LEGACY
    supporting_recommendation_ids: tuple[str, ...] = ()
    primary_recommendation_id: str | None = None
    supporting_finding_ids: tuple[str, ...] = ()
    evidence_completeness: EvidenceCompleteness = EvidenceCompleteness.LEGACY
    limitations: tuple[str, ...] = ()
    # Presentation aids retained for HTML projection without redesign.
    category: str = "unknown"
    rationale: str = ""
    risk: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "action_id",
        "title",
        "summary",
        "priority",
        "effort",
        "presentation_bucket",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="priority action field")

    @field_validator("rationale", "risk", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text

    @field_validator(
        "supporting_recommendation_ids",
        "supporting_finding_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("supporting_recommendation_ids", "supporting_finding_ids", mode="after")
    @classmethod
    def sort_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="traceability_id")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("primary_recommendation_id", mode="before")
    @classmethod
    def normalize_primary(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="primary_recommendation_id")

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @model_validator(mode="after")
    def validate_traceability(self) -> PriorityAction:
        supporting = self.supporting_recommendation_ids
        primary = self.primary_recommendation_id
        if primary is not None and primary not in supporting:
            raise TraceabilityValidationError(
                "primary_recommendation_id must reference a "
                "supporting_recommendation_ids entry"
            )
        if primary is None and len(supporting) == 1:
            primary = supporting[0]
        if not supporting and self.action_type is PriorityActionType.RECOMMENDATION_BACKED:
            raise TraceabilityValidationError(
                "recommendation_backed Priority Actions require supporting_recommendation_ids"
            )
        updates: dict[str, Any] = {}
        if primary != self.primary_recommendation_id:
            updates["primary_recommendation_id"] = primary
        if updates:
            return self.model_copy(update=updates)
        return self

    @classmethod
    def create(
        cls,
        *,
        title: str,
        summary: str,
        priority: str,
        supporting_recommendation_ids: Sequence[str],
        supporting_finding_ids: Sequence[str] = (),
        primary_recommendation_id: str | None = None,
        priority_score: float = 0.0,
        effort: str = "unknown",
        presentation_bucket: str = "future",
        action_type: PriorityActionType | None = None,
        evidence_completeness: EvidenceCompleteness | None = None,
        limitations: Sequence[str] = (),
        category: str = "unknown",
        rationale: str = "",
        risk: str = "medium",
        metadata: Mapping[str, Any] | None = None,
    ) -> PriorityAction:
        """Construct a recommendation-backed Priority Action.

        ``action_id`` equals the primary recommendation ID for presentation
        compatibility. Completeness must be supplied by the application mapper
        from referenced Recommendations — callers should not invent it.
        """

        supporting_recs = sorted_unique_ids(
            supporting_recommendation_ids,
            label="recommendation_id",
        )
        if not supporting_recs:
            raise TraceabilityValidationError(
                "Priority Actions require at least one supporting recommendation"
            )
        primary = primary_recommendation_id or supporting_recs[0]
        if primary not in supporting_recs:
            raise TraceabilityValidationError(
                "primary_recommendation_id must reference a "
                "supporting_recommendation_ids entry"
            )
        if action_type is None:
            action_type = (
                PriorityActionType.MERGED
                if len(supporting_recs) > 1
                else PriorityActionType.RECOMMENDATION_BACKED
            )
        if evidence_completeness is None:
            evidence_completeness = (
                EvidenceCompleteness.COMPLETE
                if supporting_finding_ids
                else EvidenceCompleteness.PARTIAL
            )
        action_id = build_priority_action_id(
            primary_recommendation_id=primary,
            supporting_recommendation_ids=supporting_recs,
        )
        return cls(
            action_id=action_id,
            title=title,
            summary=summary,
            priority=priority,
            priority_score=priority_score,
            effort=effort,
            presentation_bucket=presentation_bucket,
            action_type=action_type,
            supporting_recommendation_ids=supporting_recs,
            primary_recommendation_id=primary,
            supporting_finding_ids=tuple(supporting_finding_ids),
            evidence_completeness=evidence_completeness,
            limitations=tuple(limitations),
            category=category,
            rationale=rationale,
            risk=risk,
            metadata=dict(metadata or {}),
        )
