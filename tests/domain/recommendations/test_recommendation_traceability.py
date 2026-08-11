"""Tests for Recommendation → Finding traceability (Epic 2 Slice 2.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.traceability import (
    merge_recommendation_traceability,
    select_primary_finding_id,
    synthesize_recommendation_traceability,
)
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationType,
    build_recommendation_id,
)
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION


def _action() -> RecommendationAction:
    return RecommendationAction(order=1, title="Act", description="Do the thing")


def _finding(
    *,
    finding_id_suffix: str,
    severity: FindingSeverity,
    confidence: str = "medium",
    rule_id: str = "codestrata-rule-missing-readme",
) -> Finding:
    finding = Finding.create(
        rule_id=rule_id,
        title=f"Finding {finding_id_suffix}",
        description="desc",
        severity=severity,
        category=FindingCategory.DOCUMENTATION,
        subject_keys=(finding_id_suffix,),
        metadata={"confidence": confidence},
    )
    return finding


def test_empty_supporting_findings_remain_legacy() -> None:
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="Add a README",
        rationale="Missing docs",
        priority=RecommendationPriority.MEDIUM,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=(),
        actions=(_action(),),
        subject_keys=("repo",),
    )
    assert recommendation.supporting_finding_ids == ()
    assert recommendation.related_finding_ids == ()
    assert recommendation.primary_finding_id is None
    assert recommendation.recommendation_type is RecommendationType.LEGACY
    assert recommendation.evidence_completeness is EvidenceCompleteness.LEGACY


def test_single_finding_dual_writes_related_and_supporting() -> None:
    finding = _finding(finding_id_suffix="a", severity=FindingSeverity.HIGH)
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="Add a README",
        rationale="Missing docs",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        recommendation_type=RecommendationType.FINDING_BACKED,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=(_action(),),
        subject_keys=(finding.id, "codestrata-rec-missing-readme"),
    )
    assert recommendation.related_finding_ids == recommendation.supporting_finding_ids
    assert recommendation.primary_finding_id == finding.id
    assert recommendation.recommendation_type is RecommendationType.FINDING_BACKED


def test_multiple_findings_select_primary_by_severity_then_confidence() -> None:
    low = _finding(finding_id_suffix="low", severity=FindingSeverity.LOW, confidence="certain")
    high = _finding(finding_id_suffix="high", severity=FindingSeverity.HIGH, confidence="low")
    critical = _finding(
        finding_id_suffix="critical",
        severity=FindingSeverity.CRITICAL,
        confidence="medium",
    )
    primary = select_primary_finding_id((low, high, critical))
    assert primary == critical.id

    same_sev_a = _finding(
        finding_id_suffix="a",
        severity=FindingSeverity.HIGH,
        confidence="medium",
    )
    same_sev_b = _finding(
        finding_id_suffix="b",
        severity=FindingSeverity.HIGH,
        confidence="certain",
    )
    assert select_primary_finding_id((same_sev_a, same_sev_b)) == same_sev_b.id


def test_compatibility_aliases_must_match() -> None:
    with pytest.raises(ValidationError, match="related_finding_ids must match"):
        Recommendation(
            id="recommendation:x:deadbeefdeadbeef",
            title="t",
            summary="s",
            rationale="r",
            priority=RecommendationPriority.LOW,
            category=RecommendationCategory.DOCUMENTATION,
            related_finding_ids=("finding:a",),
            supporting_finding_ids=("finding:b",),
            provider_id="codestrata-rec-missing-readme",
        )


def test_recommendation_id_unchanged_with_traceability_populated() -> None:
    finding_ids = ("finding:a", "finding:b")
    subjects = ("repo", "readme")
    without = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="Add a README",
        rationale="Missing docs",
        priority=RecommendationPriority.MEDIUM,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=finding_ids,
        actions=(_action(),),
        subject_keys=subjects,
    )
    with_trace = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="Add a README",
        rationale="Missing docs",
        priority=RecommendationPriority.MEDIUM,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=finding_ids,
        supporting_finding_ids=finding_ids,
        primary_finding_id="finding:a",
        recommendation_type=RecommendationType.FINDING_BACKED,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        limitations=("note",),
        actions=(_action(),),
        subject_keys=subjects,
    )
    assert without.id == with_trace.id
    assert without.id == build_recommendation_id(
        provider_id="codestrata-rec-missing-readme",
        related_finding_ids=finding_ids,
        subject_keys=subjects,
    )


def test_merge_unions_findings_and_preserves_id() -> None:
    left = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="left",
        rationale="r",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=("finding:a",),
        actions=(_action(),),
        subject_keys=("shared-subject",),
        limitations=("left-limit",),
    )
    right = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="right",
        rationale="r",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=("finding:b",),
        actions=(_action(),),
        subject_keys=("shared-subject",),
        limitations=("right-limit",),
    )
    # Engine merges by identical recommendation.id; force shared id for unit test.
    right = right.model_copy(update={"id": left.id})
    merged = merge_recommendation_traceability(left, right)
    assert merged.id == left.id
    assert merged.supporting_finding_ids == ("finding:a", "finding:b")
    assert merged.related_finding_ids == merged.supporting_finding_ids
    assert "left-limit" in merged.limitations
    assert "right-limit" in merged.limitations
    assert merged.recommendation_type is RecommendationType.MERGED


def test_synthesize_dedupes_and_orders() -> None:
    supporting, primary, rec_type, completeness, _limits = synthesize_recommendation_traceability(
        ("finding:b", "finding:a", "finding:b"),
    )
    assert supporting == ("finding:a", "finding:b")
    assert primary == "finding:a"
    assert rec_type is RecommendationType.FINDING_BACKED
    assert completeness is EvidenceCompleteness.COMPLETE


def test_schema_remains_1_2() -> None:
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
