"""Tests for Phase 3 recommendation domain models."""

from __future__ import annotations

from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationEvidence,
    RecommendationPriority,
    RecommendationSource,
    build_recommendation_id,
)


def test_recommendation_id_is_deterministic() -> None:
    first = build_recommendation_id(
        provider_id="codestrata-rec-missing-readme",
        related_finding_ids=("finding:a", "finding:b"),
        subject_keys=("repo", "readme"),
    )
    second = build_recommendation_id(
        provider_id="codestrata-rec-missing-readme",
        related_finding_ids=("finding:b", "finding:a"),
        subject_keys=("readme", "repo"),
    )
    assert first == second
    assert first.startswith("recommendation:codestrata-rec-missing-readme:")


def test_recommendation_create_round_trip() -> None:
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-missing-license",
        title="Add LICENSE",
        summary="Commit a license file.",
        rationale="Governance requires an explicit license.",
        priority=RecommendationPriority.MEDIUM,
        category=RecommendationCategory.GOVERNANCE,
        related_finding_ids=("finding:codestrata-rule-missing-license:abc",),
        actions=(
            RecommendationAction(
                order=1,
                title="Choose license",
                description="Pick an SPDX license.",
                documentation_ref="https://choosealicense.com/",
            ),
        ),
        evidence=(
            RecommendationEvidence(
                evidence_type="finding",
                source_id="finding:codestrata-rule-missing-license:abc",
            ),
        ),
        subject_keys=("demo", "license"),
    )
    assert recommendation.source is RecommendationSource.FINDING_RULE
    restored = Recommendation.model_validate(recommendation.model_dump(mode="json"))
    assert restored == recommendation
