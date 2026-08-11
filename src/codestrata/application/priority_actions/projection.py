"""Project PriorityAction onto existing HTML RecommendationView (no HTML redesign)."""

from __future__ import annotations

from codestrata.domain.priority_actions import PriorityAction
from codestrata.reporting.html_v2.models import RecommendationView


def priority_action_to_recommendation_view(
    action: PriorityAction,
    *,
    related_finding_titles: tuple[str, ...] = (),
    supporting_recommendation_titles: tuple[str, ...] = (),
) -> RecommendationView:
    """Preserve presentation IDs: recommendation_id == action_id == primary rec ID."""

    return RecommendationView(
        recommendation_id=action.action_id,
        title=action.title,
        summary=action.summary,
        rationale=action.rationale or action.summary,
        priority=action.priority,
        category=action.category,
        related_finding_ids=action.supporting_finding_ids,
        related_finding_titles=related_finding_titles,
        effort=action.effort,
        risk=action.risk,
        priority_score=action.priority_score,
        presentation_bucket=action.presentation_bucket,
        evidence_completeness=action.evidence_completeness.value,
        limitations=tuple(action.limitations),
        supporting_recommendation_ids=tuple(action.supporting_recommendation_ids),
        supporting_recommendation_titles=supporting_recommendation_titles,
        primary_recommendation_id=action.primary_recommendation_id,
        action_type=action.action_type.value,
        recommendation_type="priority_action",
    )
