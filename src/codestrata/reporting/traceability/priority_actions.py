"""Build and serialize assessment.priority_actions from Recommendations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.domain.priority_actions import PriorityAction
from codestrata.reporting.customer_universe import CustomerRecommendation


def build_assessment_priority_actions(
    recommendations: Sequence[CustomerRecommendation],
) -> tuple[PriorityAction, ...]:
    """Build canonical Priority Actions from customer recommendations.

    Never synthesizes actions from Findings. Ungrounded recommendations are
    skipped by ``build_priority_actions``.
    """

    # Lazy import avoids reporting ↔ application circular import at package load.
    from codestrata.application.priority_actions import build_priority_actions

    grounded = tuple(
        item
        for item in recommendations
        if (item.supporting_finding_ids or item.related_finding_ids)
    )
    if not grounded:
        return ()
    # Canonical report.json must not truncate Priority Actions the way HTML
    # presentation (max 8) does — preserve every grounded recommendation ref.
    return build_priority_actions(grounded, max_actions=len(grounded))


def serialize_priority_actions(actions: Sequence[PriorityAction]) -> list[dict[str, Any]]:
    """Serialize PriorityAction models for assessment.priority_actions."""

    payload: list[dict[str, Any]] = []
    for action in actions:
        payload.append(
            {
                "action_id": action.action_id,
                "title": action.title,
                "summary": action.summary,
                "priority": action.priority,
                "priority_score": round(float(action.priority_score), 2),
                "effort": action.effort,
                "presentation_bucket": action.presentation_bucket,
                "category": action.category,
                "rationale": action.rationale,
                "risk": action.risk,
                "action_type": action.action_type.value,
                "supporting_recommendation_ids": list(action.supporting_recommendation_ids),
                "primary_recommendation_id": action.primary_recommendation_id,
                "supporting_finding_ids": list(action.supporting_finding_ids),
                "evidence_completeness": action.evidence_completeness.value,
                "limitations": list(action.limitations),
            }
        )
    return payload
