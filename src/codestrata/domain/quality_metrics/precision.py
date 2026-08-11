"""Canonical Precision Metric (Epic 5 Slice 5.7).

Precision answers: of assessment outputs classified as positive within a defined
validation scope, what proportion were confirmed true positives?

    precision = true_positives / (true_positives + false_positives)

Precision is internal validation/calibration evidence — not confidence,
assessment coverage, recall, severity, priority, or a product-wide accuracy claim.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.quality_metrics.common import (
    QualityMetricAvailability,
    QualityMetricClassificationStatus,
    QualityMetricSample,
    QualityMetricScope,
    QualityMetricSource,
    as_decimal,
    build_quality_metric_id,
    dedupe_limitations,
    format_metric_display,
    normalize_scope_id,
    provisional_availability_for_denominator,
    resolve_quality_metric_source,
    source_from_matrix_label,
)

# Re-export shared primitives for existing importers.
__all__ = [
    "PrecisionMetric",
    "QualityMetricAvailability",
    "QualityMetricClassificationStatus",
    "QualityMetricSample",
    "QualityMetricScope",
    "QualityMetricSource",
    "aggregate_precision_from_counts",
    "build_precision_metric",
    "build_precision_metric_id",
    "format_precision_display",
    "normalize_scope_id",
    "precision_ratio_as_float",
    "precision_ratio_from_counts",
    "resolve_quality_metric_source",
    "source_from_matrix_label",
]


def build_precision_metric_id(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
) -> str:
    """Deterministic metric id: ``precision:{scope}:{scope_id}``."""

    return build_quality_metric_id(kind="precision", scope=scope, scope_id=scope_id)


def precision_ratio_from_counts(
    true_positive_count: int,
    false_positive_count: int,
) -> Decimal | None:
    """Return exact Decimal precision or ``None`` when TP+FP == 0.

    False negatives and ambiguous observations are intentionally ignored.
    """

    if true_positive_count < 0 or false_positive_count < 0:
        raise ValueError("TP and FP counts must be non-negative")
    denominator = true_positive_count + false_positive_count
    if denominator == 0:
        return None
    return Decimal(true_positive_count) / Decimal(denominator)


def precision_ratio_as_float(
    true_positive_count: int,
    false_positive_count: int,
) -> float | None:
    """Compatibility float projection for legacy pack/result fields."""

    value = precision_ratio_from_counts(true_positive_count, false_positive_count)
    return float(value) if value is not None else None


class PrecisionMetric(BaseModel):
    """Canonical precision metric derived only from TP and FP counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    scope: QualityMetricScope
    scope_id: str
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: Decimal | None = None
    availability: QualityMetricAvailability
    classification_status: QualityMetricClassificationStatus
    source: QualityMetricSource = QualityMetricSource.EXPECTED_ACTUAL_VALIDATION
    sample: QualityMetricSample = Field(default_factory=QualityMetricSample)
    limitations: tuple[str, ...] = ()

    @field_validator("metric_id", "scope_id", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="precision metric identity")

    @field_validator("value", mode="before")
    @classmethod
    def normalize_value(cls, value: object) -> Decimal | None:
        return as_decimal(value, label="precision value")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return dedupe_limitations(value, label="precision limitation")

    @model_validator(mode="after")
    def validate_metric(self) -> PrecisionMetric:
        expected_id = build_precision_metric_id(scope=self.scope, scope_id=self.scope_id)
        if self.metric_id != expected_id:
            raise ValueError(
                f"metric_id must be deterministic ({expected_id!r}), got {self.metric_id!r}"
            )
        if self.scope_id != normalize_scope_id(self.scope_id):
            raise ValueError("scope_id must be normalized")
        expected_denom = self.true_positive_count + self.false_positive_count
        if self.denominator != expected_denom:
            raise ValueError("denominator must equal true_positive_count + false_positive_count")

        if self.availability is QualityMetricAvailability.NOT_APPLICABLE:
            if self.value is not None:
                raise ValueError("not_applicable precision cannot emit a value")
            if self.classification_status is not QualityMetricClassificationStatus.UNAVAILABLE:
                raise ValueError("not_applicable requires unavailable classification_status")
            return self

        if expected_denom == 0:
            if self.value is not None:
                raise ValueError("zero denominator cannot emit artificial precision")
            if self.availability not in {
                QualityMetricAvailability.UNAVAILABLE,
                QualityMetricAvailability.NOT_APPLICABLE,
            }:
                raise ValueError("zero denominator requires unavailable or not_applicable")
            if self.classification_status is not QualityMetricClassificationStatus.UNAVAILABLE:
                raise ValueError("zero denominator requires unavailable classification_status")
            return self

        expected_value = precision_ratio_from_counts(
            self.true_positive_count,
            self.false_positive_count,
        )
        if self.value is None:
            raise ValueError("positive denominator requires a precision value")
        if expected_value is None:
            raise ValueError("value must reconcile with TP and FP counts")
        if (self.value - expected_value).copy_abs() > Decimal("1e-12"):
            raise ValueError("value must reconcile with TP and FP counts")
        if self.value < Decimal("0") or self.value > Decimal("1"):
            raise ValueError("precision value must be within 0 and 1")
        if self.availability not in {
            QualityMetricAvailability.AVAILABLE,
            QualityMetricAvailability.INSUFFICIENT_SAMPLE,
        }:
            raise ValueError(
                "positive denominator requires available or insufficient_sample availability"
            )
        if self.classification_status is QualityMetricClassificationStatus.UNAVAILABLE:
            raise ValueError("positive denominator cannot use unavailable classification_status")
        return self

    def as_compat_float(self) -> float | None:
        """Legacy float projection for PackPrecisionRecord.precision."""

        return float(self.value) if self.value is not None else None

    def canonical_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        if payload.get("value") is not None:
            payload["value"] = format(Decimal(str(payload["value"])), "f")
        return payload

    def to_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))


