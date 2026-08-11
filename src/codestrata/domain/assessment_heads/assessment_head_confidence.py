"""Assessment-Head Confidence — support strength for one head (Slice 5.4).

Assessment-Head Confidence is independent of severity, repository health,
Finding Confidence (though bounded by it), and coverage (though capped by it).
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class AssessmentHeadConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class AssessmentHeadConfidenceBasis(StrEnum):
    ALL_MATERIAL_FINDINGS_HIGH = "all_material_findings_high"
    MIXED_FINDING_CONFIDENCE = "mixed_finding_confidence"
    LIMITED_FINDING_CONFIDENCE = "limited_finding_confidence"
    NO_FINDINGS_WITH_COMPLETE_COVERAGE = "no_findings_with_complete_coverage"
    NO_FINDINGS_WITH_PARTIAL_COVERAGE = "no_findings_with_partial_coverage"
    COMPLETE_ASSESSMENT_COVERAGE = "complete_assessment_coverage"
    PARTIAL_ASSESSMENT_COVERAGE = "partial_assessment_coverage"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    LEGACY_FINDINGS = "legacy_findings"
    SYNTHESIZED_HEAD = "synthesized_head"
    DISABLED_HEAD = "disabled_head"
    UNAVAILABLE_HEAD = "unavailable_head"


class AssessmentHeadConfidenceDerivationStatus(StrEnum):
    DERIVED = "derived"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


_LEVEL_RANK: dict[AssessmentHeadConfidenceLevel, int] = {
    AssessmentHeadConfidenceLevel.UNAVAILABLE: 0,
    AssessmentHeadConfidenceLevel.LIMITED: 1,
    AssessmentHeadConfidenceLevel.MODERATE: 2,
    AssessmentHeadConfidenceLevel.HIGH: 3,
}


def assessment_head_confidence_level_rank(
    level: AssessmentHeadConfidenceLevel,
) -> int:
    return _LEVEL_RANK[level]


def min_assessment_head_confidence_level(
    levels: tuple[AssessmentHeadConfidenceLevel, ...],
) -> AssessmentHeadConfidenceLevel:
    if not levels:
        return AssessmentHeadConfidenceLevel.UNAVAILABLE
    return min(levels, key=assessment_head_confidence_level_rank)


class AssessmentHeadConfidenceComponents(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_count: int = Field(default=0, ge=0)
    high_finding_count: int = Field(default=0, ge=0)
    moderate_finding_count: int = Field(default=0, ge=0)
    limited_finding_count: int = Field(default=0, ge=0)
    unavailable_finding_count: int = Field(default=0, ge=0)
    weakest_material_finding_confidence: str | None = None
    coverage_state: str | None = None
    evidence_completeness: str | None = None
    assessment_status: str | None = None
    activated: bool = False
    limitations_count: int = Field(default=0, ge=0)

    @field_validator(
        "weakest_material_finding_confidence",
        "coverage_state",
        "evidence_completeness",
        "assessment_status",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class AssessmentHeadConfidence(BaseModel):
    """Canonical assessment-head support reliability contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: AssessmentHeadConfidenceLevel
    basis: tuple[AssessmentHeadConfidenceBasis, ...]
    limitations: tuple[str, ...] = ()
    derivation_status: AssessmentHeadConfidenceDerivationStatus
    component_summary: AssessmentHeadConfidenceComponents = Field(
        default_factory=AssessmentHeadConfidenceComponents
    )

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(
        cls, value: object
    ) -> tuple[AssessmentHeadConfidenceBasis, ...]:
        basis = tuple(AssessmentHeadConfidenceBasis(item) for item in as_tuple(value))
        if not basis:
            raise ValueError("basis must contain at least one confidence basis")
        return tuple(sorted(set(basis), key=lambda item: item.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="assessment head confidence limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_policy(self) -> AssessmentHeadConfidence:
        if AssessmentHeadConfidenceBasis.DISABLED_HEAD in self.basis:
            if self.level is not AssessmentHeadConfidenceLevel.UNAVAILABLE:
                raise ValueError("disabled_head must be UNAVAILABLE")
        if (
            self.level is AssessmentHeadConfidenceLevel.HIGH
            and AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE in self.basis
        ):
            raise ValueError("partial coverage cannot produce HIGH head confidence")
        if (
            self.level is AssessmentHeadConfidenceLevel.HIGH
            and AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE in self.basis
        ):
            raise ValueError("insufficient evidence cannot produce HIGH head confidence")
        if (
            self.level is AssessmentHeadConfidenceLevel.HIGH
            and AssessmentHeadConfidenceBasis.LEGACY_FINDINGS in self.basis
        ):
            raise ValueError("legacy findings cannot produce HIGH head confidence")
        if (
            self.level is AssessmentHeadConfidenceLevel.HIGH
            and AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_COMPLETE_COVERAGE
            in self.basis
        ):
            raise ValueError("zero findings cannot produce HIGH head confidence")
        return self

    @classmethod
    def unavailable(
        cls,
        *,
        limitations: tuple[str, ...] = (
            "Assessment-head confidence could not be derived.",
        ),
        basis: tuple[AssessmentHeadConfidenceBasis, ...] = (
            AssessmentHeadConfidenceBasis.UNAVAILABLE_HEAD,
        ),
        component_summary: AssessmentHeadConfidenceComponents | None = None,
    ) -> AssessmentHeadConfidence:
        return cls(
            level=AssessmentHeadConfidenceLevel.UNAVAILABLE,
            basis=basis,
            limitations=limitations,
            derivation_status=AssessmentHeadConfidenceDerivationStatus.UNAVAILABLE,
            component_summary=component_summary or AssessmentHeadConfidenceComponents(),
        )


def assessment_head_confidence_to_json(
    confidence: AssessmentHeadConfidence,
) -> dict[str, Any]:
    payload = confidence.model_dump(mode="json")
    return json.loads(json.dumps(payload, sort_keys=True))
