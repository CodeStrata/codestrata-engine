"""Tests for Recommendation Confidence model and derivation (Slice 5.5)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from codestrata.application.recommendations.confidence import (
    apply_recommendation_confidence,
    derive_recommendation_confidence,
)
from codestrata.application.traceability.recommendation import (
    merge_recommendation_traceability,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity, FindingSource
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
    RecommendationConfidence,
    RecommendationConfidenceBasis,
    RecommendationConfidenceComponents,
    RecommendationConfidenceDerivationStatus,
    RecommendationConfidenceLevel,
    RecommendationPriority,
    RecommendationType,
    recommendation_confidence_to_json,
)
from codestrata.domain.traceability import EvidenceCompleteness


def _finding_confidence(level: FindingConfidenceLevel) -> FindingConfidence:
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


def _finding(
    *,
    finding_id: str,
    level: FindingConfidenceLevel = FindingConfidenceLevel.HIGH,
    category: FindingCategory = FindingCategory.ARCHITECTURE,
    severity: FindingSeverity = FindingSeverity.HIGH,
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id="architecture.layer",
        title=f"Finding {finding_id}",
        description="desc",
        severity=severity,
        category=category,
        source=FindingSource.RULE,
        finding_confidence=_finding_confidence(level),
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )


def _recommendation(
    *,
    finding_ids: tuple[str, ...] = ("f1",),
    rec_type: RecommendationType = RecommendationType.FINDING_BACKED,
    completeness: EvidenceCompleteness = EvidenceCompleteness.COMPLETE,
    priority: RecommendationPriority = RecommendationPriority.HIGH,
) -> Recommendation:
    return Recommendation.create(
        provider_id="test.provider",
        title="Do the thing",
        summary="summary",
        rationale="rationale",
        priority=priority,
        category=RecommendationCategory.MAINTAINABILITY,
        related_finding_ids=finding_ids,
        actions=(
            RecommendationAction(order=1, title="Step", description="Do it"),
        ),
        recommendation_type=rec_type,
        evidence_completeness=completeness,
        primary_finding_id=finding_ids[0] if finding_ids else None,
    )


def test_model_valid_levels_ordering_and_dedupe() -> None:
    confidence = RecommendationConfidence(
        level=RecommendationConfidenceLevel.MODERATE,
        basis=(
            RecommendationConfidenceBasis.MIXED_FINDING_CONFIDENCE,
            RecommendationConfidenceBasis.COMPLETE_FINDING_TRACEABILITY,
        ),
        limitations=("b", "a", "a"),
        derivation_status=RecommendationConfidenceDerivationStatus.DERIVED,
        component_summary=RecommendationConfidenceComponents(
            supporting_finding_count=2,
            high_finding_count=1,
            moderate_finding_count=1,
            weakest_supporting_finding_confidence="moderate",
            primary_finding_confidence="high",
            evidence_completeness="complete",
            traceability_complete=True,
            recommendation_type="merged",
        ),
    )
    assert confidence.basis == (
        RecommendationConfidenceBasis.COMPLETE_FINDING_TRACEABILITY,
        RecommendationConfidenceBasis.MIXED_FINDING_CONFIDENCE,
    )
    assert confidence.limitations == ("a", "b")
    payload = recommendation_confidence_to_json(confidence)
    assert list(payload.keys()) == sorted(payload.keys())


def test_model_rejects_invalid_high_and_legacy() -> None:
    with pytest.raises(ValidationError):
        RecommendationConfidence(
            level=RecommendationConfidenceLevel.HIGH,
            basis=(RecommendationConfidenceBasis.PARTIAL_FINDING_TRACEABILITY,),
            derivation_status=RecommendationConfidenceDerivationStatus.DERIVED,
            component_summary=RecommendationConfidenceComponents(
                traceability_complete=True
            ),
        )
    with pytest.raises(ValidationError):
        RecommendationConfidence(
            level=RecommendationConfidenceLevel.HIGH,
            basis=(RecommendationConfidenceBasis.LEGACY_RECOMMENDATION,),
            derivation_status=RecommendationConfidenceDerivationStatus.UNAVAILABLE,
        )


def test_one_high_finding_yields_high() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("high",),
        primary_finding_level="high",
        supporting_finding_ids=("f1",),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
        assessment_head_ids=("architecture_intelligence",),
    )
    assert result.level is RecommendationConfidenceLevel.HIGH


def test_mixed_and_limited_caps() -> None:
    mixed = derive_recommendation_confidence(
        supporting_finding_levels=("high", "moderate"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
    )
    assert mixed.level is RecommendationConfidenceLevel.MODERATE

    limited = derive_recommendation_confidence(
        supporting_finding_levels=("high", "limited"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
    )
    assert limited.level is RecommendationConfidenceLevel.LIMITED


def test_unavailable_finding_cannot_be_high_or_moderate() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("high", "unavailable"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
    )
    assert result.level is RecommendationConfidenceLevel.LIMITED
    assert (
        RecommendationConfidenceBasis.UNAVAILABLE_SUPPORTING_FINDING in result.basis
    )


def test_missing_and_legacy_unavailable() -> None:
    missing = derive_recommendation_confidence(
        supporting_finding_levels=(),
        supporting_finding_ids=(),
        recommendation_type="finding_backed",
    )
    assert missing.level is RecommendationConfidenceLevel.UNAVAILABLE

    legacy = derive_recommendation_confidence(
        supporting_finding_levels=(),
        supporting_finding_ids=(),
        recommendation_type="legacy",
        evidence_completeness="legacy",
    )
    assert legacy.level is RecommendationConfidenceLevel.UNAVAILABLE
    assert RecommendationConfidenceBasis.LEGACY_RECOMMENDATION in legacy.basis


def test_priority_and_severity_do_not_affect_confidence() -> None:
    high_priority = apply_recommendation_confidence(
        _recommendation(priority=RecommendationPriority.IMMEDIATE),
        findings=(_finding(finding_id="f1", severity=FindingSeverity.CRITICAL),),
    )
    low_priority = apply_recommendation_confidence(
        _recommendation(priority=RecommendationPriority.LOW),
        findings=(_finding(finding_id="f1", severity=FindingSeverity.LOW),),
    )
    assert (
        high_priority.recommendation_confidence.level
        == low_priority.recommendation_confidence.level
        == RecommendationConfidenceLevel.HIGH
    )


def test_stronger_primary_does_not_override_weaker_support() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("limited", "high"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f2",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
    )
    assert result.level is RecommendationConfidenceLevel.LIMITED
    assert result.component_summary.primary_finding_confidence == "high"
    assert result.component_summary.weakest_supporting_finding_confidence == "limited"


def test_merged_recomputes_weakest_and_preserves_id() -> None:
    f1 = _finding(finding_id="f1", level=FindingConfidenceLevel.HIGH)
    f2 = _finding(finding_id="f2", level=FindingConfidenceLevel.LIMITED)
    left = apply_recommendation_confidence(
        _recommendation(finding_ids=("f1",)),
        findings=(f1,),
    )
    right = Recommendation.create(
        provider_id="test.provider",
        title="Do the thing",
        summary="summary",
        rationale="rationale",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.MAINTAINABILITY,
        related_finding_ids=("f2",),
        actions=(
            RecommendationAction(order=1, title="Step", description="Do it"),
        ),
        subject_keys=(),  # may produce different id — merge uses preferred id
    )
    # Force same id for merge identity collision path.
    right = right.model_copy(
        update={
            "id": left.id,
            "supporting_finding_ids": ("f2",),
            "related_finding_ids": ("f2",),
            "primary_finding_id": "f2",
            "recommendation_type": RecommendationType.FINDING_BACKED,
            "evidence_completeness": EvidenceCompleteness.COMPLETE,
        }
    )
    merged = merge_recommendation_traceability(left, right, findings=(f1, f2))
    assert merged.id == left.id
    assert set(merged.supporting_finding_ids) == {"f1", "f2"}
    assert merged.recommendation_type is RecommendationType.MERGED
    assert (
        merged.recommendation_confidence.level is RecommendationConfidenceLevel.LIMITED
    )
    assert (
        RecommendationConfidenceBasis.MERGED_RECOMMENDATION
        in merged.recommendation_confidence.basis
    )


def test_cross_head_basis() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("high", "high"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="finding_backed",
        assessment_head_ids=(
            "architecture_intelligence",
            "security_intelligence",
        ),
    )
    assert result.level is RecommendationConfidenceLevel.HIGH
    assert RecommendationConfidenceBasis.CROSS_HEAD_SUPPORT in result.basis
    assert result.component_summary.assessment_head_count == 2


def test_fact_based_limited_or_unavailable() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("high",),
        supporting_finding_ids=("f1",),
        primary_finding_id="f1",
        primary_finding_level="high",
        evidence_completeness="complete",
        recommendation_type="fact_based",
    )
    assert result.level is RecommendationConfidenceLevel.LIMITED
    assert RecommendationConfidenceBasis.FACT_BASED_RECOMMENDATION in result.basis


def test_json_stable_ordering() -> None:
    result = derive_recommendation_confidence(
        supporting_finding_levels=("high", "moderate"),
        primary_finding_level="high",
        supporting_finding_ids=("f1", "f2"),
        primary_finding_id="f1",
        evidence_completeness="complete",
        recommendation_type="merged",
    )
    payload = recommendation_confidence_to_json(result)
    encoded = json.dumps(payload, sort_keys=True)
    assert '"level": "moderate"' in encoded
    assert list(payload.keys()) == sorted(payload.keys())
