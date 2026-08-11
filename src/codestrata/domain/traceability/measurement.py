"""EvidenceMeasurement — measured value / threshold envelope for traceability.

Distinguishes measured zero (``AVAILABLE`` + value ``0``) from unavailable,
not-applicable, failed, unsupported, and unknown states. Do not use truthiness
checks that conflate zero with missing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.traceability.enums import (
    MeasurementAvailability,
    MeasurementComparisonResult,
    MeasurementScope,
    MeasurementValueType,
    ThresholdOperator,
)
from codestrata.domain.traceability.validators import (
    TraceabilityValidationError,
    normalize_limitations,
)

_JSON_SCALAR = (str, int, float, bool, type(None))


class EvidenceMeasurement(BaseModel):
    """Bounded measurement attached to an EvidenceRef.

    When ``availability`` is not ``AVAILABLE``, ``measured_value`` /
    ``normalized_value`` must be unset (``None``). A measured zero remains
    ``AVAILABLE`` with ``measured_value=0``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    metric_name: str
    measured_value: int | float | str | bool | None = None
    value_type: MeasurementValueType = MeasurementValueType.NUMBER
    unit: str | None = None
    threshold: int | float | str | None = None
    upper_threshold: int | float | str | None = None
    threshold_operator: ThresholdOperator = ThresholdOperator.NONE
    threshold_source: str | None = None
    comparison_result: MeasurementComparisonResult = (
        MeasurementComparisonResult.NOT_COMPARED
    )
    availability: MeasurementAvailability = MeasurementAvailability.AVAILABLE
    scope: MeasurementScope = MeasurementScope.OTHER
    scope_reference: str | None = None
    raw_value: str | None = None
    normalized_value: int | float | str | bool | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("metric_id", "metric_name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="measurement field")

    @field_validator(
        "unit",
        "threshold_source",
        "scope_reference",
        "raw_value",
        mode="before",
    )
    @classmethod
    def normalize_optional_str(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional measurement field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("measured_value", "normalized_value", "threshold", "upper_threshold")
    @classmethod
    def ensure_json_scalar(cls, value: object) -> object:
        if value is None or isinstance(value, _JSON_SCALAR):
            # Reject bool masquerading checks already OK; ban non-finite floats.
            if isinstance(value, float) and (
                value != value or value in (float("inf"), float("-inf"))
            ):
                raise TraceabilityValidationError(
                    "measurement numeric values must be finite"
                )
            return value
        raise TraceabilityValidationError(
            "measurement values must be JSON scalars (str|int|float|bool|null)"
        )

    @model_validator(mode="after")
    def validate_availability_and_thresholds(self) -> EvidenceMeasurement:
        if self.availability is MeasurementAvailability.AVAILABLE:
            if self.measured_value is None:
                raise TraceabilityValidationError(
                    "available measurements require measured_value "
                    "(use 0 for a measured zero)"
                )
        elif self.measured_value is not None or self.normalized_value is not None:
            raise TraceabilityValidationError(
                "non-available measurements must leave measured_value and "
                "normalized_value unset (None); do not encode unavailable as 0"
            )

        operator = self.threshold_operator
        if operator is ThresholdOperator.NONE:
            if self.threshold is not None or self.upper_threshold is not None:
                raise TraceabilityValidationError(
                    "threshold_operator=none forbids threshold values"
                )
            if self.comparison_result not in {
                MeasurementComparisonResult.NOT_COMPARED,
                MeasurementComparisonResult.UNKNOWN,
            }:
                raise TraceabilityValidationError(
                    "comparison_result requires a threshold operator"
                )
            return self

        if operator in {
            ThresholdOperator.BETWEEN,
            ThresholdOperator.OUTSIDE,
        }:
            if self.threshold is None or self.upper_threshold is None:
                raise TraceabilityValidationError(
                    f"{operator.value} requires threshold and upper_threshold"
                )
            if (
                isinstance(self.threshold, (int, float))
                and isinstance(self.upper_threshold, (int, float))
                and self.upper_threshold < self.threshold
            ):
                raise TraceabilityValidationError(
                    "upper_threshold must be >= threshold"
                )
        else:
            if self.threshold is None:
                raise TraceabilityValidationError(
                    f"{operator.value} requires threshold"
                )
            if self.upper_threshold is not None:
                raise TraceabilityValidationError(
                    f"{operator.value} forbids upper_threshold"
                )

        return self

    @classmethod
    def available(
        cls,
        *,
        metric_id: str,
        metric_name: str,
        measured_value: int | float | str | bool,
        value_type: MeasurementValueType = MeasurementValueType.NUMBER,
        **kwargs: Any,
    ) -> EvidenceMeasurement:
        return cls(
            metric_id=metric_id,
            metric_name=metric_name,
            measured_value=measured_value,
            value_type=value_type,
            availability=MeasurementAvailability.AVAILABLE,
            **kwargs,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        metric_id: str,
        metric_name: str,
        availability: MeasurementAvailability = MeasurementAvailability.UNAVAILABLE,
        **kwargs: Any,
    ) -> EvidenceMeasurement:
        if availability is MeasurementAvailability.AVAILABLE:
            raise TraceabilityValidationError(
                "unavailable() cannot use availability=available"
            )
        return cls(
            metric_id=metric_id,
            metric_name=metric_name,
            measured_value=None,
            availability=availability,
            comparison_result=MeasurementComparisonResult.NOT_COMPARED,
            threshold_operator=ThresholdOperator.NONE,
            **kwargs,
        )
