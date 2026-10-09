"""Live hotfixes land on the maintenance lane and are backported into next on purpose."""

from __future__ import annotations

from verification.release_isolation.models import (
    CheckStatus,
    HotfixAction,
    HotfixPlan,
    IsolationLanes,
)


def evaluate_hotfix(
    action: HotfixAction,
    *,
    source_lane: str,
    dest_lane: str,
    lanes: IsolationLanes,
    recorded: bool,
    rewrite_rollback: bool = False,
) -> HotfixPlan:
    reasons: list[str] = []
    status = CheckStatus.PASS
    if rewrite_rollback:
        status = CheckStatus.FAIL
        reasons.append("hotfix must preserve exact rollback artifacts")
    if action is HotfixAction.MOVE_STABLE_TAG:
        status = CheckStatus.FAIL
        reasons.append("hotfixes must not move stable tags")
    elif action is HotfixAction.REWRITE_ROLLBACK_ARTIFACT:
        status = CheckStatus.FAIL
        reasons.append("rewriting the live rollback artifact is forbidden")
    elif action is HotfixAction.AUTO_PROMOTE_NEXT_TO_MAINTENANCE:
        status = CheckStatus.FAIL
        reasons.append("next must not auto-promote onto the stable maintenance lane")
    elif action is HotfixAction.LAND_ON_MAINTENANCE:
        if dest_lane != lanes.maintenance:
            status = CheckStatus.FAIL
            reasons.append("live hotfixes land on the one maintenance lane (main)")
        elif source_lane == lanes.integration:
            status = CheckStatus.FAIL
            reasons.append("do not land an unreviewed next branch as a live hotfix")
    elif action is HotfixAction.BACKPORT_TO_NEXT:
        if source_lane != lanes.maintenance or dest_lane != lanes.integration:
            status = CheckStatus.FAIL
            reasons.append("backport is maintenance -> release/engine-next only")
        elif not recorded:
            status = CheckStatus.FAIL
            reasons.append("backport into next must be deliberate and recorded")
        else:
            reasons.append("recorded backport from maintenance into next")
    if status is CheckStatus.PASS and not reasons:
        reasons.append("hotfix isolation holds")
    return HotfixPlan(
        action=action,
        source_lane=source_lane,
        dest_lane=dest_lane,
        recorded=recorded,
        status=status,
        reasons=tuple(reasons),
    )
