"""Classify git refs into the one integration, story, maintenance and hotfix lanes."""

from __future__ import annotations

import re

from verification.release_isolation.models import IsolationLanes, LaneKind

_STORY = re.compile(r"^engine/E\d+\.\d+-[A-Za-z0-9._-]+$")


def classify_ref(ref: str, lanes: IsolationLanes) -> LaneKind:
    name = ref.removeprefix("refs/heads/")
    if name == lanes.integration:
        return LaneKind.INTEGRATION
    if name == lanes.maintenance:
        return LaneKind.MAINTENANCE
    if name.startswith(lanes.hotfix_prefix) and name != lanes.hotfix_prefix:
        return LaneKind.HOTFIX
    if _STORY.fullmatch(name):
        return LaneKind.STORY
    if name.startswith(lanes.story_prefix):
        return LaneKind.STORY
    return LaneKind.UNKNOWN


def story_branch_is_short(ref: str) -> bool:
    """Story/epic work is one short-lived branch per story, not a stacked epic train."""

    name = ref.removeprefix("refs/heads/")
    if not name.startswith("engine/"):
        return False
    return _STORY.fullmatch(name) is not None and "/epic/" not in name
