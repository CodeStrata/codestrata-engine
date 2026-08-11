"""Tests for Priority Action domain model (Epic 2 Slice 2.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.priority_actions import (
    build_priority_actions,
    merge_priority_actions,
    priority_action_from_recommendation,
    select_primary_recommendation_id,
)
from codestrata.domain.priority_actions import PriorityAction, PriorityActionType
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.customer_universe import CustomerRecommendation


def _customer_rec(
    *,
    rec_id: str,
    title: str,
    priority: str = "high",
    finding_ids: tuple[str, ...] = ("finding:a",),
    score: float = 100.0,
    bucket: str = "near_term",
    completeness: str = "complete",
    limitations: tuple[str, ...] = (),
) -> CustomerRecommendation:
    return CustomerRecommendation(
        id=rec_id,
        rule_id=f"provider:{rec_id}",
        title=title,
        description=f"Summary for {title}",
        rationale="Because findings require it",
        priority=priority,
        category="testing",
        effort="medium",
        risk="medium",
        related_finding_ids=finding_ids,
        supporting_finding_ids=finding_ids,
        primary_finding_id=finding_ids[0] if finding_ids else None,
        recommendation_type="finding_backed",
        evidence_completeness=completeness,
        limitations=limitations,
        actions=("Do it",),
        dependencies=(),
        evidence=(),
        priority_score=score,
        presentation_bucket=bucket,
    )


def test_single_recommendation_maps_to_priority_action() -> None:
    rec = _customer_rec(rec_id="rec-1", title="Establish a test baseline")
    action = priority_action_from_recommendation(rec)
    assert action.action_id == "rec-1"
    assert action.primary_recommendation_id == "rec-1"
    assert action.supporting_recommendation_ids == ("rec-1",)
    assert action.supporting_finding_ids == ("finding:a",)
    assert action.action_type is PriorityActionType.RECOMMENDATION_BACKED
    assert action.evidence_completeness is EvidenceCompleteness.COMPLETE


def test_primary_recommendation_selection_prefers_higher_priority() -> None:
    low = _customer_rec(rec_id="rec-low", title="Later", priority="low", score=40.0)
    high = _customer_rec(rec_id="rec-high", title="Soon", priority="high", score=90.0)
    assert select_primary_recommendation_id((low, high)) == "rec-high"


def test_build_skips_ungrounded_and_does_not_fabricate() -> None:
    grounded = _customer_rec(rec_id="rec-1", title="Add tests")
    ungrounded = _customer_rec(
        rec_id="rec-2",
        title="Cloud packaging",
        finding_ids=(),
        completeness="legacy",
    )
    actions = build_priority_actions((ungrounded, grounded))
    assert len(actions) == 1
    assert actions[0].action_id == "rec-1"


def test_merge_unions_recommendations_and_findings() -> None:
    left = priority_action_from_recommendation(
        _customer_rec(
            rec_id="rec-a",
            title="Action",
            finding_ids=("finding:a",),
            limitations=("left",),
        )
    )
    right = priority_action_from_recommendation(
        _customer_rec(
            rec_id="rec-b",
            title="Action",
            finding_ids=("finding:b",),
            limitations=("right",),
            priority="medium",
            score=50.0,
        )
    )
    # Force shared presentation id path used by engine merge-by-id.
    right = right.model_copy(update={"action_id": left.action_id})
    merged = merge_priority_actions(
        left,
        right,
        recommendations=(
            _customer_rec(rec_id="rec-a", title="Action", finding_ids=("finding:a",)),
            _customer_rec(
                rec_id="rec-b",
                title="Action",
                finding_ids=("finding:b",),
                priority="medium",
                score=50.0,
            ),
        ),
    )
    assert merged.supporting_recommendation_ids == ("rec-a", "rec-b")
    assert merged.supporting_finding_ids == ("finding:a", "finding:b")
    assert "left" in merged.limitations and "right" in merged.limitations
    assert merged.action_type is PriorityActionType.MERGED
    assert merged.primary_recommendation_id == "rec-a"


def test_primary_must_be_in_supporting_recommendations() -> None:
    with pytest.raises(ValidationError, match="primary_recommendation_id"):
        PriorityAction(
            action_id="rec-a",
            title="t",
            summary="s",
            priority="high",
            supporting_recommendation_ids=("rec-a",),
            primary_recommendation_id="rec-missing",
            supporting_finding_ids=("finding:a",),
            action_type=PriorityActionType.RECOMMENDATION_BACKED,
            evidence_completeness=EvidenceCompleteness.COMPLETE,
        )


def test_create_requires_recommendation() -> None:
    from codestrata.domain.traceability import TraceabilityValidationError

    with pytest.raises(TraceabilityValidationError, match="at least one supporting recommendation"):
        PriorityAction.create(
            title="t",
            summary="s",
            priority="high",
            supporting_recommendation_ids=(),
        )


def test_schema_remains_1_2() -> None:
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_presentation_id_equals_recommendation_id() -> None:
    action = priority_action_from_recommendation(
        _customer_rec(rec_id="stable-rec-id", title="Pin versions")
    )
    assert action.action_id == "stable-rec-id"
    assert action.action_id == action.primary_recommendation_id
