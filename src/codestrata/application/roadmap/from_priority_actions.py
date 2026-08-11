"""Authoritative Roadmap builder from Priority Actions (Epic 2 Slice 2.5).

Chain: Priority Action → Roadmap Initiative → Recommendation / Finding (derived).

Does not invent Recommendation or Finding relationships independently of
referenced Priority Actions. Does not create initiatives from Findings or
Recommendations alone.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.application.roadmap.mapping import (
    map_effort,
    map_priority,
    map_risk,
    normalize_category,
    prerequisite_phases,
)
from codestrata.domain.priority_actions import PriorityAction
from codestrata.domain.roadmap.constants import (
    PHASE_OBJECTIVES,
    PHASE_OUTCOMES,
    PHASE_SEQUENCE,
    PHASE_TITLES,
)
from codestrata.domain.roadmap.enums import (
    RoadmapConfidence,
    RoadmapInitiativeType,
    RoadmapPhaseName,
    RoadmapStatus,
)
from codestrata.domain.roadmap.identifiers import (
    ENGINE_VERSION,
    build_initiative_id,
    build_phase_id,
)
from codestrata.domain.roadmap.models import (
    RoadmapAssessmentSection,
    RoadmapInitiative,
    RoadmapPhasePlan,
)
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.domain.traceability.validators import merge_unique_sorted, normalize_limitations

_ASSUMPTIONS = (
    "Roadmap initiatives are derived from Priority Actions; assessments are not re-run.",
    "Recommendation and Finding references are derived from referenced Priority Actions.",
    "Phase assignment follows Priority Action horizon and category rules.",
)

_BASE_LIMITATIONS = (
    "Does not produce schedules, dates, cost estimates, or portfolio plans.",
    "Does not mutate repositories or create external tracker tickets.",
    "Does not invent Priority Actions, Recommendations, or Findings.",
)

_PRIORITY_RANK = {
    "immediate": 0,
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

_COMPLETENESS_RANK = {
    EvidenceCompleteness.COMPLETE: 0,
    EvidenceCompleteness.PARTIAL: 1,
    EvidenceCompleteness.TRUNCATED: 2,
    EvidenceCompleteness.LEGACY: 3,
    EvidenceCompleteness.UNAVAILABLE: 4,
}

_PHASE_RANK = {phase: index for index, phase in enumerate(PHASE_SEQUENCE)}


def map_phase_for_priority_action(action: PriorityAction) -> RoadmapPhaseName:
    """Horizon-first phase so roadmap order matches Priority Action sequencing."""

    bucket = (action.presentation_bucket or "").strip().lower()
    category = action.category.strip().lower().replace(" ", "_").replace("-", "_")
    if category == "security":
        return RoadmapPhaseName.SECURE
    if category == "performance":
        return RoadmapPhaseName.OPTIMIZE
    if bucket in {"immediate", "near_term"}:
        return RoadmapPhaseName.STABILIZE
    if category in {
        "testing",
        "ci_cd",
        "build",
        "docs",
        "documentation",
        "governance",
        "configuration",
    }:
        return RoadmapPhaseName.MODERNIZE
    return RoadmapPhaseName.MODERNIZE


def select_primary_priority_action_id(
    actions: Sequence[PriorityAction],
    *,
    phase_by_action_id: dict[str, RoadmapPhaseName] | None = None,
) -> str | None:
    """Select primary: earliest phase → priority → score → completeness → action_id."""

    if not actions:
        return None
    phases = phase_by_action_id or {
        item.action_id: map_phase_for_priority_action(item) for item in actions
    }

    def sort_key(item: PriorityAction) -> tuple[object, ...]:
        phase = phases.get(item.action_id, RoadmapPhaseName.MODERNIZE)
        return (
            _PHASE_RANK.get(phase, 99),
            _PRIORITY_RANK.get(str(item.priority).lower(), 99),
            -float(item.priority_score or 0.0),
            _COMPLETENESS_RANK.get(item.evidence_completeness, 99),
            item.action_id,
        )

    return sorted(actions, key=sort_key)[0].action_id


def derive_completeness_from_actions(
    actions: Sequence[PriorityAction],
) -> EvidenceCompleteness:
    if not actions:
        return EvidenceCompleteness.UNAVAILABLE
    values = [item.evidence_completeness for item in actions]
    if all(item is EvidenceCompleteness.COMPLETE for item in values):
        return EvidenceCompleteness.COMPLETE
    if all(item is EvidenceCompleteness.LEGACY for item in values):
        return EvidenceCompleteness.LEGACY
    return EvidenceCompleteness.PARTIAL


def initiative_from_priority_action(
    action: PriorityAction,
    *,
    sequence: int = 0,
) -> RoadmapInitiative:
    """One Priority Action → one Roadmap Initiative (default Slice 2.5 mapping)."""

    phase = map_phase_for_priority_action(action)
    category = normalize_category(action.category)
    rec_ids = tuple(action.supporting_recommendation_ids)
    finding_ids = tuple(action.supporting_finding_ids)
    if not rec_ids and action.primary_recommendation_id:
        rec_ids = (action.primary_recommendation_id,)
    if not rec_ids:
        rec_ids = (action.action_id,)
    return RoadmapInitiative(
        initiative_id=build_initiative_id(
            phase=phase.value,
            category=category,
            recommendation_ids=rec_ids,
        ),
        title=action.title,
        summary=action.summary or action.title,
        phase=phase,
        priority=map_priority(action.priority),
        effort=map_effort(action.effort, action_count=1),
        risk=map_risk(action.risk, priority=map_priority(action.priority)),
        expected_outcome=PHASE_OUTCOMES[phase],
        depends_on_initiative_ids=(),
        supporting_finding_ids=finding_ids,
        supporting_recommendation_ids=rec_ids,
        supporting_priority_action_ids=(action.action_id,),
        primary_priority_action_id=action.action_id,
        initiative_type=RoadmapInitiativeType.PRIORITY_ACTION_BACKED,
        evidence_completeness=action.evidence_completeness,
        limitations=tuple(action.limitations),
        confidence=(
            RoadmapConfidence.HIGH
            if finding_ids and action.evidence_completeness is EvidenceCompleteness.COMPLETE
            else RoadmapConfidence.MEDIUM
            if finding_ids
            else RoadmapConfidence.LOW
        ),
        category=category,
        sequence=sequence,
    )


def merge_roadmap_initiatives(
    preferred: RoadmapInitiative,
    other: RoadmapInitiative,
    *,
    actions_by_id: dict[str, PriorityAction] | None = None,
) -> RoadmapInitiative:
    """Union Priority Action / derived refs without first-wins loss."""

    actions_by_id = actions_by_id or {}
    supporting_pas = merge_unique_sorted(
        preferred.supporting_priority_action_ids,
        other.supporting_priority_action_ids,
    )
    source_actions = tuple(
        actions_by_id[action_id]
        for action_id in supporting_pas
        if action_id in actions_by_id
    )
    if source_actions:
        rec_ids: tuple[str, ...] = ()
        finding_ids: tuple[str, ...] = ()
        for item in source_actions:
            rec_ids = merge_unique_sorted(rec_ids, item.supporting_recommendation_ids)
            finding_ids = merge_unique_sorted(finding_ids, item.supporting_finding_ids)
        primary = select_primary_priority_action_id(source_actions)
        completeness = derive_completeness_from_actions(source_actions)
    else:
        rec_ids = merge_unique_sorted(
            preferred.supporting_recommendation_ids,
            other.supporting_recommendation_ids,
        )
        finding_ids = merge_unique_sorted(
            preferred.supporting_finding_ids,
            other.supporting_finding_ids,
        )
        primary = preferred.primary_priority_action_id or other.primary_priority_action_id
        if primary not in supporting_pas and supporting_pas:
            primary = supporting_pas[0]
        completeness = (
            EvidenceCompleteness.COMPLETE
            if preferred.evidence_completeness is EvidenceCompleteness.COMPLETE
            and other.evidence_completeness is EvidenceCompleteness.COMPLETE
            else EvidenceCompleteness.PARTIAL
        )
    limits = normalize_limitations((*preferred.limitations, *other.limitations))
    return preferred.model_copy(
        update={
            "supporting_priority_action_ids": supporting_pas,
            "primary_priority_action_id": primary,
            "supporting_recommendation_ids": rec_ids,
            "supporting_finding_ids": finding_ids,
            "initiative_type": RoadmapInitiativeType.MERGED,
            "evidence_completeness": completeness,
            "limitations": limits,
        }
    )


def build_roadmap_from_priority_actions(
    actions: Sequence[PriorityAction],
) -> RoadmapAssessmentSection:
    """Authoritative assessment roadmap: one initiative per Priority Action."""

    ordered = tuple(
        sorted(
            actions,
            key=lambda item: (
                _PHASE_RANK.get(map_phase_for_priority_action(item), 99),
                _PRIORITY_RANK.get(str(item.priority).lower(), 99),
                -float(item.priority_score or 0.0),
                item.action_id,
            ),
        )
    )
    if not ordered:
        return RoadmapAssessmentSection.empty(
            limitations=(*_BASE_LIMITATIONS, "No Priority Actions were supplied."),
        )

    initiatives: list[RoadmapInitiative] = []
    by_phase: dict[RoadmapPhaseName, list[str]] = defaultdict(list)
    for index, action in enumerate(ordered):
        initiative = initiative_from_priority_action(action, sequence=index)
        initiatives.append(initiative)
        by_phase[initiative.phase].append(initiative.initiative_id)

    linked: list[RoadmapInitiative] = []
    for item in initiatives:
        deps: list[str] = []
        for prior in prerequisite_phases(item.phase):
            deps.extend(by_phase.get(prior, ()))
        linked.append(
            item.model_copy(
                update={"depends_on_initiative_ids": tuple(sorted(set(deps)))}
            )
        )

    phases = _build_phases(linked)
    summary = (
        f"{len(linked)} initiative(s) across {len(phases)} phase(s) derived "
        f"from {len(ordered)} Priority Action(s)."
    )
    return RoadmapAssessmentSection(
        status=RoadmapStatus.SUCCEEDED,
        summary=summary,
        phases=phases,
        initiatives=tuple(linked),
        assumptions=_ASSUMPTIONS,
        limitations=_BASE_LIMITATIONS,
        confidence=RoadmapConfidence.HIGH
        if all(item.supporting_finding_ids for item in linked)
        else RoadmapConfidence.MEDIUM,
        metadata={
            "engine_version": ENGINE_VERSION,
            "source": "priority_actions",
            "initiative_count": str(len(linked)),
            "phase_count": str(len(phases)),
            "priority_action_count": str(len(ordered)),
        },
    )


def _build_phases(initiatives: Sequence[RoadmapInitiative]) -> tuple[RoadmapPhasePlan, ...]:
    by_phase: dict[RoadmapPhaseName, list[str]] = defaultdict(list)
    for item in initiatives:
        by_phase[item.phase].append(item.initiative_id)
    plans: list[RoadmapPhasePlan] = []
    for index, phase in enumerate(PHASE_SEQUENCE):
        ids = tuple(by_phase.get(phase, ()))
        if not ids:
            continue
        plans.append(
            RoadmapPhasePlan(
                phase_id=build_phase_id(phase.value),
                phase=phase,
                title=PHASE_TITLES[phase],
                objective=PHASE_OBJECTIVES[phase],
                sequence=index,
                initiative_ids=ids,
            )
        )
    return tuple(plans)
