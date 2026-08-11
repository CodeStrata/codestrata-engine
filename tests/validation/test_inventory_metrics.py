"""Unit tests for Technology Inventory classification and metrics (Slice 4.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from validation.inventory import (
    FactClassification,
    InventoryVersionExpectation,
    TechnologyInventoryExpectation,
    aggregate_inventory_results,
    classify_name_sets,
    compute_precision_recall,
    metrics_from_classifications,
    validate_technology_inventory,
)


def test_contradictory_inventory_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        TechnologyInventoryExpectation(
            required_languages=("Python",),
            forbidden_languages=("Python",),
        )
    with pytest.raises(ValidationError, match="ambiguous"):
        TechnologyInventoryExpectation(
            required_frameworks=("Flask",),
            allowed_ambiguous_facts=("Flask",),
        )


def test_classify_true_false_ambiguous_and_na() -> None:
    facts = classify_name_sets(
        category="languages",
        required=("Python", "Java"),
        forbidden=("COBOL",),
        actual=("Python", "COBOL", "Shell"),
        ambiguous_allowed=("Shell",),
    )
    by_class = {item.name: item.classification for item in facts}
    assert by_class["Python"] is FactClassification.TRUE_POSITIVE
    assert by_class["Java"] is FactClassification.FALSE_NEGATIVE
    assert by_class["COBOL"] is FactClassification.FALSE_POSITIVE
    assert by_class["Shell"] is FactClassification.AMBIGUOUS

    na = classify_name_sets(
        category="versions",
        required=(),
        forbidden=(),
        actual=(),
        category_not_applicable=True,
    )
    assert na[0].classification is FactClassification.NOT_APPLICABLE


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0,
        false_positives=0,
        false_negatives=0,
    )
    assert precision is None
    assert recall is None
    assert reason is not None
    assert "unavailable" in reason

    precision, recall, _ = compute_precision_recall(
        true_positives=2,
        false_positives=1,
        false_negatives=1,
    )
    assert precision == pytest.approx(2 / 3)
    assert recall == pytest.approx(2 / 3)


def test_validate_inventory_and_aggregate_deterministic() -> None:
    expectation = TechnologyInventoryExpectation(
        required_languages=("Python",),
        forbidden_languages=("Java",),
        required_build_systems=("pip",),
        required_dependency_ecosystems=("pip",),
        required_libraries=("OpenAI",),
        required_versions=(
            InventoryVersionExpectation(
                name="OpenAI",
                version=">=1.40.0",
                version_state="range",
                evidence_note="requirements.txt",
            ),
        ),
        expected_application_indicators=("ai_integration",),
        evidence_notes="controlled fixture",
    )
    actual = {
        "languages": ("Python",),
        "build_systems": ("pip",),
        "dependency_ecosystems": ("pip",),
        "libraries": ("OpenAI",),
        "application_indicators": ("ai_integration",),
    }
    result = validate_technology_inventory(
        repository_id="local-ai-readiness",
        expectation=expectation,
        actual_by_category=actual,
        actual_versions={"OpenAI": ">=1.40.0"},
    )
    assert result.passed
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.precision == 1.0
    assert result.recall == 1.0

    failed = validate_technology_inventory(
        repository_id="local-ai-readiness",
        expectation=expectation,
        actual_by_category={
            "languages": ("Python", "Java"),
            "build_systems": (),
            "dependency_ecosystems": (),
            "libraries": (),
            "application_indicators": (),
        },
        actual_versions={},
    )
    assert not failed.passed
    assert failed.false_positives >= 1
    assert failed.false_negatives >= 1

    aggregate = aggregate_inventory_results([result, failed])
    assert aggregate.repository_count == 2
    assert aggregate.true_positives == result.true_positives + failed.true_positives
    categories = [item.category for item in aggregate.per_category]
    assert categories == sorted(categories)


def test_category_metrics_from_classifications() -> None:
    facts = classify_name_sets(
        category="frameworks",
        required=("Flask",),
        forbidden=("Django",),
        actual=("Flask",),
    )
    metrics = metrics_from_classifications(category="frameworks", classifications=facts)
    assert metrics.true_positives == 1
    assert metrics.false_positives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
