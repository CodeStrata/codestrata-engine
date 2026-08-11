"""Build Priority Actions from Recommendations (Epic 2 Slice 2.4).

Authority rule: every deterministic Priority Action originates from at least
one Recommendation. Findings without Recommendations are never fabricated into
Priority Actions here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from codestrata.domain.priority_actions import PriorityAction, PriorityActionType
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.domain.traceability.validators import merge_unique_sorted, normalize_limitations


class RecommendationLike(Protocol):
    """Minimal recommendation shape consumed by Priority Action mapping."""

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def rationale(self) -> str: ...

    @property
    def priority(self) -> str: ...

    @property
    def category(self) -> str: ...

    @property
    def effort(self) -> str: ...

    @property
    def risk(self) -> str: ...

    @property
    def related_finding_ids(self) -> tuple[str, ...]: ...

    @property
    def priority_score(self) -> float: ...

    @property
    def presentation_bucket(self) -> str: ...


_PRIORITY_RANK = {
    "immediate": 0,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _recommendation_id(item: RecommendationLike) -> str:
    return str(getattr(item, "id", None) or getattr(item, "recommendation_id", "")).strip()


def _description(item: RecommendationLike) -> str:
    return str(
        getattr(item, "description", None)
        or getattr(item, "summary", None)
        or item.title
    ).strip()


def _supporting_finding_ids(item: RecommendationLike) -> tuple[str, ...]:
    supporting = getattr(item, "supporting_finding_ids", None)
    if supporting:
        return tuple(str(value) for value in supporting)
    return tuple(str(value) for value in item.related_finding_ids)


def _limitations(item: RecommendationLike) -> tuple[str, ...]:
    raw = getattr(item, "limitations", ()) or ()
    return tuple(str(value) for value in raw)


def _completeness(item: RecommendationLike) -> EvidenceCompleteness:
    raw = getattr(item, "evidence_completeness", None)
    if isinstance(raw, EvidenceCompleteness):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return EvidenceCompleteness(raw.strip().lower())
        except ValueError:
            pass
    findings = _supporting_finding_ids(item)
    return EvidenceCompleteness.COMPLETE if findings else EvidenceCompleteness.PARTIAL


def _confidence_rank(item: RecommendationLike) -> int:
    """Higher is better. Prefer explicit confidence; else infer from score."""

    metadata = getattr(item, "metadata", None) or {}
    if isinstance(metadata, dict):
        raw = str(metadata.get("confidence", "")).lower()
        ranks = {"certain": 3, "high": 2, "medium": 1, "low": 0}
        if raw in ranks:
            return ranks[raw]
    score = float(getattr(item, "priority_score", 0.0) or 0.0)
    # Support both calibrated 0–100 scores and legacy composite scores.
    if score >= 140 or (score <= 100 and score >= 90):
        return 3
    if score >= 80 or (score <= 100 and score >= 70):
        return 2
    if score >= 40:
        return 1
    return 0


def select_primary_recommendation_id(
    recommendations: Sequence[RecommendationLike],
) -> str | None:
    """Select primary: priority → confidence → score → recommendation ID."""

    if not recommendations:
        return None

    def sort_key(item: RecommendationLike) -> tuple[object, ...]:
        return (
            _PRIORITY_RANK.get(str(item.priority).lower(), 99),
            -_confidence_rank(item),
            -float(item.priority_score or 0.0),
            _recommendation_id(item),
        )

    return _recommendation_id(sorted(recommendations, key=sort_key)[0])


def derive_evidence_completeness(
    recommendations: Sequence[RecommendationLike],
) -> EvidenceCompleteness:
    """Derive completeness from referenced recommendations — never invent it."""

    if not recommendations:
        return EvidenceCompleteness.UNAVAILABLE
    values = [_completeness(item) for item in recommendations]
    if all(item is EvidenceCompleteness.COMPLETE for item in values):
        return EvidenceCompleteness.COMPLETE
    if any(item is EvidenceCompleteness.COMPLETE for item in values):
        return EvidenceCompleteness.PARTIAL
    if all(item is EvidenceCompleteness.LEGACY for item in values):
        return EvidenceCompleteness.LEGACY
    if any(item is EvidenceCompleteness.UNAVAILABLE for item in values):
        return EvidenceCompleteness.PARTIAL
    return EvidenceCompleteness.PARTIAL


def priority_action_from_recommendation(recommendation: RecommendationLike) -> PriorityAction:
    """Map one grounded Recommendation onto a Priority Action."""

    finding_ids = _supporting_finding_ids(recommendation)
    if not finding_ids:
        raise ValueError(
            "Priority Actions require recommendation finding traceability "
            f"(recommendation_id={_recommendation_id(recommendation)!r})"
        )
    summary = _description(recommendation) or recommendation.rationale or recommendation.title
    return PriorityAction.create(
        title=recommendation.title,
        summary=summary,
        priority=str(recommendation.priority),
        supporting_recommendation_ids=(_recommendation_id(recommendation),),
        supporting_finding_ids=finding_ids,
        primary_recommendation_id=_recommendation_id(recommendation),
        priority_score=float(recommendation.priority_score or 0.0),
        effort=str(recommendation.effort or "unknown"),
        presentation_bucket=str(recommendation.presentation_bucket or "future"),
        action_type=PriorityActionType.RECOMMENDATION_BACKED,
        evidence_completeness=_completeness(recommendation),
        limitations=_limitations(recommendation),
        category=str(recommendation.category or "unknown"),
        rationale=str(recommendation.rationale or ""),
        risk=str(recommendation.risk or "medium"),
    )


def merge_priority_actions(
    preferred: PriorityAction,
    other: PriorityAction,
    *,
    recommendations: Sequence[RecommendationLike] = (),
) -> PriorityAction:
    """Union recommendation/finding traceability without changing presentation intent.

    Reselects primary recommendation deterministically. Does not invent findings.
    """

    by_id = {_recommendation_id(item): item for item in recommendations}
    supporting_recs = merge_unique_sorted(
        preferred.supporting_recommendation_ids,
        other.supporting_recommendation_ids,
    )
    # Findings are always derived from referenced recommendations when available.
    if by_id:
        finding_ids: tuple[str, ...] = ()
        for rec_id in supporting_recs:
            if rec_id not in by_id:
                continue
            finding_ids = merge_unique_sorted(finding_ids, _supporting_finding_ids(by_id[rec_id]))
        source_recs = tuple(by_id[rec_id] for rec_id in supporting_recs if rec_id in by_id)
        primary = select_primary_recommendation_id(source_recs) or preferred.primary_recommendation_id
        completeness = derive_evidence_completeness(source_recs)
    else:
        finding_ids = merge_unique_sorted(
            preferred.supporting_finding_ids,
            other.supporting_finding_ids,
        )
        primary = preferred.primary_recommendation_id or other.primary_recommendation_id
        if primary not in supporting_recs and supporting_recs:
            primary = supporting_recs[0]
        completeness = (
            EvidenceCompleteness.COMPLETE
            if preferred.evidence_completeness is EvidenceCompleteness.COMPLETE
            and other.evidence_completeness is EvidenceCompleteness.COMPLETE
            else EvidenceCompleteness.PARTIAL
        )
    limits = normalize_limitations((*preferred.limitations, *other.limitations))
    # Prefer higher-ranked presentation fields from preferred (already sorted upstream).
    return preferred.model_copy(
        update={
            "action_id": primary or preferred.action_id,
            "supporting_recommendation_ids": supporting_recs,
            "primary_recommendation_id": primary,
            "supporting_finding_ids": finding_ids,
            "action_type": PriorityActionType.MERGED,
            "evidence_completeness": completeness,
            "limitations": limits,
        }
    )


def build_priority_actions(
    recommendations: Sequence[RecommendationLike],
    *,
    max_actions: int = 8,
) -> tuple[PriorityAction, ...]:
    """Build recommendation-backed Priority Actions.

    Skips recommendations without finding links. Does not fabricate actions from
    Findings. Merges duplicate action IDs by unioning traceability.
    """

    grounded = [
        item
        for item in recommendations
        if _supporting_finding_ids(item) and _recommendation_id(item)
    ]
    by_id: dict[str, PriorityAction] = {}
    order: list[str] = []
    for item in grounded:
        action = priority_action_from_recommendation(item)
        existing = by_id.get(action.action_id)
        if existing is None:
            by_id[action.action_id] = action
            order.append(action.action_id)
            continue
        by_id[action.action_id] = merge_priority_actions(
            existing,
            action,
            recommendations=grounded,
        )

    ordered = [by_id[action_id] for action_id in order]
    ordered.sort(
        key=lambda item: (
            _bucket_rank(item.presentation_bucket),
            -float(item.priority_score or 0.0),
            _PRIORITY_RANK.get(str(item.priority).lower(), 99),
            item.title.lower(),
            item.action_id,
        )
    )
    return tuple(ordered[:max_actions])


def _bucket_rank(bucket: str) -> int:
    order = {"immediate": 0, "near_term": 1, "future": 2}
    return order.get(str(bucket).lower(), 99)
