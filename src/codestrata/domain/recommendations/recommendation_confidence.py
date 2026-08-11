"""Recommendation Confidence — support strength for one Recommendation (Slice 5.5).

Recommendation Confidence is independent of priority, severity, effort, and
Assessment-Head Confidence. It is derived from supporting Finding Confidence
via the weakest-support principle.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class RecommendationConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class RecommendationConfidenceBasis(StrEnum):
    ALL_SUPPORTING_FINDINGS_HIGH = "all_supporting_findings_high"
    MIXED_FINDING_CONFIDENCE = "mixed_finding_confidence"
    LIMITED_SUPPORTING_FINDING = "limited_supporting_finding"
    UNAVAILABLE_SUPPORTING_FINDING = "unavailable_supporting_finding"
    SINGLE_SUPPORTING_FINDING = "single_supporting_finding"
    MULTIPLE_CONSISTENT_FINDINGS = "multiple_consistent_findings"
    COMPLETE_FINDING_TRACEABILITY = "complete_finding_traceability"
    PARTIAL_FINDING_TRACEABILITY = "partial_finding_traceability"
    MERGED_RECOMMENDATION = "merged_recommendation"
    FACT_BASED_RECOMMENDATION = "fact_based_recommendation"
    LEGACY_RECOMMENDATION = "legacy_recommendation"
    MISSING_SUPPORTING_FINDINGS = "missing_supporting_findings"
    CROSS_HEAD_SUPPORT = "cross_head_support"
    SYNTHESIZED_ACTION = "synthesized_action"


class RecommendationConfidenceDerivationStatus(StrEnum):
    DERIVED = "derived"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


_LEVEL_RANK: dict[RecommendationConfidenceLevel, int] = {
    RecommendationConfidenceLevel.UNAVAILABLE: 0,
    RecommendationConfidenceLevel.LIMITED: 1,
    RecommendationConfidenceLevel.MODERATE: 2,
    RecommendationConfidenceLevel.HIGH: 3,
}


def recommendation_confidence_level_rank(
    level: RecommendationConfidenceLevel,
) -> int:
    return _LEVEL_RANK[level]


def min_recommendation_confidence_level(
    levels: tuple[RecommendationConfidenceLevel, ...],
) -> RecommendationConfidenceLevel:
    if not levels:
        return RecommendationConfidenceLevel.UNAVAILABLE
    return min(levels, key=recommendation_confidence_level_rank)


class RecommendationConfidenceComponents(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    supporting_finding_count: int = Field(default=0, ge=0)
    high_finding_count: int = Field(default=0, ge=0)
    moderate_finding_count: int = Field(default=0, ge=0)
    limited_finding_count: int = Field(default=0, ge=0)
    unavailable_finding_count: int = Field(default=0, ge=0)
    weakest_supporting_finding_confidence: str | None = None
    primary_finding_confidence: str | None = None
    evidence_completeness: str | None = None
    traceability_complete: bool = False
    recommendation_type: str | None = None
    assessment_head_count: int = Field(default=0, ge=0)
    limitations_count: int = Field(default=0, ge=0)

    @field_validator(
        "weakest_supporting_finding_confidence",
        "primary_finding_confidence",
        "evidence_completeness",
        "recommendation_type",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RecommendationConfidence(BaseModel):
    """Canonical recommendation-support reliability contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: RecommendationConfidenceLevel
    basis: tuple[RecommendationConfidenceBasis, ...]
    limitations: tuple[str, ...] = ()
    derivation_status: RecommendationConfidenceDerivationStatus
    component_summary: RecommendationConfidenceComponents = Field(
        default_factory=RecommendationConfidenceComponents
    )

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(
        cls, value: object
    ) -> tuple[RecommendationConfidenceBasis, ...]:
        basis = tuple(RecommendationConfidenceBasis(item) for item in as_tuple(value))
        if not basis:
            raise ValueError("basis must contain at least one confidence basis")
        return tuple(sorted(set(basis), key=lambda item: item.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(
                        str(item), label="recommendation confidence limitation"
                    )
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_policy(self) -> RecommendationConfidence:
        if RecommendationConfidenceBasis.LEGACY_RECOMMENDATION in self.basis:
            if self.level is not RecommendationConfidenceLevel.UNAVAILABLE:
                raise ValueError("legacy_recommendation must be UNAVAILABLE")
            if (
                self.derivation_status
                is not RecommendationConfidenceDerivationStatus.UNAVAILABLE
            ):
                raise ValueError(
                    "legacy_recommendation requires unavailable derivation_status"
                )
        if RecommendationConfidenceBasis.MISSING_SUPPORTING_FINDINGS in self.basis:
            if self.level is not RecommendationConfidenceLevel.UNAVAILABLE:
                raise ValueError("missing_supporting_findings must be UNAVAILABLE")
        if (
            self.level is RecommendationConfidenceLevel.HIGH
            and not self.component_summary.traceability_complete
        ):
            raise ValueError(
                "HIGH recommendation confidence requires complete finding traceability"
            )
        if (
            self.level is RecommendationConfidenceLevel.HIGH
            and RecommendationConfidenceBasis.PARTIAL_FINDING_TRACEABILITY in self.basis
        ):
            raise ValueError(
                "partial_finding_traceability cannot produce HIGH recommendation confidence"
            )
        if (
            self.level is RecommendationConfidenceLevel.HIGH
            and RecommendationConfidenceBasis.UNAVAILABLE_SUPPORTING_FINDING in self.basis
        ):
            raise ValueError(
                "unavailable_supporting_finding cannot produce HIGH recommendation confidence"
            )
        if (
            self.level
            in {
                RecommendationConfidenceLevel.HIGH,
                RecommendationConfidenceLevel.MODERATE,
            }
            and RecommendationConfidenceBasis.UNAVAILABLE_SUPPORTING_FINDING in self.basis
        ):
            raise ValueError(
                "unavailable_supporting_finding cannot produce High or Moderate "
                "recommendation confidence"
            )
        return self

    @classmethod
    def unavailable(
        cls,
        *,
        limitations: tuple[str, ...] = (
            "Recommendation confidence could not be derived.",
        ),
        basis: tuple[RecommendationConfidenceBasis, ...] = (
            RecommendationConfidenceBasis.LEGACY_RECOMMENDATION,
        ),
        component_summary: RecommendationConfidenceComponents | None = None,
    ) -> RecommendationConfidence:
        return cls(
            level=RecommendationConfidenceLevel.UNAVAILABLE,
            basis=basis,
            limitations=limitations,
            derivation_status=RecommendationConfidenceDerivationStatus.UNAVAILABLE,
            component_summary=component_summary or RecommendationConfidenceComponents(),
        )


def recommendation_confidence_to_json(
    confidence: RecommendationConfidence,
) -> dict[str, Any]:
    payload = confidence.model_dump(mode="json")
    return json.loads(json.dumps(payload, sort_keys=True))
