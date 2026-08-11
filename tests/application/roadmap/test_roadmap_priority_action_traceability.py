"""Tests for Priority Action → Roadmap Initiative traceability (Slice 2.5)."""

from __future__ import annotations

import pytest

from codestrata.application.roadmap import (
    build_roadmap_from_priority_actions,
    initiative_from_priority_action,
    merge_roadmap_initiatives,
    presentation_initiative_id,
    project_roadmap_for_leadership,
    select_primary_priority_action_id,
)
from codestrata.domain.priority_actions import PriorityAction, PriorityActionType
from codestrata.domain.roadmap.enums import RoadmapInitiativeType, RoadmapPhaseName
from codestrata.domain.roadmap.identifiers import build_initiative_id
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION


def _action(
    *,
    action_id: str,
    title: str,
    priority: str = "high",
    score: float = 100.0,
    bucket: str = "near_term",
    category: str = "testing",
    finding_ids: tuple[str, ...] = ("finding:a",),
    rec_ids: tuple[str, ...] | None = None,
    completeness: EvidenceCompleteness = EvidenceCompleteness.COMPLETE,
    limitations: tuple[str, ...] = (),
) -> PriorityAction:
    recs = rec_ids if rec_ids is not None else (action_id,)
    return PriorityAction.create(
        title=title,
        summary=f"Summary for {title}",
        priority=priority,
        supporting_recommendation_ids=recs,
        supporting_finding_ids=finding_ids,
        primary_recommendation_id=recs[0],
        priority_score=score,
        effort="medium",
        presentation_bucket=bucket,
        action_type=PriorityActionType.RECOMMENDATION_BACKED,
        evidence_completeness=completeness,
        limitations=limitations,
        category=category,
        rationale="r",
        risk="medium",
    )


def test_single_priority_action_creates_initiative() -> None:
    action = _action(action_id="rec-1", title="Establish a test baseline")
    initiative = initiative_from_priority_action(action)
    assert initiative.supporting_priority_action_ids == ("rec-1",)
    assert initiative.primary_priority_action_id == "rec-1"
    assert initiative.supporting_recommendation_ids == ("rec-1",)
    assert initiative.supporting_finding_ids == ("finding:a",)
    assert initiative.initiative_type is RoadmapInitiativeType.PRIORITY_ACTION_BACKED
    assert initiative.phase is RoadmapPhaseName.STABILIZE
    assert initiative.initiative_id == build_initiative_id(
        phase="stabilize",
        category="testing",
        recommendation_ids=("rec-1",),
    )


def test_builder_one_initiative_per_action_and_empty_without_actions() -> None:
    actions = (
        _action(action_id="rec-1", title="Add tests", category="testing"),
        _action(
            action_id="rec-2",
            title="Remediate secrets",
            category="security",
            bucket="immediate",
            finding_ids=("finding:b",),
        ),
    )
    section = build_roadmap_from_priority_actions(actions)
    assert len(section.initiatives) == 2
    assert all(item.supporting_priority_action_ids for item in section.initiatives)
    assert section.metadata.get("source") == "priority_actions"
    empty = build_roadmap_from_priority_actions(())
    assert empty.initiatives == ()
    assert empty.status.value == "empty"


def test_recommendation_or_finding_alone_cannot_create_pa_backed_initiative() -> None:
    from pydantic import ValidationError

    from codestrata.domain.roadmap.enums import (
        RoadmapEffort,
        RoadmapPriority,
        RoadmapRisk,
    )
    from codestrata.domain.roadmap.models import RoadmapInitiative

    with pytest.raises(ValidationError, match="supporting_priority_action_ids"):
        RoadmapInitiative(
            initiative_id="x",
            title="t",
            summary="s",
            phase=RoadmapPhaseName.STABILIZE,
            priority=RoadmapPriority.HIGH,
            effort=RoadmapEffort.M,
            risk=RoadmapRisk.MEDIUM,
            expected_outcome="o",
            supporting_recommendation_ids=("rec-1",),
            supporting_finding_ids=("finding:a",),
            initiative_type=RoadmapInitiativeType.PRIORITY_ACTION_BACKED,
            supporting_priority_action_ids=(),
        )


def test_primary_priority_action_selection() -> None:
    low = _action(action_id="rec-low", title="Later", priority="low", score=40.0)
    high = _action(action_id="rec-high", title="Soon", priority="high", score=90.0)
    assert select_primary_priority_action_id((low, high)) == "rec-high"


def test_merge_unions_priority_actions_and_derived_refs() -> None:
    left = initiative_from_priority_action(
        _action(
            action_id="rec-a",
            title="A",
            finding_ids=("finding:a",),
            limitations=("left",),
        )
    )
    right_action = _action(
        action_id="rec-b",
        title="B",
        finding_ids=("finding:b",),
        limitations=("right",),
        priority="medium",
        score=50.0,
    )
    right = initiative_from_priority_action(right_action)
    merged = merge_roadmap_initiatives(
        left,
        right,
        actions_by_id={
            "rec-a": _action(action_id="rec-a", title="A", finding_ids=("finding:a",)),
            "rec-b": right_action,
        },
    )
    assert merged.supporting_priority_action_ids == ("rec-a", "rec-b")
    assert merged.supporting_recommendation_ids == ("rec-a", "rec-b")
    assert merged.supporting_finding_ids == ("finding:a", "finding:b")
    assert "left" in merged.limitations and "right" in merged.limitations
    assert merged.initiative_type is RoadmapInitiativeType.MERGED


def test_presentation_adapter_preserves_leadership_ids_and_order() -> None:
    actions = (
        _action(action_id="a1", title="Establish a test baseline", category="testing"),
        _action(
            action_id="a2",
            title="Commit an npm lockfile",
            category="dependency",
            finding_ids=("finding:b",),
        ),
    )
    section = build_roadmap_from_priority_actions(actions)
    projected = project_roadmap_for_leadership(
        section,
        actions_by_id={item.action_id: item for item in actions},
        outcome_for_action=lambda title, _cat: f"Outcome for {title}",
    )
    assert projected is not None
    assert [item.initiative_id for item in projected.initiatives] == [
        presentation_initiative_id("a1"),
        presentation_initiative_id("a2"),
    ]
    assert [item.title for item in projected.initiatives] == [
        "Establish a test baseline",
        "Commit an npm lockfile",
    ]
    assert all(item.supporting_recommendation_ids for item in projected.initiatives)
    assert all(item.supporting_finding_ids for item in projected.initiatives)


def test_initiative_id_stable_with_traceability_fields() -> None:
    action = _action(action_id="rec-1", title="Add LICENSE", category="governance")
    first = initiative_from_priority_action(action)
    second = initiative_from_priority_action(
        action.model_copy(update={"limitations": ("note",)})
    )
    assert first.initiative_id == second.initiative_id


def test_schema_remains_1_2() -> None:
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
