"""Slice 5.8 — canonical RecallMetric model and formula tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from codestrata.domain.quality_metrics.common import (
    QualityMetricAvailability,
    QualityMetricClassificationStatus,
    QualityMetricSample,
    QualityMetricScope,
    QualityMetricSource,
)
from codestrata.domain.quality_metrics.recall import (
    RecallMetric,
    aggregate_recall_from_counts,
    build_recall_metric,
    build_recall_metric_id,
    format_recall_display,
    recall_ratio_from_counts,
)


def test_valid_tp_fn_and_deterministic_metric_id() -> None:
    metric = build_recall_metric(
        scope=QualityMetricScope.RULE,
        scope_id="security.credential-literal",
        true_positive_count=4,
        false_negative_count=0,
        source=QualityMetricSource.CONTROLLED_FIXTURE,
        sample=QualityMetricSample(controlled_fixture_count=1),
    )
    assert metric.metric_id == "recall:rule:security.credential-literal"
    assert metric.denominator == 4
    assert metric.value == Decimal("1")
    assert "controlled-fixture" in " ".join(metric.limitations)
    assert "arbitrary-repository recall" in " ".join(metric.limitations)


def test_negative_counts_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_recall_metric(
            scope="rule",
            scope_id="x",
            true_positive_count=0,
            false_negative_count=-1,
        )


def test_decimal_serialization_stable() -> None:
    metric = build_recall_metric(
        scope=QualityMetricScope.VALIDATION_SET,
        scope_id="security",
        true_positive_count=3,
        false_negative_count=1,
    )
    payload = metric.canonical_dict()
    assert payload["value"] == "0.75"
    restored = RecallMetric.model_validate(payload)
    assert restored.value == Decimal("0.75")
    assert metric.to_json() == RecallMetric.model_validate(payload).to_json()


def test_limitation_dedupe() -> None:
    metric = build_recall_metric(
        scope="other",
        scope_id="demo",
        true_positive_count=2,
        false_negative_count=0,
        limitations=("note-a", "note-a", "note-b"),
    )
    assert metric.limitations.count("note-a") == 1
    assert "note-b" in metric.limitations
    assert metric.limitations == tuple(sorted(set(metric.limitations)))


def test_contradictory_denominator_rejected() -> None:
    with pytest.raises(ValidationError, match="denominator"):
        RecallMetric(
            metric_id="recall:other:demo",
            scope=QualityMetricScope.OTHER,
            scope_id="demo",
            true_positive_count=1,
            false_negative_count=1,
            denominator=3,
            value=Decimal("0.5"),
            availability=QualityMetricAvailability.AVAILABLE,
            classification_status=QualityMetricClassificationStatus.MEASURED,
        )


def test_value_outside_0_1_rejected() -> None:
    with pytest.raises(ValidationError, match="reconcile|within 0 and 1"):
        RecallMetric(
            metric_id="recall:other:demo",
            scope=QualityMetricScope.OTHER,
            scope_id="demo",
            true_positive_count=2,
            false_negative_count=0,
            denominator=2,
            value=Decimal("1.5"),
            availability=QualityMetricAvailability.AVAILABLE,
            classification_status=QualityMetricClassificationStatus.MEASURED,
        )


def test_formula_cases() -> None:
    assert recall_ratio_from_counts(4, 0) == Decimal("1")
    assert recall_ratio_from_counts(3, 1) == Decimal("0.75")
    assert recall_ratio_from_counts(0, 2) == Decimal("0")
    assert recall_ratio_from_counts(0, 0) is None

    m_fn = build_recall_metric(
        scope="other",
        scope_id="fn-only",
        true_positive_count=0,
        false_negative_count=2,
    )
    assert m_fn.value == Decimal("0")
    assert m_fn.availability is QualityMetricAvailability.AVAILABLE

    m_zero = build_recall_metric(
        scope="other",
        scope_id="zero",
        true_positive_count=0,
        false_negative_count=0,
    )
    assert m_zero.value is None
    assert m_zero.availability is QualityMetricAvailability.UNAVAILABLE
    assert any("negative controls" in note for note in m_zero.limitations)


def test_fp_ambiguous_do_not_affect_recall() -> None:
    metric = build_recall_metric(
        scope="repository",
        scope_id="repo:security",
        true_positive_count=2,
        false_negative_count=0,
        sample=QualityMetricSample(
            ambiguous_count=5,
            false_positive_count=9,
            not_applicable_count=3,
        ),
    )
    assert metric.value == Decimal("1")
    assert metric.denominator == 2
    assert metric.sample.false_positive_count == 9


def test_single_tp_is_provisional_not_complete_detection_claim() -> None:
    metric = build_recall_metric(
        scope=QualityMetricScope.RULE,
        scope_id="rule.one-hit",
        true_positive_count=1,
        false_negative_count=0,
    )
    assert metric.value == Decimal("1")
    assert metric.classification_status is QualityMetricClassificationStatus.PROVISIONAL
    assert metric.availability is QualityMetricAvailability.INSUFFICIENT_SAMPLE
    assert "100% detection" not in format_recall_display(metric.value)
    assert format_recall_display(metric.value) == "1.000"


def test_pack_aggregate_sums_counts_not_averages() -> None:
    averaged = (Decimal("1") + Decimal("0.5")) / 2
    metric = aggregate_recall_from_counts(
        scope=QualityMetricScope.VALIDATION_SET,
        scope_id="architecture",
        true_positive_count=6,
        false_negative_count=1,
        source=QualityMetricSource.MIXED_VALIDATION_SET,
        sample=QualityMetricSample(
            repository_count=2,
            expected_positive_repository_count=2,
            controlled_fixture_count=1,
            real_world_repository_count=1,
        ),
    )
    assert metric.value == Decimal("6") / Decimal("7")
    assert metric.value != averaged
    assert metric.metric_id == build_recall_metric_id(
        scope="validation_set",
        scope_id="architecture",
    )


def test_negative_control_unavailable() -> None:
    metric = build_recall_metric(
        scope=QualityMetricScope.REPOSITORY,
        scope_id="local-ai-negative:security",
        true_positive_count=0,
        false_negative_count=0,
        unavailable_reason="negative-control repository",
    )
    assert metric.value is None
    assert metric.availability is QualityMetricAvailability.UNAVAILABLE


def test_not_applicable_pack_disabled() -> None:
    metric = build_recall_metric(
        scope=QualityMetricScope.REPOSITORY,
        scope_id="repo:cloud",
        true_positive_count=0,
        false_negative_count=0,
        not_applicable=True,
        unavailable_reason="pack disabled",
    )
    assert metric.value is None
    assert metric.availability is QualityMetricAvailability.NOT_APPLICABLE


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
        build_recall_metric_id(
            scope=QualityMetricScope.INVENTORY_CATEGORY,
            scope_id=category,
        )
        for category in categories
    ]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == [
        build_recall_metric_id(
            scope=QualityMetricScope.INVENTORY_CATEGORY,
            scope_id=category,
        )
        for category in sorted(categories)
    ]
    families = (
        "cloud.container",
        "architecture.cycle",
        "technical_debt.large-callable",
        "dependency.manifest",
        "ai.api-boundary",
        "modernization.priority-action",
    )
    family_ids = [
        build_recall_metric_id(
            scope=QualityMetricScope.EVIDENCE_FAMILY,
            scope_id=family,
        )
        for family in families
    ]
    assert sorted(family_ids) == [
        build_recall_metric_id(
            scope=QualityMetricScope.EVIDENCE_FAMILY,
            scope_id=family,
        )
        for family in sorted(families)
    ]
