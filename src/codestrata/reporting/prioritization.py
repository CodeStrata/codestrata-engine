"""Deterministic recommendation prioritization (Phase 7.1.3).

Presentation-layer scoring over the customer recommendation universe.
No AI. Uses only existing recommendation and finding metadata.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.reporting.customer_universe import (
    CustomerFinding,
    CustomerRecommendation,
)

# Fixed weights — documented for explainability; keep stable across releases.
_SEVERITY_POINTS = {
    "critical": 100,
    "high": 80,
    "medium": 50,
    "low": 25,
    "informational": 0,
    "info": 0,
}
_PRIORITY_POINTS = {
    "immediate": 40,
    "critical": 40,
    "high": 30,
    "medium": 15,
    "low": 5,
}
_RISK_POINTS = {
    "high": 20,
    "medium": 10,
    "low": 5,
    "unknown": 8,
}
# Smaller effort scores higher so comparable risks prefer quicker wins.
_EFFORT_POINTS = {
    "small": 15,
    "xs": 15,
    "s": 15,
    "medium": 10,
    "m": 10,
    "large": 5,
    "l": 5,
    "extra_large": 0,
    "xl": 0,
    "unknown": 8,
}
_CATEGORY_POINTS = {
    "security": 8,
    "testing": 6,
    "operational_readiness": 6,
    "dependency": 5,
    "architecture": 4,
    "maintainability": 3,
    "cloud_readiness": 3,
    "performance": 2,
    "ai_readiness": 2,
}

# Bucket thresholds on the composite score.
_IMMEDIATE_MIN = 140.0
_NEAR_TERM_MIN = 80.0

BUCKET_IMMEDIATE = "immediate"
BUCKET_NEAR_TERM = "near_term"
BUCKET_FUTURE = "future"

BUCKET_LABELS = {
    BUCKET_IMMEDIATE: "Immediate",
    BUCKET_NEAR_TERM: "Near Term",
    BUCKET_FUTURE: "Future",
}


def compute_priority_score(
    recommendation: CustomerRecommendation,
    *,
    finding_severity_by_id: Mapping[str, str],
) -> float:
    """Compute a deterministic priority score for one recommendation."""

    severities = [
        finding_severity_by_id[fid]
        for fid in recommendation.related_finding_ids
        if fid in finding_severity_by_id
    ]
    if severities:
        severity_points = max(_SEVERITY_POINTS.get(_norm(s), 0) for s in severities)
    else:
        # Ungrounded recommendations stay low so they sort after finding-backed ones.
        severity_points = 0

    priority_points = _PRIORITY_POINTS.get(_norm(recommendation.priority), 5)
    risk_points = _RISK_POINTS.get(_norm(recommendation.risk), 8)
    effort_points = _EFFORT_POINTS.get(_norm(recommendation.effort), 8)
    category_points = _CATEGORY_POINTS.get(_norm(recommendation.category), 1)

    # Dependencies delay work: each listed dependency soft-penalizes ordering.
    dependency_penalty = min(20, 5 * len(recommendation.dependencies))

    # Breadth: more related findings → slightly higher (capped).
    breadth_points = min(10, 2 * len(recommendation.related_finding_ids))

    return float(
        severity_points
        + priority_points
        + risk_points
        + effort_points
        + category_points
        + breadth_points
        - dependency_penalty
    )


def presentation_bucket_for_score(score: float) -> str:
    """Map a score onto Immediate / Near Term / Future buckets."""

    if score >= _IMMEDIATE_MIN:
        return BUCKET_IMMEDIATE
    if score >= _NEAR_TERM_MIN:
        return BUCKET_NEAR_TERM
    return BUCKET_FUTURE


def prioritize_customer_recommendations(
    recommendations: Sequence[CustomerRecommendation],
    findings: Sequence[CustomerFinding],
) -> tuple[CustomerRecommendation, ...]:
    """Return recommendations scored and sorted highest-value first."""

    severity_by_id = {item.id: item.severity for item in findings}
    scored: list[CustomerRecommendation] = []
    for item in recommendations:
        score = compute_priority_score(
            item,
            finding_severity_by_id=severity_by_id,
        )
        bucket = presentation_bucket_for_score(score)
        scored.append(
            CustomerRecommendation(
                id=item.id,
                rule_id=item.rule_id,
                title=item.title,
                description=item.description,
                rationale=item.rationale,
                priority=item.priority,
                category=item.category,
                effort=item.effort,
                risk=item.risk,
                related_finding_ids=item.related_finding_ids,
                actions=item.actions,
                dependencies=item.dependencies,
                evidence=item.evidence,
                phase1=item.phase1,
                priority_score=score,
                presentation_bucket=bucket,
            )
        )

    scored.sort(
        key=lambda item: (
            -item.priority_score,
            _priority_tiebreak(item.priority),
            item.category.lower(),
            item.title.lower(),
            item.id,
        )
    )
    return tuple(scored)


def grounded_recommendations(
    recommendations: Sequence[CustomerRecommendation],
) -> tuple[CustomerRecommendation, ...]:
    """Priority Actions require at least one related deterministic finding."""

    return tuple(item for item in recommendations if item.related_finding_ids)


def _norm(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _priority_tiebreak(priority: str) -> int:
    order = {
        "immediate": 0,
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return order.get(_norm(priority), 9)


__all__ = [
    "BUCKET_FUTURE",
    "BUCKET_IMMEDIATE",
    "BUCKET_LABELS",
    "BUCKET_NEAR_TERM",
    "compute_priority_score",
    "grounded_recommendations",
    "presentation_bucket_for_score",
    "prioritize_customer_recommendations",
]
