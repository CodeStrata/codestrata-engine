"""Tests for EvidenceMeasurement."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    EvidenceMeasurement,
    MeasurementAvailability,
    MeasurementComparisonResult,
    MeasurementScope,
    MeasurementValueType,
    ThresholdOperator,
    to_stable_dict,
)


def test_measured_zero_remains_available() -> None:
    metric = EvidenceMeasurement.available(
        metric_id="complexity.branches",
        metric_name="branches",
        measured_value=0,
        value_type=MeasurementValueType.INTEGER,
        scope=MeasurementScope.CALLABLE,
    )
    assert metric.availability is MeasurementAvailability.AVAILABLE
    assert metric.measured_value == 0


def test_unavailable_differs_from_zero() -> None:
    metric = EvidenceMeasurement.unavailable(
        metric_id="complexity.branches",
        metric_name="branches",
    )
    assert metric.availability is MeasurementAvailability.UNAVAILABLE
    assert metric.measured_value is None
    assert metric.measured_value != 0


def test_rejects_available_without_value() -> None:
    with pytest.raises(ValidationError, match="require measured_value"):
        EvidenceMeasurement(
            metric_id="m",
            metric_name="m",
            availability=MeasurementAvailability.AVAILABLE,
            measured_value=None,
        )


def test_rejects_unavailable_with_zero() -> None:
    with pytest.raises(ValidationError, match="leave measured_value"):
        EvidenceMeasurement(
            metric_id="m",
            metric_name="m",
            availability=MeasurementAvailability.UNAVAILABLE,
            measured_value=0,
        )


def test_thresholds_and_operators() -> None:
    metric = EvidenceMeasurement.available(
        metric_id="complexity.cyclomatic",
        metric_name="cyclomatic",
        measured_value=12,
        value_type=MeasurementValueType.INTEGER,
        threshold=10,
        threshold_operator=ThresholdOperator.GT,
        comparison_result=MeasurementComparisonResult.FAILS,
        scope=MeasurementScope.CALLABLE,
    )
    assert metric.threshold_operator is ThresholdOperator.GT


def test_bounded_thresholds() -> None:
    metric = EvidenceMeasurement.available(
        metric_id="ratio",
        metric_name="ratio",
        measured_value=0.5,
        threshold=0.2,
        upper_threshold=0.8,
        threshold_operator=ThresholdOperator.BETWEEN,
        comparison_result=MeasurementComparisonResult.PASSES,
    )
    assert metric.upper_threshold == 0.8


def test_invalid_comparison_combinations() -> None:
    with pytest.raises(ValidationError, match="forbids threshold"):
        EvidenceMeasurement.available(
            metric_id="m",
            metric_name="m",
            measured_value=1,
            threshold=1,
            threshold_operator=ThresholdOperator.NONE,
        )


def test_between_requires_both_thresholds() -> None:
    with pytest.raises(ValidationError, match="upper_threshold"):
        EvidenceMeasurement.available(
            metric_id="m",
            metric_name="m",
            measured_value=1,
            threshold=1,
            threshold_operator=ThresholdOperator.BETWEEN,
        )


def test_deterministic_serialization() -> None:
    metric = EvidenceMeasurement.available(
        metric_id="m",
        metric_name="metric",
        measured_value=0,
        value_type=MeasurementValueType.INTEGER,
        limitations=("b", "a"),
    )
    payload = to_stable_dict(metric)
    assert payload["measured_value"] == 0
    assert payload["limitations"] == ["a", "b"]
    assert "threshold" not in payload
