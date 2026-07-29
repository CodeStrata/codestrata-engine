"""Immutable AI recommendation contract models."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.ai.recommendations.enums import (
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
)

AI_RECOMMENDATION_SCHEMA_VERSION = "1.0.0"
AI_RECOMMENDATION_ID_PATTERN = re.compile(r"^AI-REC-\d{3}$")


def _sorted_unique_strings(values: list[str], *, label: str) -> list[str]:
    cleaned: list[str] = []
    for item in values:
        compact = item.strip()
        if not compact:
            raise ValueError(f"{label} must not contain blank values")
        cleaned.append(compact)
    return sorted(dict.fromkeys(cleaned), key=str.lower)


def _unique_strings_preserve_order(values: list[str], *, label: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        compact = item.strip()
        if not compact:
            raise ValueError(f"{label} must not contain blank values")
        if compact in seen:
            continue
        seen.add(compact)
        cleaned.append(compact)
    return cleaned


class EvidenceCoverage(BaseModel):
    """How completely the recommendations cover analyzed findings.

    Numeric fields are owned by CodeStrata. Model-supplied values may be accepted as
    untrusted schema placeholders and are overwritten after validation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_findings: int = Field(ge=0)
    findings_considered: int = Field(ge=0)
    findings_referenced: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0.0, le=100.0)
    input_truncated: bool = False


class AIRecommendation(BaseModel):
    """A single provider-neutral modernization recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    priority: AIRecommendationPriority
    effort: AIRecommendationEffort
    impact: AIRecommendationImpact
    confidence: AIRecommendationConfidence
    related_finding_ids: list[str] = Field(default_factory=list)
    related_deterministic_recommendation_ids: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    @field_validator("recommendation_id")
    @classmethod
    def validate_recommendation_id(cls, value: str) -> str:
        compact = value.strip()
        if not compact:
            raise ValueError("recommendation_id must be a nonempty string")
        if not AI_RECOMMENDATION_ID_PATTERN.fullmatch(compact):
            raise ValueError(
                "recommendation_id must match AI-REC-NNN "
                "(for example AI-REC-001); PMD rule IDs and deterministic "
                "recommendation IDs are not valid AI recommendation IDs"
            )
        return compact

    @field_validator(
        "related_finding_ids",
        "suggested_actions",
        "dependencies",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return _sorted_unique_strings([str(item) for item in value], label="list")

    @field_validator("related_deterministic_recommendation_ids", mode="before")
    @classmethod
    def normalize_deterministic_recommendation_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return _unique_strings_preserve_order(
            [str(item) for item in value],
            label="related_deterministic_recommendation_ids",
        )


class ModernizationPhase(BaseModel):
    """An ordered phase grouping recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: int = Field(ge=1)
    name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)

    @field_validator("recommendations", "expected_outcomes", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return _sorted_unique_strings([str(item) for item in value], label="list")


class AIRecommendationResult(BaseModel):
    """Provider-neutral AI recommendation contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = AI_RECOMMENDATION_SCHEMA_VERSION
    executive_summary: str = Field(min_length=1)
    overall_assessment: str = Field(min_length=1)
    key_risks: list[str] = Field(default_factory=list)
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    modernization_phases: list[ModernizationPhase] = Field(default_factory=list)
    evidence_coverage: EvidenceCoverage
    limitations: list[str] = Field(default_factory=list)

    @field_validator("key_risks", "limitations", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return _sorted_unique_strings([str(item) for item in value], label="list")

    @field_validator("recommendations", mode="before")
    @classmethod
    def sort_recommendations(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return sorted(
            value,
            key=lambda item: (
                item.get("recommendation_id", "")
                if isinstance(item, dict)
                else getattr(item, "recommendation_id", "")
            ).lower(),
        )

    @field_validator("modernization_phases", mode="before")
    @classmethod
    def sort_phases(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return sorted(
            value,
            key=lambda item: (
                item.get("phase", 0) if isinstance(item, dict) else getattr(item, "phase", 0)
            ),
        )

    @model_validator(mode="after")
    def validate_result_integrity(self) -> AIRecommendationResult:
        recommendation_ids = [item.recommendation_id for item in self.recommendations]
        if len(recommendation_ids) != len(set(recommendation_ids)):
            raise ValueError("recommendation_id values must be unique")

        if recommendation_ids:
            expected_ids = [
                f"AI-REC-{index:03d}" for index in range(1, len(recommendation_ids) + 1)
            ]
            if sorted(recommendation_ids) != expected_ids:
                raise ValueError(
                    "recommendation_id values must be sequential "
                    f"AI-REC-001 through AI-REC-{len(recommendation_ids):03d}"
                )

        phase_numbers = [item.phase for item in self.modernization_phases]
        if len(phase_numbers) != len(set(phase_numbers)):
            raise ValueError("modernization phase numbers must be unique")
        if phase_numbers != sorted(phase_numbers):
            raise ValueError("modernization phases must be ordered by phase number")

        known_ids = set(recommendation_ids)
        for recommendation in self.recommendations:
            unknown_dependencies = sorted(set(recommendation.dependencies) - known_ids)
            if unknown_dependencies:
                raise ValueError(
                    "recommendation dependencies reference unknown recommendation IDs: "
                    + ", ".join(unknown_dependencies)
                )

        assigned: list[str] = []
        for phase in self.modernization_phases:
            if not phase.recommendations:
                raise ValueError(f"modernization phase {phase.phase} must not be empty")
            unknown = sorted(set(phase.recommendations) - known_ids)
            if unknown:
                raise ValueError(
                    "modernization phases reference unknown recommendation IDs: "
                    + ", ".join(unknown)
                )
            assigned.extend(phase.recommendations)

        if self.modernization_phases:
            if len(assigned) != len(set(assigned)):
                raise ValueError(
                    "each AI recommendation may appear in at most one modernization phase"
                )
            missing = sorted(known_ids - set(assigned))
            if missing:
                raise ValueError(
                    "modernization phases omit recommendation IDs: " + ", ".join(missing)
                )

        if self.schema_version != AI_RECOMMENDATION_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {AI_RECOMMENDATION_SCHEMA_VERSION}")

        return self

    def model_dump_json_ready(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary using mode='json'."""

        return self.model_dump(mode="json")
