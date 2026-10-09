"""Hotfix backport policy."""

from __future__ import annotations

from verification.release_isolation.hotfix import evaluate_hotfix
from verification.release_isolation.models import CheckStatus, HotfixAction
from verification.release_isolation.policy import load_policy


def test_recorded_backport_from_main_to_next_passes() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.BACKPORT_TO_NEXT,
        source_lane=lanes.maintenance,
        dest_lane=lanes.integration,
        lanes=lanes,
        recorded=True,
    )
    assert plan.status is CheckStatus.PASS


def test_unrecorded_backport_fails() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.BACKPORT_TO_NEXT,
        source_lane=lanes.maintenance,
        dest_lane=lanes.integration,
        lanes=lanes,
        recorded=False,
    )
    assert plan.status is CheckStatus.FAIL


def test_wrong_direction_backport_fails() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.BACKPORT_TO_NEXT,
        source_lane=lanes.integration,
        dest_lane=lanes.maintenance,
        lanes=lanes,
        recorded=True,
    )
    assert plan.status is CheckStatus.FAIL


def test_auto_promote_next_fails() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.AUTO_PROMOTE_NEXT_TO_MAINTENANCE,
        source_lane=lanes.integration,
        dest_lane=lanes.maintenance,
        lanes=lanes,
        recorded=True,
    )
    assert plan.status is CheckStatus.FAIL


def test_moving_stable_tag_fails() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.MOVE_STABLE_TAG,
        source_lane=lanes.maintenance,
        dest_lane=lanes.maintenance,
        lanes=lanes,
        recorded=True,
    )
    assert plan.status is CheckStatus.FAIL


def test_rewrite_rollback_during_hotfix_fails() -> None:
    lanes = load_policy().lanes
    plan = evaluate_hotfix(
        HotfixAction.LAND_ON_MAINTENANCE,
        source_lane="hotfix/r01",
        dest_lane=lanes.maintenance,
        lanes=lanes,
        recorded=True,
        rewrite_rollback=True,
    )
    assert plan.status is CheckStatus.FAIL
