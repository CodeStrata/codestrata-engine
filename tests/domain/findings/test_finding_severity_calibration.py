"""Slice 5.13 — Finding severity calibration model and policy tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.findings.correlation import correlate_findings
from codestrata.application.findings.severity_calibration import (
    calibrate_finding_severity,
    classify_repository_context,
)
from codestrata.application.findings.severity_policies import (
    all_severity_policies,
    assert_catalog_covers_registered_rules,
    severity_policy_for_rule,
)
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    FindingSeverityAssessment,
    FindingSeverityBasis,
    SeverityCalibrationStatus,
    compute_threshold_ratio,
)
from codestrata.domain.findings.finding_confidence import (
    FindingConfidence,
    FindingConfidenceBasis,
    FindingConfidenceDerivationStatus,
    FindingConfidenceLevel,
)
from codestrata.domain.findings.severity import RepositoryContextClass


def test_catalog_covers_every_shared_rule_and_unique_policy_ids() -> None:
    assert_catalog_covers_registered_rules()
    policies = all_severity_policies()
    assert len(policies) >= 70
    ids = [item.policy_id for item in policies]
    assert len(ids) == len(set(ids))
    rules = [item.rule_id for item in policies]
    assert len(rules) == len(set(rules))


def test_rule_metadata_gets_severity_policy_id() -> None:
    from codestrata.application.rules.security.helpers import make_metadata
    from codestrata.domain.security.ids import RULE_CREDENTIAL_LITERAL

    meta = make_metadata(
        rule_id=RULE_CREDENTIAL_LITERAL,
        title="Credential literal",
        description="desc",
        remediation="remediate",
    )
    assert meta.severity_policy_id == f"severity.{RULE_CREDENTIAL_LITERAL}"
    assert severity_policy_for_rule(RULE_CREDENTIAL_LITERAL) is not None


def test_threshold_ratio_decimal_safe() -> None:
    assert compute_threshold_ratio(120, 50) == "2.4"
    assert compute_threshold_ratio(0, 0) is None


def test_context_classifier() -> None:
    assert (
        classify_repository_context(("src/service.py",))
        is RepositoryContextClass.PRODUCTION
    )
    assert (
        classify_repository_context(("tests/unit/test_a.py",))
        is RepositoryContextClass.TEST
    )
    assert (
        classify_repository_context(("docs/guide.md",))
        is RepositoryContextClass.DOCUMENTATION
    )


def test_placeholder_lower_than_credential() -> None:
    cred = calibrate_finding_severity(
        rule_id="security.credential-literal",
        emitted_severity=FindingSeverity.HIGH,
        evidence_paths=("src/app.env",),
    )
    placeholder = calibrate_finding_severity(
        rule_id="security.placeholder-credential",
        emitted_severity=FindingSeverity.LOW,
        evidence_paths=("src/app.env",),
    )
    assert cred.severity is FindingSeverity.HIGH
    assert placeholder.severity is FindingSeverity.LOW


def test_test_context_caps_credential() -> None:
    assessment = calibrate_finding_severity(
        rule_id="security.credential-literal",
        emitted_severity=FindingSeverity.HIGH,
        evidence_paths=("tests/fixtures/secrets.env",),
    )
    assert assessment.severity in {
        FindingSeverity.INFORMATIONAL,
        FindingSeverity.LOW,
    }
    assert FindingSeverityBasis.CONTEXT_CAP in assessment.basis


def test_technical_debt_bands() -> None:
    medium = calibrate_finding_severity(
        rule_id="technical_debt.large-callable",
        emitted_severity=FindingSeverity.MEDIUM,
        metadata={"value": "75", "threshold": "50"},
    )
    high = calibrate_finding_severity(
        rule_id="technical_debt.large-callable",
        emitted_severity=FindingSeverity.HIGH,
        metadata={"value": "120", "threshold": "50"},
    )
    assert medium.severity is FindingSeverity.MEDIUM
    assert high.severity is FindingSeverity.HIGH
    assert high.severity is not FindingSeverity.CRITICAL


def test_cloud_and_ai_capped() -> None:
    cloud = calibrate_finding_severity(
        rule_id="cloud.cloud-061",
        emitted_severity=FindingSeverity.LOW,
    )
    ai = calibrate_finding_severity(
        rule_id="ai_readiness.ai-051",
        emitted_severity=FindingSeverity.LOW,
    )
    assert cloud.severity in {FindingSeverity.INFORMATIONAL, FindingSeverity.LOW, FindingSeverity.MEDIUM}
    assert ai.severity in {FindingSeverity.INFORMATIONAL, FindingSeverity.LOW, FindingSeverity.MEDIUM}
    assert FindingSeverity.CRITICAL not in (
        severity_policy_for_rule("cloud.cloud-061").allowed_severities  # type: ignore[union-attr]
    )


def test_enterprise_mismatch_not_high() -> None:
    assessment = calibrate_finding_severity(
        rule_id="architecture.enterprise-standard-mismatch",
        emitted_severity=FindingSeverity.HIGH,
    )
    assert assessment.severity in {
        FindingSeverity.INFORMATIONAL,
        FindingSeverity.LOW,
        FindingSeverity.MEDIUM,
    }
    assert assessment.calibration_status is SeverityCalibrationStatus.PROVISIONAL


def test_confidence_does_not_change_severity() -> None:
    left = calibrate_finding_severity(
        rule_id="dependency.mutable-version",
        emitted_severity=FindingSeverity.MEDIUM,
        metadata={"finding_confidence": "high", "rule_confidence": "high"},
    )
    right = calibrate_finding_severity(
        rule_id="dependency.mutable-version",
        emitted_severity=FindingSeverity.MEDIUM,
        metadata={"finding_confidence": "limited", "rule_confidence": "limited"},
    )
    assert left.severity is right.severity is FindingSeverity.MEDIUM


def test_correlation_does_not_change_severity() -> None:
    a = Finding.create(
        rule_id="security.tls-verification-disabled",
        title="tls",
        description="tls",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("ssl.yml", "verify"),
        evidence=(FindingEvidence(evidence_type="config", source_id="verify", path="ssl.yml"),),
        metadata={"subject_keys": "ssl.yml,verify"},
    )
    b = Finding.create(
        rule_id="security.hostname-verification-disabled",
        title="host",
        description="host",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("ssl.yml", "hostname"),
        evidence=(
            FindingEvidence(evidence_type="config", source_id="hostname", path="ssl.yml"),
        ),
        metadata={"subject_keys": "ssl.yml,hostname"},
    )
    before = {item.id: item.severity for item in (a, b)}
    result = correlate_findings((a, b))
    after = {item.id: item.severity for item in result.findings}
    assert before == after


def test_duplicate_count_metadata_ignored() -> None:
    assessment = calibrate_finding_severity(
        rule_id="dependency.duplicate-declaration",
        emitted_severity=FindingSeverity.LOW,
        metadata={"duplicate_count": "99", "correlation_count": "12"},
    )
    assert assessment.severity is FindingSeverity.LOW


def test_legacy_phase1_preserved() -> None:
    assessment = calibrate_finding_severity(
        rule_id="codestrata-rule-missing-readme",
        emitted_severity=FindingSeverity.LOW,
        legacy=True,
    )
    assert assessment.calibration_status is SeverityCalibrationStatus.LEGACY
    assert assessment.severity is FindingSeverity.LOW


def test_assessment_requires_basis_when_calibrated() -> None:
    with pytest.raises(ValidationError):
        FindingSeverityAssessment(
            severity=FindingSeverity.HIGH,
            basis=(),
            calibration_status=SeverityCalibrationStatus.CALIBRATED,
        )


def test_finding_confidence_independence_on_model() -> None:
    confidence = FindingConfidence(
        level=FindingConfidenceLevel.LIMITED,
        basis=(FindingConfidenceBasis.LIMITED_RULE_CONFIDENCE,),
        limitations=("limited",),
        derivation_status=FindingConfidenceDerivationStatus.DERIVED,
    )
    finding = Finding.create(
        rule_id="security.authentication-disabled",
        title="auth",
        description="auth",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("cfg",),
        finding_confidence=confidence,
    )
    assert finding.severity is FindingSeverity.HIGH
    assert finding.finding_confidence.level is FindingConfidenceLevel.LIMITED
