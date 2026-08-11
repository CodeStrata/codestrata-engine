"""Slice 5.9 — FalsePositiveRecord model, identity, and lifecycle tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.quality_metrics.false_positives import (
    FalsePositiveClassification,
    FalsePositiveEntityType,
    FalsePositiveRecord,
    FalsePositiveResolution,
    FalsePositiveRootCause,
    FalsePositiveStatus,
    SafeValidationValue,
    build_false_positive_id,
    build_false_positive_record,
    merge_false_positive_records,
    summarize_false_positives,
)


def test_valid_fp_and_stable_id() -> None:
    a = build_false_positive_record(
        repository_id="local-security-hygiene",
        assessment_area="security:security.credential-literal",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="forbidden credential finding",
        actual="path=src/app.py",
        diagnostic="forbidden present",
        run_id="20260801T120000Z",
        rule_id="security.credential-literal",
        path="src/app.py",
        classification=FalsePositiveClassification.CONFIRMED,
    )
    b = build_false_positive_record(
        repository_id="local-security-hygiene",
        assessment_area="security:security.credential-literal",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="forbidden credential finding",
        actual="path=src/app.py",
        diagnostic="different diagnostic prose",
        run_id="20260801T130000Z",
        rule_id="security.credential-literal",
        path="src/app.py",
        classification=FalsePositiveClassification.SUSPECTED,
    )
    assert a.false_positive_id == b.false_positive_id
    assert a.false_positive_id.startswith("fp:")
    assert a.to_json()


def test_different_identity_inputs_change_id() -> None:
    base = dict(
        repository_id="repo-a",
        assessment_area="security:rule.a",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="forbidden",
        actual="hit",
        diagnostic="fp",
        run_id="20260801T120000Z",
        rule_id="rule.a",
        path="src/a.py",
    )
    first = build_false_positive_record(**base)
    assert (
        build_false_positive_record(**{**base, "repository_id": "repo-b"}).false_positive_id
        != first.false_positive_id
    )
    assert (
        build_false_positive_record(**{**base, "rule_id": "rule.b"}).false_positive_id
        != first.false_positive_id
    )
    assert (
        build_false_positive_record(**{**base, "path": "src/b.py"}).false_positive_id
        != first.false_positive_id
    )
    assert (
        build_false_positive_record(**{**base, "expected": "other"}).false_positive_id
        != first.false_positive_id
    )


def test_absolute_path_rejected() -> None:
    with pytest.raises(ValueError, match="absolute"):
        build_false_positive_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalsePositiveEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            path="/Users/me/secret.py",
        )


def test_safe_value_bounds_and_redaction() -> None:
    value = SafeValidationValue.from_raw("x" * 500)
    assert len(value.value) <= 240
    with pytest.raises(ValidationError):
        SafeValidationValue(kind="text", value="/Users/me/file")


def test_fixed_confirmed_requires_root_cause_resolution_and_regression() -> None:
    with pytest.raises(ValidationError, match="root_cause"):
        build_false_positive_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalsePositiveEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            classification=FalsePositiveClassification.CONFIRMED,
            status=FalsePositiveStatus.FIXED,
            resolution=FalsePositiveResolution.PRODUCT_FIX,
            regression_test_refs=("tests/validation/test_security_precision.py",),
        )
    with pytest.raises(ValidationError, match="regression"):
        build_false_positive_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalsePositiveEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            classification=FalsePositiveClassification.CONFIRMED,
            status=FalsePositiveStatus.FIXED,
            root_cause=FalsePositiveRootCause.RULE_PREDICATE,
            resolution=FalsePositiveResolution.PRODUCT_FIX,
        )
    ok = build_false_positive_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        classification=FalsePositiveClassification.CONFIRMED,
        status=FalsePositiveStatus.FIXED,
        root_cause=FalsePositiveRootCause.RULE_PREDICATE,
        resolution=FalsePositiveResolution.PRODUCT_FIX,
        resolved_run_id="20260801T130000Z",
        regression_test_refs=("tests/validation/test_security_precision.py",),
    )
    assert ok.status is FalsePositiveStatus.FIXED


def test_confirmed_cannot_use_expectation_error_root_cause() -> None:
    with pytest.raises(ValidationError, match="expectation_error"):
        build_false_positive_record(
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalsePositiveEntityType.FINDING,
            expected="e",
            actual="a",
            diagnostic="d",
            run_id="20260801T120000Z",
            classification=FalsePositiveClassification.CONFIRMED,
            root_cause=FalsePositiveRootCause.EXPECTATION_ERROR,
        )


def test_merge_dedupes_and_unions_refs() -> None:
    first = build_false_positive_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        rule_id="rule.x",
        evidence_ids=("ev-1",),
    )
    second = build_false_positive_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T130000Z",
        rule_id="rule.x",
        evidence_ids=("ev-2",),
    )
    merged = merge_false_positive_records((first, second))
    assert len(merged) == 1
    assert merged[0].first_seen_run_id == "20260801T120000Z"
    assert merged[0].last_seen_run_id == "20260801T130000Z"
    assert merged[0].evidence_ids == ("ev-1", "ev-2")


def test_summary_excludes_ambiguous_from_confirmed() -> None:
    confirmed = build_false_positive_record(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="e",
        actual="a",
        diagnostic="d",
        run_id="20260801T120000Z",
        classification=FalsePositiveClassification.CONFIRMED,
    )
    ambiguous = build_false_positive_record(
        repository_id="repo",
        assessment_area="security:y",
        entity_type=FalsePositiveEntityType.FINDING,
        expected="e2",
        actual="a2",
        diagnostic="amb",
        run_id="20260801T120000Z",
        classification=FalsePositiveClassification.AMBIGUOUS,
        status=FalsePositiveStatus.INVESTIGATING,
    )
    summary = summarize_false_positives((confirmed, ambiguous))
    assert summary.confirmed == 1
    assert summary.ambiguous == 1
    assert summary.total == 2


def test_build_false_positive_id_deterministic() -> None:
    assert build_false_positive_id(
        repository_id="repo",
        assessment_area="security:x",
        entity_type="finding",
        rule_id="x",
        expected_identity="e",
        actual_identity="a",
    ) == build_false_positive_id(
        repository_id="repo",
        assessment_area="security:x",
        entity_type=FalsePositiveEntityType.FINDING,
        rule_id="x",
        expected_identity="e",
        actual_identity="a",
    )


def test_resolved_before_first_seen_rejected() -> None:
    with pytest.raises(ValidationError, match="resolved_run_id"):
        FalsePositiveRecord(
            false_positive_id=build_false_positive_id(
                repository_id="repo",
                assessment_area="security:x",
                entity_type="finding",
                expected_identity="e",
                actual_identity="a",
            ),
            repository_id="repo",
            assessment_area="security:x",
            entity_type=FalsePositiveEntityType.FINDING,
            classification=FalsePositiveClassification.EXPECTATION_ERROR,
            status=FalsePositiveStatus.FIXED,
            expected=SafeValidationValue(kind="text", value="e"),
            actual=SafeValidationValue(kind="text", value="a"),
            diagnostic="d",
            first_seen_run_id="20260801T120000Z",
            last_seen_run_id="20260801T120000Z",
            resolved_run_id="20260701T120000Z",
            resolution=FalsePositiveResolution.EXPECTATION_FIX,
        )
