"""Slice 5.10 — FalseNegativeRecord model, identity, and lifecycle tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.quality_metrics.false_negatives import (
    FalseNegativeClassification,
    FalseNegativeEntityType,
    FalseNegativeRecord,
    FalseNegativeResolution,
    FalseNegativeRootCause,
    FalseNegativeStatus,
    build_false_negative_id,
    build_false_negative_record,
    merge_false_negative_records,
    summarize_false_negatives,
)
from codestrata.domain.quality_metrics.false_positives import SafeValidationValue


def test_valid_fn_and_stable_id() -> None:
    a = build_false_negative_record(
        repository_id="local-security-hygiene",
        assessment_area="security:security.credential-literal",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="required credential finding",
        actual="absent",
        diagnostic="required missing",
        run_id="20260801T120000Z",
        expected_rule_id="security.credential-literal",
        expected_path="src/app.py",
        classification=FalseNegativeClassification.CONFIRMED,
    )
    b = build_false_negative_record(
        repository_id="local-security-hygiene",
        assessment_area="security:security.credential-literal",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="required credential finding",
        actual="still absent",
        diagnostic="different diagnostic prose",
        run_id="20260801T130000Z",
        expected_rule_id="security.credential-literal",
        expected_path="src/app.py",
        classification=FalseNegativeClassification.SUSPECTED,
    )
    assert a.false_negative_id == b.false_negative_id
    assert a.false_negative_id.startswith("fn:")
    assert a.to_json()


def test_different_identity_inputs_change_id() -> None:
    base = dict(
        repository_id="repo-a",
        assessment_area="security:rule.a",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="required",
        actual="absent",
        diagnostic="fn",
        run_id="20260801T120000Z",
        expected_rule_id="rule.a",
        expected_path="src/a.py",
    )
    first = build_false_negative_record(**base)
    assert (
        build_false_negative_record(**{**base, "repository_id": "repo-b"}).false_negative_id
        != first.false_negative_id
    )
    assert (
        build_false_negative_record(
            **{**base, "expected_rule_id": "rule.b"}
        ).false_negative_id
        != first.false_negative_id
    )
    assert (
        build_false_negative_record(**{**base, "expected_path": "src/b.py"}).false_negative_id
        != first.false_negative_id
    )
    assert (
        build_false_negative_record(**{**base, "expected": "other"}).false_negative_id
        != first.false_negative_id
    )


def test_absolute_path_rejected() -> None:
    with pytest.raises(ValueError, match="absolute"):
        build_false_negative_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            expected_path="/Users/me/secret.py",
        )


def test_safe_value_bounds_and_redaction() -> None:
    value = SafeValidationValue.from_raw("x" * 500)
    assert len(value.value) <= 240
    with pytest.raises(ValidationError):
        SafeValidationValue(kind="text", value="/Users/me/file")


def test_missing_expected_identity_rejected() -> None:
    with pytest.raises(ValidationError, match="expected-positive identity"):
        FalseNegativeRecord(
            false_negative_id=build_false_negative_id(
                repository_id="repo",
                assessment_area="security:x",
                entity_type="finding",
                expected_condition_identity="placeholder",
            ),
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected=SafeValidationValue(kind="text", value=""),
            actual=SafeValidationValue(kind="text", value="absent"),
            diagnostic="d",
            first_seen_run_id="20260801T120000Z",
            last_seen_run_id="20260801T120000Z",
        )


def test_fixed_confirmed_requires_root_cause_resolution_and_regression() -> None:
    with pytest.raises(ValidationError, match="root_cause"):
        build_false_negative_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            expected_rule_id="rule.x",
            classification=FalseNegativeClassification.CONFIRMED,
            status=FalseNegativeStatus.FIXED,
            resolution=FalseNegativeResolution.PRODUCT_FIX,
            regression_test_refs=("tests/validation/test_security_precision.py",),
        )
    with pytest.raises(ValidationError, match="regression"):
        build_false_negative_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            expected_rule_id="rule.x",
            classification=FalseNegativeClassification.CONFIRMED,
            status=FalseNegativeStatus.FIXED,
            root_cause=FalseNegativeRootCause.RULE_PREDICATE,
            resolution=FalseNegativeResolution.PRODUCT_FIX,
        )
    ok = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        expected_rule_id="rule.x",
        classification=FalseNegativeClassification.CONFIRMED,
        status=FalseNegativeStatus.FIXED,
        root_cause=FalseNegativeRootCause.RULE_PREDICATE,
        resolution=FalseNegativeResolution.PRODUCT_FIX,
        resolved_run_id="20260801T130000Z",
        regression_test_refs=("tests/validation/test_security_precision.py",),
    )
    assert ok.status is FalseNegativeStatus.FIXED


def test_confirmed_cannot_use_expectation_error_root_cause() -> None:
    with pytest.raises(ValidationError, match="expectation_error"):
        build_false_negative_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            expected_rule_id="rule.x",
            classification=FalseNegativeClassification.CONFIRMED,
            root_cause=FalseNegativeRootCause.EXPECTATION_ERROR,
        )


def test_merge_dedupes_and_unions_refs() -> None:
    first = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        expected_rule_id="rule.x",
        supporting_evidence_ids=("ev-1",),
    )
    second = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T130000Z",
        expected_rule_id="rule.x",
        supporting_evidence_ids=("ev-2",),
    )
    different_rule = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:y",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        expected_rule_id="rule.y",
    )
    merged = merge_false_negative_records((first, second, different_rule))
    assert len(merged) == 2
    same = next(item for item in merged if item.expected_rule_id == "rule.x")
    assert same.first_seen_run_id == "20260801T120000Z"
    assert same.last_seen_run_id == "20260801T130000Z"
    assert same.supporting_evidence_ids == ("ev-1", "ev-2")


def test_summary_separates_classifications() -> None:
    confirmed = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        expected_rule_id="rule.x",
        classification=FalseNegativeClassification.CONFIRMED,
    )
    ambiguous = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:y",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e2",
        actual="a2",
        diagnostic="amb",
        run_id="20260801T120000Z",
        expected_rule_id="rule.y",
        classification=FalseNegativeClassification.AMBIGUOUS,
        status=FalseNegativeStatus.INVESTIGATING,
    )
    insufficient = build_false_negative_record(
        repository_id="repo",
        assessment_area="security:z",
        entity_type=FalseNegativeEntityType.FINDING,
        expected="e3",
        actual="a3",
        diagnostic="parse failed",
        run_id="20260801T120000Z",
        expected_rule_id="rule.z",
        classification=FalseNegativeClassification.INSUFFICIENT_EVIDENCE,
        status=FalseNegativeStatus.INVESTIGATING,
    )
    summary = summarize_false_negatives((confirmed, ambiguous, insufficient))
    assert summary.confirmed == 1
    assert summary.ambiguous == 1
    assert summary.insufficient_evidence == 1
    assert summary.total == 3


def test_build_false_negative_id_deterministic() -> None:
    assert build_false_negative_id(
        repository_id="repo",
        assessment_area="security:x",
        entity_type="finding",
        expected_rule_id="x",
        expected_condition_identity="e",
    ) == build_false_negative_id(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalseNegativeEntityType.FINDING,
        expected_rule_id="x",
        expected_condition_identity="e",
    )


def test_resolved_before_first_seen_rejected() -> None:
    with pytest.raises(ValidationError, match="resolved_run_id"):
        FalseNegativeRecord(
            false_negative_id=build_false_negative_id(
                repository_id="repo",
                assessment_area="security:x",
                entity_type="finding",
                expected_condition_identity="e",
            ),
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalseNegativeEntityType.FINDING,
            expected_rule_id="rule.x",
            classification=FalseNegativeClassification.EXPECTATION_ERROR,
            status=FalseNegativeStatus.FIXED,
            expected=SafeValidationValue(kind="text", value="e"),
            actual=SafeValidationValue(kind="text", value="a"),
            diagnostic="d",
            first_seen_run_id="20260801T120000Z",
            last_seen_run_id="20260801T120000Z",
            resolved_run_id="20260701T120000Z",
            resolution=FalseNegativeResolution.EXPECTATION_FIX,
        )
