"""Recommendation priority calibration contracts (Epic 5 Slice 5.14).

Priority answers which recommended actions should be addressed earlier.
It is not Finding Severity, Recommendation Confidence, ROI, or AI judgment.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.recommendations.enums import RecommendationPriority
from codestrata.domain.traceability.validators import normalize_limitations

# Ordering utility only — not probability, ROI, or business impact.
PRIORITY_SCORE_MIN = 0
PRIORITY_SCORE_MAX = 100

# Bands map calibrated score → RecommendationPriority (immediate ≈ critical).
BAND_IMMEDIATE_MIN = 90
BAND_HIGH_MIN = 70
BAND_MEDIUM_MIN = 40


class RecommendationPriorityBasis(StrEnum):
    CALIBRATED_FINDING_SEVERITY = "calibrated_finding_severity"
    FINDING_CONFIDENCE = "finding_confidence"
    RECOMMENDATION_CONFIDENCE = "recommendation_confidence"
    DIRECT_SECURITY_EXPOSURE = "direct_security_exposure"
    DETERMINISTIC_SCOPE = "deterministic_scope"
    AFFECTED_SUBJECT_COUNT = "affected_subject_count"
    CORRELATED_SUPPORTING_FINDINGS = "correlated_supporting_findings"
    REMEDIATION_DEPENDENCY = "remediation_dependency"
    STABILIZATION_PREREQUISITE = "stabilization_prerequisite"
    EVIDENCE_COMPLETENESS = "evidence_completeness"
    PRODUCTION_CONTEXT = "production_context"
    STATIC_ONLY_LIMITATION = "static_only_limitation"
    LEGACY_RECOMMENDATION = "legacy_recommendation"
    PROVIDER_DEFAULT = "provider_default"
    EXPLICIT_POLICY = "explicit_policy"
    CONFIDENCE_CAP = "confidence_cap"
    CONTEXT_CAP = "context_cap"


class PriorityCalibrationStatus(StrEnum):
    CALIBRATED = "calibrated"
    PROVISIONAL = "provisional"
    LEGACY = "legacy"
    UNAVAILABLE = "unavailable"


class RecommendationPriorityComponents(BaseModel):
    """Explainable priority component snapshot (no probabilities)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supporting_finding_count: int = Field(default=0, ge=0)
    highest_finding_severity: str | None = None
    weakest_finding_confidence: str | None = None
    recommendation_confidence: str | None = None
    evidence_completeness: str | None = None
    affected_subject_count: int | None = Field(default=None, ge=0)
    assessment_head_count: int = Field(default=0, ge=0)
    correlation_count: int = Field(default=0, ge=0)
    effort: str | None = None
    base_score: int = Field(default=0, ge=PRIORITY_SCORE_MIN, le=PRIORITY_SCORE_MAX)
    calibrated_score: int = Field(default=0, ge=PRIORITY_SCORE_MIN, le=PRIORITY_SCORE_MAX)
    priority: RecommendationPriority | None = None
    limitations_count: int = Field(default=0, ge=0)


class RecommendationPriorityAssessment(BaseModel):
    """Canonical Recommendation priority calibration result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    priority: RecommendationPriority
    score: int = Field(ge=PRIORITY_SCORE_MIN, le=PRIORITY_SCORE_MAX)
    basis: tuple[RecommendationPriorityBasis, ...] = ()
    calibration_status: PriorityCalibrationStatus = PriorityCalibrationStatus.CALIBRATED
    limitations: tuple[str, ...] = ()
    component_summary: RecommendationPriorityComponents = Field(
        default_factory=RecommendationPriorityComponents
    )
    policy_id: str | None = None

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[Any, ...]:
        seen: set[str] = set()
        out: list[Any] = []
        for item in as_tuple(value):
            key = getattr(item, "value", str(item))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return tuple(out)

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("policy_id", mode="before")
    @classmethod
    def normalize_policy(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_assessment(self) -> RecommendationPriorityAssessment:
        expected = priority_for_score(self.score)
        if self.priority is not expected:
            raise ValueError(
                f"priority {self.priority.value} inconsistent with score {self.score} "
                f"(expected {expected.value})"
            )
        if (
            self.calibration_status is PriorityCalibrationStatus.CALIBRATED
            and not self.basis
        ):
            raise ValueError("calibrated priority assessment requires at least one basis")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def legacy(
        cls,
        *,
        priority: RecommendationPriority,
        score: int | None = None,
        limitations: tuple[str, ...] = (),
    ) -> RecommendationPriorityAssessment:
        bounded = clamp_score(score if score is not None else score_for_priority(priority))
        # Legacy never Critical/Immediate.
        if bounded >= BAND_IMMEDIATE_MIN:
            bounded = BAND_HIGH_MIN + 5
        priority = priority_for_score(bounded)
        return cls(
            priority=priority,
            score=bounded,
            basis=(RecommendationPriorityBasis.LEGACY_RECOMMENDATION,),
            calibration_status=PriorityCalibrationStatus.LEGACY,
            limitations=limitations
            or ("Legacy Recommendation; priority bounded conservatively.",),
            component_summary=RecommendationPriorityComponents(
                base_score=bounded,
                calibrated_score=bounded,
                priority=priority,
                limitations_count=1,
            ),
            policy_id="priority.legacy.compatibility",
        )


def clamp_score(score: int | float) -> int:
    value = int(round(float(score)))
    return max(PRIORITY_SCORE_MIN, min(PRIORITY_SCORE_MAX, value))


def priority_for_score(score: int) -> RecommendationPriority:
    if score >= BAND_IMMEDIATE_MIN:
        return RecommendationPriority.IMMEDIATE
    if score >= BAND_HIGH_MIN:
        return RecommendationPriority.HIGH
    if score >= BAND_MEDIUM_MIN:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW


def score_for_priority(priority: RecommendationPriority) -> int:
    if priority is RecommendationPriority.IMMEDIATE:
        return 95
    if priority is RecommendationPriority.HIGH:
        return 80
    if priority is RecommendationPriority.MEDIUM:
        return 55
    return 25


def require_priority(value: object) -> RecommendationPriority:
    text = require_nonblank(str(value), label="priority").strip().lower()
    if text == "critical":
        return RecommendationPriority.IMMEDIATE
    return RecommendationPriority(text)