def build_precision_metric(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
    true_positive_count: int,
    false_positive_count: int,
    source: QualityMetricSource | str = QualityMetricSource.EXPECTED_ACTUAL_VALIDATION,
    sample: QualityMetricSample | Mapping[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    not_applicable: bool = False,
    unavailable_reason: str | None = None,
) -> PrecisionMetric:
    """Build a PrecisionMetric; value is always derived from TP/FP (never caller-supplied)."""

    if true_positive_count < 0 or false_positive_count < 0:
        raise ValueError("TP and FP counts must be non-negative")

    scope_enum = (
        scope if isinstance(scope, QualityMetricScope) else QualityMetricScope(str(scope))
    )
    normalized_scope_id = normalize_scope_id(scope_id)
    metric_id = build_precision_metric_id(scope=scope_enum, scope_id=normalized_scope_id)
    source_enum = (
        source
        if isinstance(source, QualityMetricSource)
        else QualityMetricSource(str(source))
    )
    sample_model = (
        sample
        if isinstance(sample, QualityMetricSample)
        else QualityMetricSample(**(dict(sample) if sample else {}))
    )
    notes = list(limitations or ())
    denominator = true_positive_count + false_positive_count

    if not_applicable:
        if unavailable_reason:
            notes.append(unavailable_reason)
        else:
            notes.append("precision not applicable for this scope")
        return PrecisionMetric(
            metric_id=metric_id,
            scope=scope_enum,
            scope_id=normalized_scope_id,
            true_positive_count=true_positive_count,
            false_positive_count=false_positive_count,
            denominator=denominator,
            value=None,
            availability=QualityMetricAvailability.NOT_APPLICABLE,
            classification_status=QualityMetricClassificationStatus.UNAVAILABLE,
            source=source_enum,
            sample=sample_model,
            limitations=dedupe_limitations(notes, label="precision limitation"),
        )

    if denominator == 0:
        notes.append("precision unavailable: TP+FP=0")
        if unavailable_reason:
            notes.append(unavailable_reason)
        return PrecisionMetric(
            metric_id=metric_id,
            scope=scope_enum,
            scope_id=normalized_scope_id,
            true_positive_count=true_positive_count,
            false_positive_count=false_positive_count,
            denominator=0,
            value=None,
            availability=QualityMetricAvailability.UNAVAILABLE,
            classification_status=QualityMetricClassificationStatus.UNAVAILABLE,
            source=source_enum,
            sample=sample_model,
            limitations=dedupe_limitations(notes, label="precision limitation"),
        )

    value = precision_ratio_from_counts(true_positive_count, false_positive_count)
    assert value is not None

    availability, classification_status, provisional_note = (
        provisional_availability_for_denominator(denominator)
    )
    if provisional_note:
        notes.append(provisional_note.replace("provisional metric", "provisional precision"))

    if source_enum is QualityMetricSource.CONTROLLED_FIXTURE:
        notes.append(
            "controlled-fixture scope only; not representative of arbitrary repositories"
        )

    return PrecisionMetric(
        metric_id=metric_id,
        scope=scope_enum,
        scope_id=normalized_scope_id,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        denominator=denominator,
        value=value,
        availability=availability,
        classification_status=classification_status,
        source=source_enum,
        sample=sample_model,
        limitations=dedupe_limitations(notes, label="precision limitation"),
    )


def aggregate_precision_from_counts(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
    true_positive_count: int,
    false_positive_count: int,
    source: QualityMetricSource | str = QualityMetricSource.EXPECTED_ACTUAL_VALIDATION,
    sample: QualityMetricSample | Mapping[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    not_applicable: bool = False,
) -> PrecisionMetric:
    """Aggregate precision from already-summed TP/FP (never average percentages)."""

    return build_precision_metric(
        scope=scope,
        scope_id=scope_id,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        source=source,
        sample=sample,
        limitations=limitations,
        not_applicable=not_applicable,
    )


def format_precision_display(value: Decimal | float | None) -> str:
    """Human-readable precision for Markdown (never '100% accurate')."""

    return format_metric_display(value)
