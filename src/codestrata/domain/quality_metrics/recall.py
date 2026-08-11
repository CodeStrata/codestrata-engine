"""Canonical Recall Metric (Epic 5 Slice 5.8).

Recall answers: of the expected supported positive conditions within a defined
validation scope, what proportion were detected?

    recall = true_positives / (true_positives + false_negatives)

Recall requires authored expected positives. Negative controls alone cannot
establish recall. Internal validation/calibration only — not customer runtime
quality, confidence, assessment coverage, or a product-wide detection claim.
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
)


def build_recall_metric_id(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
) -> str:
    """Deterministic metric id: ``recall:{scope}:{scope_id}``."""

    return build_quality_metric_id(kind="recall", scope=scope, scope_id=scope_id)


def recall_ratio_from_counts(
    true_positive_count: int,
    false_negative_count: int,
) -> Decimal | None:
    """Return exact Decimal recall or ``None`` when TP+FN == 0.

    False positives and ambiguous observations are intentionally ignored.
    """

    if true_positive_count < 0 or false_negative_count < 0:
        raise ValueError("TP and FN counts must be non-negative")
    denominator = true_positive_count + false_negative_count
    if denominator == 0:
        return None
    return Decimal(true_positive_count) / Decimal(denominator)


def recall_ratio_as_float(
    true_positive_count: int,
    false_negative_count: int,
) -> float | None:
    """Compatibility float projection for legacy pack/result fields."""

    value = recall_ratio_from_counts(true_positive_count, false_negative_count)
    return float(value) if value is not None else None


class RecallMetric(BaseModel):
    """Canonical recall metric derived only from TP and FN counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    scope: QualityMetricScope
    scope_id: str
    true_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
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
        return require_nonblank(str(value), label="recall metric identity")

    @field_validator("value", mode="before")
    @classmethod
    def normalize_value(cls, value: object) -> Decimal | None:
        return as_decimal(value, label="recall value")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return dedupe_limitations(value, label="recall limitation")

    @model_validator(mode="after")
    def validate_metric(self) -> RecallMetric:
        expected_id = build_recall_metric_id(scope=self.scope, scope_id=self.scope_id)
        if self.metric_id != expected_id:
            raise ValueError(
                f"metric_id must be deterministic ({expected_id!r}), got {self.metric_id!r}"
            )
        if self.scope_id != normalize_scope_id(self.scope_id):
            raise ValueError("scope_id must be normalized")
        expected_denom = self.true_positive_count + self.false_negative_count
        if self.denominator != expected_denom:
            raise ValueError("denominator must equal true_positive_count + false_negative_count")

        if self.availability is QualityMetricAvailability.NOT_APPLICABLE:
            if self.value is not None:
                raise ValueError("not_applicable recall cannot emit a value")
            if self.classification_status is not QualityMetricClassificationStatus.UNAVAILABLE:
                raise ValueError("not_applicable requires unavailable classification_status")
            return self

        if expected_denom == 0:
            if self.value is not None:
                raise ValueError("zero denominator cannot emit artificial recall")
            if self.availability not in {
                QualityMetricAvailability.UNAVAILABLE,
                QualityMetricAvailability.NOT_APPLICABLE,
                QualityMetricAvailability.INSUFFICIENT_SAMPLE,
            }:
                raise ValueError(
                    "zero denominator requires unavailable, not_applicable, or insufficient_sample"
                )
            if self.classification_status is not QualityMetricClassificationStatus.UNAVAILABLE:
                raise ValueError("zero denominator requires unavailable classification_status")
            return self

        expected_value = recall_ratio_from_counts(
            self.true_positive_count,
            self.false_negative_count,
        )
        if self.value is None:
            raise ValueError("positive denominator requires a recall value")
        if expected_value is None:
            raise ValueError("value must reconcile with TP and FN counts")
        if (self.value - expected_value).copy_abs() > Decimal("1e-12"):
            raise ValueError("value must reconcile with TP and FN counts")
        if self.value < Decimal("0") or self.value > Decimal("1"):
            raise ValueError("recall value must be within 0 and 1")
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
        """Legacy float projection for PackPrecisionRecord.recall."""

        return float(self.value) if self.value is not None else None

    def canonical_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        if payload.get("value") is not None:
            payload["value"] = format(Decimal(str(payload["value"])), "f")
        return payload

    def to_json(self) -> str:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))


