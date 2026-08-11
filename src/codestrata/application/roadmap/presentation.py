"""HTML presentation adapter for Priority Action–backed roadmaps (Slice 2.5).

Preserves existing leadership HTML appearance and anchors:
``initiative_id = leadership:{priority_action_id}``.

This adapter is not an authoritative roadmap source of truth.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from codestrata.domain.priority_actions import PriorityAction
from codestrata.domain.roadmap.constants import PHASE_OBJECTIVES, PHASE_TITLES
from codestrata.domain.roadmap.enums import RoadmapPhaseName
from codestrata.domain.roadmap.models import RoadmapAssessmentSection, RoadmapInitiative
from codestrata.reporting.roadmap.models import (
    RoadmapReportInitiativeView,
    RoadmapReportPhaseView,
    RoadmapReportSection,
)


def presentation_initiative_id(primary_priority_action_id: str) -> str:
    """Stable HTML/presentation ID used before Slice 2.5 cutover."""

    return f"leadership:{primary_priority_action_id}"


def project_roadmap_for_leadership(
    section: RoadmapAssessmentSection,
    *,
    actions_by_id: dict[str, PriorityAction] | None = None,
    outcome_for_action: Callable[[str, str], str] | None = None,
) -> RoadmapReportSection | None:
    """Project canonical PA-backed roadmap onto existing HTML RoadmapReportSection."""

    if not section.initiatives:
        return None
    actions_by_id = actions_by_id or {}
    id_map: dict[str, str] = {}
    report_initiatives: list[RoadmapReportInitiativeView] = []
    for item in section.initiatives:
        presentation_id = _presentation_id_for(item)
        id_map[item.initiative_id] = presentation_id
        action = None
        if item.primary_priority_action_id:
            action = actions_by_id.get(item.primary_priority_action_id)
        title = action.title if action is not None else item.title
        category = action.category if action is not None else item.category
        outcome = item.expected_outcome
        if outcome_for_action is not None:
            outcome = outcome_for_action(title, category)
        report_initiatives.append(
            RoadmapReportInitiativeView(
                initiative_id=presentation_id,
                title=title,
                summary=title,
                phase=item.phase.value,
                phase_label=item.phase.value.title(),
                priority=action.priority if action is not None else item.priority.value,
                effort=(
                    action.effort
                    if action is not None
                    else item.effort.value
                )
                or "medium",
                risk=(action.risk if action is not None else item.risk.value) or "medium",
                expected_outcome=outcome,
                depends_on_initiative_ids=tuple(
                    id_map.get(dep, dep) for dep in item.depends_on_initiative_ids
                ),
                supporting_finding_ids=item.supporting_finding_ids,
                supporting_recommendation_ids=item.supporting_recommendation_ids,
                supporting_priority_action_ids=item.supporting_priority_action_ids,
                primary_priority_action_id=item.primary_priority_action_id,
                initiative_type=(
                    item.initiative_type.value
                    if hasattr(item.initiative_type, "value")
                    else str(item.initiative_type)
                ),
                evidence_completeness=(
                    item.evidence_completeness.value
                    if hasattr(item.evidence_completeness, "value")
                    else str(item.evidence_completeness)
                ),
                limitations=tuple(item.limitations),
                confidence=item.confidence.value,
                category=category,
                sequence=item.sequence + 1 if item.sequence >= 0 else item.sequence,
            )
        )

    # Remap depends_on after full id_map is known.
    remapped: list[RoadmapReportInitiativeView] = []
    for item in report_initiatives:
        # depends already partially remapped; ensure all use presentation ids.
        deps = tuple(
            dep if dep.startswith("leadership:") else id_map.get(dep, dep)
            for dep in item.depends_on_initiative_ids
        )
        remapped.append(item.model_copy(update={"depends_on_initiative_ids": deps}))

    by_presentation = {item.initiative_id: item for item in remapped}
    phases: list[RoadmapReportPhaseView] = []
    for phase in section.phases:
        phase_initiatives = tuple(
            by_presentation[id_map[iid]]
            for iid in phase.initiative_ids
            if iid in id_map and id_map[iid] in by_presentation
        )
        if not phase_initiatives:
            continue
        phases.append(
            RoadmapReportPhaseView(
                phase_id=f"phase:{phase.phase.value}",
                phase=phase.phase.value,
                title=phase.phase.value.title(),
                objective=PHASE_OBJECTIVES.get(phase.phase, phase.objective),
                sequence=len(phases),
                initiative_ids=tuple(item.initiative_id for item in phase_initiatives),
                initiatives=phase_initiatives,
            )
        )

    near = sum(
        1
        for action in actions_by_id.values()
        if (action.presentation_bucket or "").lower() in {"immediate", "near_term"}
    )
    summary = (
        f"{len(remapped)} initiative(s) across {len(phases)} phase(s), "
        f"sequenced to match Priority Actions"
        + (f" ({near} near-term)." if near else ".")
    )
    return RoadmapReportSection(
        engine_version="leadership-presentation",
        status="succeeded",
        status_label="Ready",
        summary=summary,
        phases=tuple(phases),
        initiatives=tuple(remapped),
        initiatives_total=len(remapped),
        initiatives_displayed=len(remapped),
        assumptions=(),
        limitations=(),
        confidence="medium",
        metadata={
            "source": "priority_actions",
            "canonical_engine_version": section.engine_version,
            "adapter": "leadership_presentation_slice_2_5",
        },
    )


def _presentation_id_for(item: RoadmapInitiative) -> str:
    primary = item.primary_priority_action_id
    if primary:
        return presentation_initiative_id(primary)
    if item.supporting_priority_action_ids:
        return presentation_initiative_id(item.supporting_priority_action_ids[0])
    return item.initiative_id
