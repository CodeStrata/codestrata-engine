"""Slice 5.14 — Recommendation priority calibration tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.recommendations.priority_calibration import (
    apply_recommendation_priority,
    calibrate_recommendation_priority,
    presentation_bucket_for_calibrated_score,
)
from codestrata.application.recommendations.priority_policies import (
    all_priority_policies,
    assert_builtin_providers_covered,
    resolve_priority_policy,
)
from codestrata.application.traceability.recommendation import (
    merge_recommendation_traceability,
    select_primary_finding_id,
)
from codestrata.domain.findings import Finding, FindingCategory, FindingSeverity
from codestrata.domain.findings.finding_confidence import (
    FindingConfidence,
    FindingConfidenceBasis,
    FindingConfidenceComponents,
    FindingConfidenceDerivationStatus,
    FindingConfidenceLevel,
)
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
)
from codestrata.domain.recommendations.enums import RecommendationType
from codestrata.domain.recommendations.priority import (
    BAND_HIGH_MIN,
    BAND_IMMEDIATE_MIN,
    BAND_MEDIUM_MIN,
    PRIORITY_SCORE_MAX,
    PriorityCalibrationStatus,
    RecommendationPriorityAssessment,
    RecommendationPriorityBasis,
    priority_for_score,
)
from codestrata.domain.recommendations.recommendation_confidence import (
    RecommendationConfidence,
    RecommendationConfidenceBasis,
    RecommendationConfidenceComponents,
    RecommendationConfidenceDerivationStatus,
    RecommendationConfidenceLevel,
)
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.services.recommendations.providers.builtin import (
    builtin_recommendation_providers,
)


def _confidence(
    level: FindingConfidenceLevel = FindingConfidenceLevel.HIGH,
) -> FindingConfidence:
    if level is FindingConfidenceLevel.UNAVAILABLE:
        return FindingConfidence.unavailable()
    basis = (
        FindingConfidenceBasis.HIGH_RULE_CONFIDENCE
        if level is FindingConfidenceLevel.HIGH
        else FindingConfidenceBasis.MODERATE_RULE_CONFIDENCE
        if level is FindingConfidenceLevel.MODERATE
        else FindingConfidenceBasis.PARTIAL_EVIDENCE
    )
    return FindingConfidence(
        level=level,
        basis=(basis,),
        limitations=("fixture",),
        derivation_status=FindingConfidenceDerivationStatus.DERIVED,
        component_summary=FindingConfidenceComponents(
            evidence_completeness="complete",
            traceability_complete=True,
        ),
    )


def _rec_confidence(
    level: RecommendationConfidenceLevel = RecommendationConfidenceLevel.HIGH,
) -> RecommendationConfidence:
    if level is RecommendationConfidenceLevel.UNAVAILABLE:
        return RecommendationConfidence.unavailable()
    return RecommendationConfidence(
        level=level,
        basis=(RecommendationConfidenceBasis.SINGLE_SUPPORTING_FINDING,),
        limitations=("fixture",),
        derivation_status=RecommendationConfidenceDerivationStatus.DERIVED,
        component_summary=RecommendationConfidenceComponents(
            evidence_completeness="complete",
            traceability_complete=True,
            supporting_finding_count=1,
        ),
    )


def _finding(
    *,
    finding_id: str = "f1",
    severity: FindingSeverity = FindingSeverity.HIGH,
    confidence: FindingConfidenceLevel = FindingConfidenceLevel.HIGH,
    rule_id: str = "security.credential-literal",
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title="Finding",
        description="desc",
        severity=severity,
        category=FindingCategory.SECURITY,
        evidence=(),
        subject_keys=(finding_id,),
        finding_confidence=_confidence(confidence),
    )


def _recommendation(
    *,
    provider_id: str = "codestrata-rec-missing-readme",
    finding: Finding | None = None,
    priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    confidence: RecommendationConfidenceLevel = RecommendationConfidenceLevel.HIGH,
    recommendation_type: RecommendationType = RecommendationType.FINDING_BACKED,
) -> Recommendation:
    finding = finding or _finding()
    return Recommendation.create(
        provider_id=provider_id,
        title="Action",
        summary="summary",
        rationale="rationale",
        priority=priority,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        recommendation_type=recommendation_type,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        recommendation_confidence=_rec_confidence(confidence),
        actions=(
            RecommendationAction(order=1, title="Do", description="Do it"),
        ),
    )


def test_catalog_covers_builtin_providers_and_unique_ids() -> None:
    assert_builtin_providers_covered({p.id() for p in builtin_recommendation_providers()})
    policies = all_priority_policies()
    ids = [item.policy_id for item in policies]
    assert len(ids) == len(set(ids))
    providers = [item.provider_id for item in policies]
    assert len(providers) == len(set(providers))


def test_score_bands_and_assessment_validation() -> None:
    assert priority_for_score(95) is RecommendationPriority.IMMEDIATE
    assert priority_for_score(80) is RecommendationPriority.HIGH
    assert priority_for_score(50) is RecommendationPriority.MEDIUM
    assert priority_for_score(10) is RecommendationPriority.LOW
    with pytest.raises(ValidationError):
        RecommendationPriorityAssessment(
            priority=RecommendationPriority.HIGH,
            score=95,
            basis=(RecommendationPriorityBasis.EXPLICIT_POLICY,),
            calibration_status=PriorityCalibrationStatus.CALIBRATED,
        )


def test_priority_not_equal_to_severity() -> None:
    finding = _finding(severity=FindingSeverity.HIGH)
    rec = _recommendation(
        provider_id="codestrata-rec-missing-readme",
        finding=finding,
        priority=RecommendationPriority.HIGH,
    )
    assessment = calibrate_recommendation_priority(rec, findings=(finding,))
    assert assessment.priority is not RecommendationPriority.IMMEDIATE
    assert assessment.priority is RecommendationPriority.LOW or assessment.score < BAND_HIGH_MIN
    assert assessment.priority is RecommendationPriority.MEDIUM or assessment.score < BAND_HIGH_MIN


def test_recommendation_confidence_caps_urgency() -> None:
    finding = _finding(severity=FindingSeverity.CRITICAL)
    high = _recommendation(
        provider_id="codestrata-rec-correlation-transport-verification",
        finding=finding,
        confidence=RecommendationConfidenceLevel.HIGH,
    )
    limited = _recommendation(
        provider_id="codestrata-rec-correlation-transport-verification",
        finding=finding,
        confidence=RecommendationConfidenceLevel.LIMITED,
    )
    high_a = calibrate_recommendation_priority(high, findings=(finding,))
    limited_a = calibrate_recommendation_priority(limited, findings=(finding,))
    assert high_a.score >= limited_a.score
    assert limited_a.priority in {
        RecommendationPriority.MEDIUM,
        RecommendationPriority.LOW,
        RecommendationPriority.HIGH,
    }
    assert limited_a.priority is not RecommendationPriority.IMMEDIATE
    assert RecommendationPriorityBasis.CONFIDENCE_CAP in limited_a.basis or limited_a.score < BAND_IMMEDIATE_MIN


def test_title_does_not_affect_priority() -> None:
    finding = _finding()
    left = _recommendation(finding=finding).model_copy(update={"title": "URGENT CRITICAL NOW"})
    right = _recommendation(finding=finding).model_copy(update={"title": "mild note"})
    assert calibrate_recommendation_priority(left, findings=(finding,)).score == (
        calibrate_recommendation_priority(right, findings=(finding,)).score
    )


def test_precision_recall_fp_fn_do_not_affect_priority() -> None:
    finding = _finding()
    rec = _recommendation(finding=finding)
    baseline = calibrate_recommendation_priority(rec, findings=(finding,))
    noisy = rec.model_copy(
        update={
            "metadata": {
                "precision": 0.1,
                "recall": 0.9,
                "false_positive_count": 99,
                "false_negative_count": 99,
                "duplicate_count": 50,
                "correlation_count": 50,
            }
        }
    )
    assert calibrate_recommendation_priority(noisy, findings=(finding,)).score == baseline.score


def test_legacy_is_conservative() -> None:
    legacy = Recommendation.create(
        provider_id="unknown-legacy",
        title="Legacy",
        summary="s",
        rationale="r",
        priority=RecommendationPriority.IMMEDIATE,
        category=RecommendationCategory.UNKNOWN,
        related_finding_ids=(),
        actions=(RecommendationAction(order=1, title="x", description="y"),),
        recommendation_type=RecommendationType.LEGACY,
        evidence_completeness=EvidenceCompleteness.LEGACY,
        recommendation_confidence=_rec_confidence(RecommendationConfidenceLevel.UNAVAILABLE),
    )
    assessment = calibrate_recommendation_priority(legacy, findings=())
    assert assessment.calibration_status is PriorityCalibrationStatus.LEGACY
    assert assessment.priority is not RecommendationPriority.IMMEDIATE
    assert assessment.score < BAND_IMMEDIATE_MIN


def test_correlation_aware_bounded_adjustment() -> None:
    f1 = _finding(finding_id="a", rule_id="security.tls-verification-disabled")
    f2 = _finding(
        finding_id="b",
        rule_id="security.hostname-verification-disabled",
        severity=FindingSeverity.HIGH,
    )
    rec = Recommendation.create(
        provider_id="codestrata-rec-correlation-transport-verification",
        title="Restore transport verification controls",
        summary="s",
        rationale="r",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.MODERNIZATION,
        related_finding_ids=(f1.id, f2.id),
        supporting_finding_ids=(f1.id, f2.id),
        primary_finding_id=f1.id,
        recommendation_confidence=_rec_confidence(),
        actions=(RecommendationAction(order=1, title="x", description="y"),),
        metadata={"correlation_aware": "true"},
    )
    assessment = calibrate_recommendation_priority(rec, findings=(f1, f2))
    assert RecommendationPriorityBasis.CORRELATED_SUPPORTING_FINDINGS in assessment.basis
    assert assessment.component_summary.correlation_count >= 1
    # Unrelated correlation count metadata must not inflate further.
    noisy = rec.model_copy(update={"metadata": {"correlation_aware": "true", "correlation_count": 99}})
    noisy_a = calibrate_recommendation_priority(noisy, findings=(f1, f2))
    assert noisy_a.score == assessment.score


def test_merge_recomputes_priority_and_rejects_incompatible_policies() -> None:
    finding = _finding()
    left = apply_recommendation_priority(
        _recommendation(
            provider_id="codestrata-rec-missing-readme",
            finding=finding,
            confidence=RecommendationConfidenceLevel.HIGH,
        ),
        findings=(finding,),
    )
    right = left.model_copy(
        update={
            "recommendation_confidence": _rec_confidence(RecommendationConfidenceLevel.LIMITED),
        }
    )
    merged = merge_recommendation_traceability(left, right, findings=(finding,))
    assert merged.id == left.id
    assert merged.priority_assessment is not None
    assert merged.priority_assessment.score <= left.priority_assessment.score  # type: ignore[union-attr]

    other = apply_recommendation_priority(
        _recommendation(
            provider_id="codestrata-rec-large-repository",
            finding=finding,
        ),
        findings=(finding,),
    )
    with pytest.raises(ValueError, match="incompatible recommendation priority policies"):
        merge_recommendation_traceability(left, other, findings=(finding,))


def test_primary_finding_uses_finding_confidence_not_match_evidence() -> None:
    weak = _finding(
        finding_id="weak",
        severity=FindingSeverity.HIGH,
        confidence=FindingConfidenceLevel.LIMITED,
    )
    strong = _finding(
        finding_id="strong",
        severity=FindingSeverity.HIGH,
        confidence=FindingConfidenceLevel.HIGH,
        rule_id="security.hostname-verification-disabled",
    )
    # Metadata match-evidence would prefer weak if still used; Finding Confidence prefers strong.
    weak = weak.model_copy(update={"metadata": {"confidence": "certain"}})
    primary = select_primary_finding_id((weak, strong))
    assert primary == strong.id


def test_apply_sets_assessment_and_projects_priority() -> None:
    finding = _finding(severity=FindingSeverity.LOW)
    rec = _recommendation(
        provider_id="codestrata-rec-large-repository",
        finding=finding,
        priority=RecommendationPriority.HIGH,
    )
    updated = apply_recommendation_priority(rec, findings=(finding,))
    assert updated.priority_assessment is not None
    assert updated.priority is RecommendationPriority.LOW
    assert updated.priority_assessment.policy_id == "priority.technical_debt.large-repository"


def test_presentation_buckets_from_calibrated_score() -> None:
    assert presentation_bucket_for_calibrated_score(95) == "immediate"
    assert presentation_bucket_for_calibrated_score(75) == "near_term"
    assert presentation_bucket_for_calibrated_score(20) == "future"
    assert BAND_MEDIUM_MIN == 40
    assert BAND_HIGH_MIN == 70
    assert BAND_IMMEDIATE_MIN == 90
    assert PRIORITY_SCORE_MAX == 100


def test_resolve_finding_backed_compatibility_for_unknown_provider() -> None:
    policy = resolve_priority_policy(
        None,
        recommendation_type="finding_backed",
        has_supporting_findings=True,
    )
    assert policy.policy_id == "priority.finding_backed.compatibility"
    legacy = resolve_priority_policy(None, recommendation_type="legacy", has_supporting_findings=False)
    assert legacy.policy_id == "priority.legacy.compatibility"