def build_recall_metric(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
    true_positive_count: int,
    false_negative_count: int,
    source: QualityMetricSource | str = QualityMetricSource.EXPECTED_ACTUAL_VALIDATION,
    sample: QualityMetricSample | Mapping[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    not_applicable: bool = False,
    unavailable_reason: str | None = None,
) -> RecallMetric:
    """Build a RecallMetric; value is always derived from TP/FN (never caller-supplied)."""

    if true_positive_count < 0 or false_negative_count < 0:
        raise ValueError("TP and FN counts must be non-negative")

    scope_enum = (
        scope if isinstance(scope, QualityMetricScope) else QualityMetricScope(str(scope))
    )
    normalized_scope_id = normalize_scope_id(scope_id)
    metric_id = build_recall_metric_id(scope=scope_enum, scope_id=normalized_scope_id)
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
    denominator = true_positive_count + false_negative_count

    if not_applicable:
        if unavailable_reason:
            notes.append(unavailable_reason)
        else:
            notes.append("recall not applicable for this scope")
        return RecallMetric(
            metric_id=metric_id,
            scope=scope_enum,
            scope_id=normalized_scope_id,
            true_positive_count=true_positive_count,
            false_negative_count=false_negative_count,
            denominator=denominator,
            value=None,
            availability=QualityMetricAvailability.NOT_APPLICABLE,
            classification_status=QualityMetricClassificationStatus.UNAVAILABLE,
            source=source_enum,
            sample=sample_model,
            limitations=dedupe_limitations(notes, label="recall limitation"),
        )

    if denominator == 0:
        notes.append("recall unavailable: TP+FN=0")
        notes.append(
            "no authored expected positives in this scope "
            "(negative controls alone cannot establish recall)"
        )
        if unavailable_reason:
            notes.append(unavailable_reason)
        return RecallMetric(
            metric_id=metric_id,
            scope=scope_enum,
            scope_id=normalized_scope_id,
            true_positive_count=true_positive_count,
            false_negative_count=false_negative_count,
            denominator=0,
            value=None,
            availability=QualityMetricAvailability.UNAVAILABLE,
            classification_status=QualityMetricClassificationStatus.UNAVAILABLE,
            source=source_enum,
            sample=sample_model,
            limitations=dedupe_limitations(notes, label="recall limitation"),
        )

    value = recall_ratio_from_counts(true_positive_count, false_negative_count)
    assert value is not None

    availability, classification_status, provisional_note = (
        provisional_availability_for_denominator(denominator)
    )
    if provisional_note:
        notes.append(provisional_note.replace("provisional metric", "provisional recall"))

    if source_enum is QualityMetricSource.CONTROLLED_FIXTURE:
        notes.append(
            "controlled-fixture scope only; does not establish arbitrary-repository recall"
        )
        if sample_model.controlled_fixture_count:
            notes.append(
                f"controlled fixture count: {sample_model.controlled_fixture_count}; "
                f"expected-positive denominator: {denominator}"
            )

    return RecallMetric(
        metric_id=metric_id,
        scope=scope_enum,
        scope_id=normalized_scope_id,
        true_positive_count=true_positive_count,
        false_negative_count=false_negative_count,
        denominator=denominator,
        value=value,
        availability=availability,
        classification_status=classification_status,
        source=source_enum,
        sample=sample_model,
        limitations=dedupe_limitations(notes, label="recall limitation"),
    )


def aggregate_recall_from_counts(
    *,
    scope: QualityMetricScope | str,
    scope_id: str,
    true_positive_count: int,
    false_negative_count: int,
    source: QualityMetricSource | str = QualityMetricSource.EXPECTED_ACTUAL_VALIDATION,
    sample: QualityMetricSample | Mapping[str, Any] | None = None,
    limitations: Sequence[str] | None = None,
    not_applicable: bool = False,
) -> RecallMetric:
    """Aggregate recall from already-summed TP/FN (never average percentages)."""

    return build_recall_metric(
        scope=scope,
        scope_id=scope_id,
        true_positive_count=true_positive_count,
        false_negative_count=false_negative_count,
        source=source,
        sample=sample,
        limitations=limitations,
        not_applicable=not_applicable,
    )


def format_recall_display(value: Decimal | float | None) -> str:
    """Human-readable recall for Markdown (never '100% detection')."""

    return format_metric_display(value)
