"""Slice 5.7 — canonical PrecisionMetric model and formula tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from codestrata.domain.quality_metrics.precision import (
    PrecisionMetric,
    QualityMetricAvailability,
    QualityMetricClassificationStatus,
    QualityMetricSample,
    QualityMetricScope,
    QualityMetricSource,
    aggregate_precision_from_counts,
    build_precision_metric,
    build_precision_metric_id,
    format_precision_display,
    precision_ratio_from_counts,
    resolve_quality_metric_source,
)


def test_valid_tp_fp_and_deterministic_metric_id() -> None:
    metric = build_precision_metric(
        scope=QualityMetricScope.RULE,
        scope_id="security.credential-literal",
        true_positive_count=4,
        false_positive_count=0,
        source=QualityMetricSource.CONTROLLED_FIXTURE,
    )
    assert metric.metric_id == "precision:rule:security.credential-literal"
    assert metric.denominator == 4
    assert metric.value == Decimal("1")
    assert metric.availability is QualityMetricAvailability.AVAILABLE
    assert "controlled-fixture" in " ".join(metric.limitations)


def test_negative_counts_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_precision_metric(
            scope="rule",
            scope_id="x",
            true_positive_count=-1,
            false_positive_count=0,
        )


def test_decimal_serialization_stable() -> None:
    metric = build_precision_metric(
        scope=QualityMetricScope.VALIDATION_SET,
        scope_id="security",
        true_positive_count=3,
        false_positive_count=1,
    )
    payload = metric.canonical_dict()
    assert payload["value"] == "0.75"
    restored = PrecisionMetric.model_validate(payload)
    assert restored.value == Decimal("0.75")
    assert metric.to_json() == PrecisionMetric.model_validate(payload).to_json()


def test_limitation_dedupe() -> None:
    metric = build_precision_metric(
        scope="other",
        scope_id="demo",
        true_positive_count=2,
        false_positive_count=0,
        limitations=("note-a", "note-a", "note-b"),
    )
    assert metric.limitations.count("note-a") == 1
    assert "note-b" in metric.limitations
    assert metric.limitations == tuple(sorted(set(metric.limitations)))


def test_contradictory_denominator_rejected() -> None:
    with pytest.raises(ValidationError, match="denominator"):
        PrecisionMetric(
            metric_id="precision:other:demo",
            scope=QualityMetricScope.OTHER,
            scope_id="demo",
            true_positive_count=1,
            false_positive_count=1,
            denominator=3,
            value=Decimal("0.5"),
            availability=QualityMetricAvailability.AVAILABLE,
            classification_status=QualityMetricClassificationStatus.MEASURED,
        )


def test_value_outside_0_1_rejected() -> None:
    with pytest.raises(ValidationError, match="reconcile|within 0 and 1"):
        PrecisionMetric(
            metric_id="precision:other:demo",
            scope=QualityMetricScope.OTHER,
            scope_id="demo",
            true_positive_count=2,
            false_positive_count=0,
            denominator=2,
            value=Decimal("1.5"),
            availability=QualityMetricAvailability.AVAILABLE,
            classification_status=QualityMetricClassificationStatus.MEASURED,
        )


def test_formula_cases() -> None:
    assert precision_ratio_from_counts(4, 0) == Decimal("1")
    assert precision_ratio_from_counts(3, 1) == Decimal("0.75")
    assert precision_ratio_from_counts(0, 2) == Decimal("0")
    assert precision_ratio_from_counts(0, 0) is None

    m_fp = build_precision_metric(
        scope="other",
        scope_id="fp-only",
        true_positive_count=0,
        false_positive_count=2,
    )
    assert m_fp.value == Decimal("0")
    assert m_fp.availability is QualityMetricAvailability.AVAILABLE

    m_zero = build_precision_metric(
        scope="other",
        scope_id="zero",
        true_positive_count=0,
        false_positive_count=0,
    )
    assert m_zero.value is None
    assert m_zero.availability is QualityMetricAvailability.UNAVAILABLE


def test_fn_ambiguous_do_not_affect_precision() -> None:
    metric = build_precision_metric(
        scope="repository",
        scope_id="repo:security",
        true_positive_count=2,
        false_positive_count=0,
        sample=QualityMetricSample(
            ambiguous_count=5,
            false_negative_count=9,
            not_applicable_count=3,
        ),
    )
    assert metric.value == Decimal("1")
    assert metric.denominator == 2
    assert metric.sample.false_negative_count == 9
    assert metric.sample.ambiguous_count == 5


def test_single_tp_is_provisional_not_100_percent_claim() -> None:
    metric = build_precision_metric(
        scope=QualityMetricScope.RULE,
        scope_id="rule.one-hit",
        true_positive_count=1,
        false_positive_count=0,
    )
    assert metric.value == Decimal("1")
    assert metric.classification_status is QualityMetricClassificationStatus.PROVISIONAL
    assert metric.availability is QualityMetricAvailability.INSUFFICIENT_SAMPLE
    assert "100% accurate" not in format_precision_display(metric.value)
    assert format_precision_display(metric.value) == "1.000"


def test_pack_aggregate_sums_counts_not_averages() -> None:
    # Repo A precision 1.0 (TP=1 FP=0), repo B precision 0.0 (TP=0 FP=1)
    # Average of percentages would be 0.5; correct aggregate is 0.5 from counts
    # but with different weight: TP=4 FP=0 and TP=0 FP=4 → precision 0.5 from sums.
    metric = aggregate_precision_from_counts(
        scope=QualityMetricScope.VALIDATION_SET,
        scope_id="security",
        true_positive_count=4,
        false_positive_count=4,
        source=QualityMetricSource.MIXED_VALIDATION_SET,
        sample=QualityMetricSample(
            repository_count=2,
            positive_repository_count=2,
            controlled_fixture_count=1,
            real_world_repository_count=1,
        ),
    )
    assert metric.value == Decimal("0.5")
    assert metric.metric_id == build_precision_metric_id(
        scope="validation_set",
        scope_id="security",
    )


def test_average_trap_unequal_weights() -> None:
    # Averaging 1.0 and 0.5 would yield 0.75; summed counts are TP=3 FP=1 → 0.75
    # coincidentally. Use TP=5+FP=0 (1.0) and TP=1+FP=1 (0.5): average=0.75,
    # summed = 6/7.
    averaged = (Decimal("1") + Decimal("0.5")) / 2
    metric = aggregate_precision_from_counts(
        scope="validation_set",
        scope_id="architecture",
        true_positive_count=6,
        false_positive_count=1,
    )
    assert metric.value == Decimal("6") / Decimal("7")
    assert metric.value != averaged


def test_resolve_mixed_source() -> None:
    assert (
        resolve_quality_metric_source(
            [
                QualityMetricSource.CONTROLLED_FIXTURE,
                QualityMetricSource.REAL_WORLD_REPOSITORY,
            ]
        )
        is QualityMetricSource.MIXED_VALIDATION_SET
    )


def test_category_and_family_scope_ids() -> None:
    categories = (
        "languages",
        "frameworks",
        "build_systems",
        "dependency_ecosystems",
        "runtimes",
        "composition",
        "application_indicators",
    )
    ids = [
        build_precision_metric_id(
            scope=QualityMetricScope.INVENTORY_CATEGORY,
            scope_id=category,
        )
        for category in categories
    ]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == [
        build_precision_metric_id(
            scope=QualityMetricScope.INVENTORY_CATEGORY,
            scope_id=category,
        )
        for category in sorted(categories)
    ]
    families = ("cloud.container", "cloud.orchestration", "ai.api-boundary")
    family_ids = [
        build_precision_metric_id(
            scope=QualityMetricScope.EVIDENCE_FAMILY,
            scope_id=family,
        )
        for family in families
    ]
    assert sorted(family_ids) == [
        build_precision_metric_id(
            scope=QualityMetricScope.EVIDENCE_FAMILY,
            scope_id=family,
        )
        for family in sorted(families)
    ]


def test_not_applicable_pack_disabled() -> None:
    metric = build_precision_metric(
        scope=QualityMetricScope.REPOSITORY,
        scope_id="repo:cloud",
        true_positive_count=0,
        false_positive_count=0,
        not_applicable=True,
        unavailable_reason="pack disabled",
    )
    assert metric.value is None
    assert metric.availability is QualityMetricAvailability.NOT_APPLICABLE
