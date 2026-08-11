from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from codestrata.domain.rules.rule_confidence import (
    RuleConfidence,
    RuleConfidenceBasis,
    RuleConfidenceCalibrationStatus,
    RuleConfidenceLevel,
    RuleValidationSupport,
    compute_precision_recall,
    rule_confidence_to_json,
)


def test_precision_recall_and_zero_denominators() -> None:
    assert compute_precision_recall(3, 1, 2) == (0.75, 0.6)
    assert compute_precision_recall(0, 0, 0) == (None, None)
    support = RuleValidationSupport(validation_set_id="empty")
    assert support.precision is None
    assert support.recall is None


def test_validation_metrics_must_match_counts_when_present() -> None:
    support = RuleValidationSupport(
        validation_set_id="set-1",
        true_positives=3,
        false_positives=1,
        false_negatives=2,
        precision=0.75,
        recall=0.6,
    )
    assert support.precision == 0.75
    with pytest.raises(ValidationError, match="precision must match"):
        RuleValidationSupport(
            validation_set_id="set-1",
            true_positives=3,
            false_positives=1,
            precision=0.5,
        )


def test_rule_confidence_normalizes_and_enforces_high_policy() -> None:
    confidence = RuleConfidence(
        level=RuleConfidenceLevel.HIGH,
        basis=(
            RuleConfidenceBasis.EXACT_SIGNATURE,
            RuleConfidenceBasis.EXACT_SIGNATURE,
        ),
        limitations=("z limitation", "a limitation", "a limitation"),
        calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
    )
    assert confidence.basis == (RuleConfidenceBasis.EXACT_SIGNATURE,)
    assert confidence.limitations == ("a limitation", "z limitation")

    with pytest.raises(ValidationError, match="strong basis"):
        RuleConfidence(
            level=RuleConfidenceLevel.HIGH,
            basis=(RuleConfidenceBasis.STATIC_PATTERN,),
            calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
        )
    with pytest.raises(ValidationError, match="cannot be HIGH"):
        RuleConfidence(
            level=RuleConfidenceLevel.HIGH,
            basis=(
                RuleConfidenceBasis.EXACT_SIGNATURE,
                RuleConfidenceBasis.PARTIAL_EXTRACTION,
            ),
            calibration_status=RuleConfidenceCalibrationStatus.DEFINED,
        )


def test_validation_supported_requires_limited_support_record() -> None:
    with pytest.raises(ValidationError, match="requires validation_support"):
        RuleConfidence(
            level=RuleConfidenceLevel.MODERATE,
            basis=(RuleConfidenceBasis.STATIC_PATTERN,),
            calibration_status=RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED,
        )
    with pytest.raises(ValidationError, match="explicit limitations"):
        RuleConfidence(
            level=RuleConfidenceLevel.MODERATE,
            basis=(RuleConfidenceBasis.STATIC_PATTERN,),
            calibration_status=RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED,
            validation_support=RuleValidationSupport(
                validation_set_id="set-1",
                true_positives=1,
            ),
        )
    with pytest.raises(ValidationError, match="true positive"):
        RuleConfidence(
            level=RuleConfidenceLevel.MODERATE,
            basis=(RuleConfidenceBasis.STATIC_PATTERN,),
            calibration_status=RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED,
            validation_support=RuleValidationSupport(
                validation_set_id="set-1",
                limitations=("Controlled-fixture scope.",),
            ),
        )
    supported = RuleConfidence(
        level=RuleConfidenceLevel.HIGH,
        basis=(RuleConfidenceBasis.EXACT_SIGNATURE,),
        calibration_status=RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED,
        validation_support=RuleValidationSupport(
            validation_set_id="set-1",
            true_positives=2,
            false_positives=0,
            false_negatives=1,
            precision=1.0,
            recall=2 / 3,
            limitations=("Controlled-fixture scope; not universal.",),
        ),
    )
    assert supported.validation_support is not None
    assert supported.validation_support.true_positives == 2


def test_stable_report_projection_has_sorted_keys() -> None:
    confidence = RuleConfidence(
        level=RuleConfidenceLevel.LIMITED,
        basis=(RuleConfidenceBasis.PARTIAL_EXTRACTION,),
        limitations=("Partial extraction.",),
        calibration_status=RuleConfidenceCalibrationStatus.PROVISIONAL,
    )
    payload = rule_confidence_to_json(confidence)
    assert list(payload) == sorted(payload)
    assert json.dumps(payload, sort_keys=True) == json.dumps(
        rule_confidence_to_json(confidence),
        sort_keys=True,
    )
