"""Immutable Phase 3 recommendation models produced by the Recommendation Engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.recommendations.enums import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationSource,
)
from codestrata.domain.recommendations.ids import build_recommendation_id

RECOMMENDATION_RESULT_VERSION = "1.0.0"


class RecommendationEvidence(BaseModel):
    """Explainable evidence supporting a recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None
    node_id: NodeId | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional recommendation evidence field")


class RecommendationAction(BaseModel):
    """One ordered, actionable step within a recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int = Field(ge=1)
    title: str
    description: str
    command: str | None = None
    documentation_ref: str | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation action field")

    @field_validator("command", "documentation_ref", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional recommendation action field")


class Recommendation(BaseModel):
    """One deterministic modernization recommendation derived from findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    summary: str
    rationale: str
    priority: RecommendationPriority
    category: RecommendationCategory
    source: RecommendationSource = RecommendationSource.FINDING_RULE
    related_finding_ids: tuple[str, ...] = ()
    affected_node_ids: tuple[NodeId, ...] = ()
    evidence: tuple[RecommendationEvidence, ...] = ()
    actions: tuple[RecommendationAction, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider_id: str

    @field_validator(
        "id",
        "title",
        "summary",
        "rationale",
        "provider_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation field")

    @field_validator(
        "related_finding_ids",
        "affected_node_ids",
        "evidence",
        "actions",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("related_finding_ids", mode="after")
    @classmethod
    def sort_finding_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({require_nonblank(item, label="finding_id") for item in value}))

    @field_validator("actions", mode="after")
    @classmethod
    def sort_actions(
        cls, value: tuple[RecommendationAction, ...]
    ) -> tuple[RecommendationAction, ...]:
        return tuple(sorted(value, key=lambda item: (item.order, item.title)))

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @classmethod
    def create(
        cls,
        *,
        provider_id: str,
        title: str,
        summary: str,
        rationale: str,
        priority: RecommendationPriority,
        category: RecommendationCategory,
        related_finding_ids: Sequence[str],
        actions: Sequence[RecommendationAction],
        evidence: Sequence[RecommendationEvidence] = (),
        affected_node_ids: Sequence[NodeId] = (),
        metadata: Mapping[str, Any] | None = None,
        subject_keys: Sequence[str] = (),
    ) -> Recommendation:
        """Construct a recommendation with a deterministic identity."""

        finding_ids = tuple(related_finding_ids)
        return cls(
            id=build_recommendation_id(
                provider_id=provider_id,
                related_finding_ids=finding_ids,
                subject_keys=subject_keys,
            ),
            title=title,
            summary=summary,
            rationale=rationale,
            priority=priority,
            category=category,
            source=RecommendationSource.FINDING_RULE,
            related_finding_ids=finding_ids,
            affected_node_ids=tuple(affected_node_ids),
            evidence=tuple(evidence),
            actions=tuple(actions),
            metadata=dict(metadata or {}),
            provider_id=provider_id,
        )


class RecommendationResult(BaseModel):
    """Aggregated deterministic output of one Recommendation Engine execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = RECOMMENDATION_RESULT_VERSION
    recommendations: tuple[Recommendation, ...] = ()
    providers_evaluated: tuple[str, ...] = ()
    providers_skipped: tuple[str, ...] = ()
    recommendation_count: int = Field(ge=0)
    unmatched_finding_ids: tuple[str, ...] = ()

    @field_validator(
        "recommendations",
        "providers_evaluated",
        "providers_skipped",
        "unmatched_finding_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @classmethod
    def from_recommendations(
        cls,
        *,
        recommendations: Sequence[Recommendation],
        providers_evaluated: Sequence[str],
        providers_skipped: Sequence[str] = (),
        unmatched_finding_ids: Sequence[str] = (),
    ) -> RecommendationResult:
        priority_rank = {
            RecommendationPriority.IMMEDIATE: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        ordered = tuple(
            sorted(
                recommendations,
                key=lambda item: (
                    priority_rank.get(item.priority, 99),
                    item.category.value,
                    item.id,
                    item.title,
                ),
            )
        )
        evaluated = tuple(
            sorted({require_nonblank(item, label="provider_id") for item in providers_evaluated})
        )
        skipped = tuple(
            sorted({require_nonblank(item, label="provider_id") for item in providers_skipped})
        )
        unmatched = tuple(
            sorted({require_nonblank(item, label="finding_id") for item in unmatched_finding_ids})
        )
        return cls(
            recommendations=ordered,
            providers_evaluated=evaluated,
            providers_skipped=skipped,
            recommendation_count=len(ordered),
            unmatched_finding_ids=unmatched,
        )
