"""Customer projection tests for recommendation finding traceability."""

from __future__ import annotations

from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
    RecommendationType,
)
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.reporting.customer_universe import (
    customer_recommendation_json,
    merge_customer_recommendations,
)


def test_phase3_customer_projection_preserves_supporting_and_related() -> None:
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-missing-readme",
        title="Add README",
        summary="Create README",
        rationale="Docs missing",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.DOCUMENTATION,
        related_finding_ids=("finding:a", "finding:b"),
        supporting_finding_ids=("finding:a", "finding:b"),
        primary_finding_id="finding:a",
        recommendation_type=RecommendationType.FINDING_BACKED,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        limitations=("note",),
        actions=(
            RecommendationAction(order=1, title="Draft", description="Write README"),
        ),
        subject_keys=("repo",),
    )
    result = RecommendationResult.from_recommendations(
        recommendations=(recommendation,),
        providers_evaluated=("codestrata-rec-missing-readme",),
    )
    merged = merge_customer_recommendations((), result=result)
    assert len(merged) == 1
    customer = merged[0]
    assert customer.related_finding_ids == ("finding:a", "finding:b")
    assert customer.supporting_finding_ids == ("finding:a", "finding:b")
    assert customer.primary_finding_id == "finding:a"
    payload = customer_recommendation_json(customer)
    assert payload["related_finding_ids"] == ["finding:a", "finding:b"]
    assert payload["supporting_finding_ids"] == ["finding:a", "finding:b"]
    assert payload["primary_finding_id"] == "finding:a"
    assert payload["recommendation_type"] == "finding_backed"
