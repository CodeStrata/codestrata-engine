"""Assessment Coverage — examined scope for one assessment head (Slice 5.6).

Assessment Coverage is independent of confidence, precision/recall, severity,
finding counts, and repository health. It describes what supported scope was
examined during one repository assessment.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"


class CoverageDerivationStatus(StrEnum):
    MEASURED = "measured"
    DERIVED = "derived"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


class AreaSupportState(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class AreaEvaluationState(StrEnum):
    EVALUATED = "evaluated"
    PARTIALLY_EVALUATED = "partially_evaluated"
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"


class AreaClaimState(StrEnum):
    """Denominator policy for declared methodology areas."""

    CLAIMED = "claimed"
    PARTIAL = "partial"
    NOT_CLAIMED = "not_claimed"


class CoverageMetricAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CoverageMetricId(StrEnum):
    AREA_COVERAGE = "assessment.area_coverage"
    CANDIDATE_PROCESSING = "assessment.candidate_processing"
    RULE_EXECUTION = "assessment.rule_execution"
    EVIDENCE_AVAILABILITY = "assessment.evidence_availability"


class AssessmentCoverageScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    head_id: str
    pack_id: str | None = None
    activated: bool = False
    support_summary: str | None = None

    @field_validator("head_id", mode="before")
    @classmethod
    def normalize_head(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage head_id")

    @field_validator("pack_id", "support_summary", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class AssessmentAreaCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    title: str
    claim_state: AreaClaimState = AreaClaimState.CLAIMED
    support_state: AreaSupportState
    evaluation_state: AreaEvaluationState
    evidence_available: bool | None = None
    candidate_count: int | None = Field(default=None, ge=0)
    processed_count: int | None = Field(default=None, ge=0)
    partial_count: int | None = Field(default=None, ge=0)
    failed_count: int | None = Field(default=None, ge=0)
    skipped_count: int | None = Field(default=None, ge=0)
    eligible_rule_count: int | None = Field(default=None, ge=0)
    executed_rule_count: int | None = Field(default=None, ge=0)
    limitations: tuple[str, ...] = ()

    @field_validator("area_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="coverage area limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_counts(self) -> AssessmentAreaCoverage:
        for left, right, label in (
            (self.processed_count, self.candidate_count, "processed_count"),
            (self.partial_count, self.candidate_count, "partial_count"),
            (self.failed_count, self.candidate_count, "failed_count"),
            (self.skipped_count, self.candidate_count, "skipped_count"),
            (self.executed_rule_count, self.eligible_rule_count, "executed_rule_count"),
        ):
            if left is not None and right is not None and left > right:
                raise ValueError(f"{label} cannot exceed its denominator")
        return self


class AssessmentCoverageTotals(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    declared_area_count: int = Field(default=0, ge=0)
    supported_area_count: int = Field(default=0, ge=0)
    partially_supported_area_count: int = Field(default=0, ge=0)
    unsupported_area_count: int = Field(default=0, ge=0)
    applicable_area_count: int = Field(default=0, ge=0)
    evaluated_area_count: int = Field(default=0, ge=0)
    partially_evaluated_area_count: int = Field(default=0, ge=0)
    unevaluated_area_count: int = Field(default=0, ge=0)
    candidate_count: int | None = Field(default=None, ge=0)
    inspected_candidate_count: int | None = Field(default=None, ge=0)
    successfully_processed_count: int | None = Field(default=None, ge=0)
    partially_processed_count: int | None = Field(default=None, ge=0)
    failed_count: int | None = Field(default=None, ge=0)
    skipped_count: int | None = Field(default=None, ge=0)
    eligible_rule_count: int | None = Field(default=None, ge=0)
    executed_rule_count: int | None = Field(default=None, ge=0)
    unavailable_rule_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_totals(self) -> AssessmentCoverageTotals:
        if self.evaluated_area_count > self.applicable_area_count:
            raise ValueError("evaluated_area_count cannot exceed applicable_area_count")
        if (
            self.evaluated_area_count + self.partially_evaluated_area_count
            > self.applicable_area_count
        ):
            raise ValueError("evaluated area totals cannot exceed applicable_area_count")
        for left, right, label in (
            (self.successfully_processed_count, self.candidate_count, "successfully_processed"),
            (self.partially_processed_count, self.candidate_count, "partially_processed"),
            (self.failed_count, self.candidate_count, "failed"),
            (self.skipped_count, self.candidate_count, "skipped"),
            (self.executed_rule_count, self.eligible_rule_count, "executed_rule"),
        ):
            if left is not None and right is not None and left > right:
                raise ValueError(f"{label} count cannot exceed denominator")
        return self


class CoverageMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: CoverageMetricId
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    ratio: Decimal | None = None
    availability: CoverageMetricAvailability
    limitations: tuple[str, ...] = ()

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="coverage metric limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @field_validator("ratio", mode="before")
    @classmethod
    def normalize_ratio(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("ratio must be a decimal") from exc

    @model_validator(mode="after")
    def validate_metric(self) -> CoverageMetric:
        if self.denominator == 0:
            if self.availability is not CoverageMetricAvailability.UNAVAILABLE:
                raise ValueError("zero denominator requires unavailable metric")
            if self.ratio is not None:
                raise ValueError("zero denominator cannot emit a ratio")
            return self
        if self.numerator > self.denominator:
            raise ValueError("numerator cannot exceed denominator")
        if self.availability is CoverageMetricAvailability.AVAILABLE:
            expected = (Decimal(self.numerator) / Decimal(self.denominator)).quantize(
                Decimal("0.0001")
            )
            if self.ratio is None:
                raise ValueError("available metric requires ratio")
            if self.ratio.quantize(Decimal("0.0001")) != expected:
                raise ValueError("ratio must reconcile with numerator/denominator")
        return self

    @classmethod
    def build(
        cls,
        *,
        metric_id: CoverageMetricId,
        numerator: int,
        denominator: int,
        limitations: tuple[str, ...] = (),
    ) -> CoverageMetric:
        if denominator <= 0:
            return cls(
                metric_id=metric_id,
                numerator=max(0, numerator),
                denominator=0,
                ratio=None,
                availability=CoverageMetricAvailability.UNAVAILABLE,
                limitations=limitations
                or ("Coverage metric denominator is zero.",),
            )
        ratio = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))
        return cls(
            metric_id=metric_id,
            numerator=numerator,
            denominator=denominator,
            ratio=ratio,
            availability=CoverageMetricAvailability.AVAILABLE,
            limitations=limitations,
        )


class AssessmentCoverage(BaseModel):
    """Canonical assessment-run coverage for one head."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: CoverageStatus
    scope: AssessmentCoverageScope
    areas: tuple[AssessmentAreaCoverage, ...] = ()
    totals: AssessmentCoverageTotals = Field(default_factory=AssessmentCoverageTotals)
    metrics: tuple[CoverageMetric, ...] = ()
    limitations: tuple[str, ...] = ()
    derivation_status: CoverageDerivationStatus

    @field_validator("areas", "metrics", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("areas", mode="after")
    @classmethod
    def sort_areas(
        cls, value: tuple[AssessmentAreaCoverage, ...]
    ) -> tuple[AssessmentAreaCoverage, ...]:
        return tuple(sorted(value, key=lambda item: item.area_id))

    @field_validator("metrics", mode="after")
    @classmethod
    def sort_metrics(cls, value: tuple[CoverageMetric, ...]) -> tuple[CoverageMetric, ...]:
        return tuple(sorted(value, key=lambda item: item.metric_id.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="assessment coverage limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @classmethod
    def unavailable(
        cls,
        *,
        head_id: str,
        pack_id: str | None = None,
        activated: bool = False,
        status: CoverageStatus = CoverageStatus.UNAVAILABLE,
        limitations: tuple[str, ...] = (
            "Assessment coverage could not be measured.",
        ),
    ) -> AssessmentCoverage:
        return cls(
            status=status,
            scope=AssessmentCoverageScope(
                head_id=head_id,
                pack_id=pack_id,
                activated=activated,
            ),
            areas=(),
            totals=AssessmentCoverageTotals(),
            metrics=(),
            limitations=limitations,
            derivation_status=CoverageDerivationStatus.UNAVAILABLE,
        )


def assessment_coverage_to_json(coverage: AssessmentCoverage) -> dict[str, Any]:
    payload = coverage.model_dump(mode="json")
    # Decimal → stable string.
    for metric in payload.get("metrics") or []:
        if isinstance(metric, dict) and metric.get("ratio") is not None:
            metric["ratio"] = format(Decimal(str(metric["ratio"])), "f")
    return json.loads(json.dumps(payload, sort_keys=True))


def coverage_status_to_confidence_coverage_state(status: CoverageStatus) -> str:
    """Map CoverageStatus onto Assessment-Head Confidence coverage_state tokens."""

    mapping = {
        CoverageStatus.COMPLETE: "complete",
        CoverageStatus.PARTIAL: "partial",
        CoverageStatus.INSUFFICIENT_EVIDENCE: "insufficient",
        CoverageStatus.UNAVAILABLE: "unavailable",
        CoverageStatus.DISABLED: "unavailable",
        CoverageStatus.NOT_APPLICABLE: "unsupported",
    }
    return mapping[status]
