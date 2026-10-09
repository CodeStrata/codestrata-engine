"""Lane classification for integration, story, maintenance and hotfix refs."""

from __future__ import annotations

from verification.release_isolation.lanes import classify_ref, story_branch_is_short
from verification.release_isolation.models import LaneKind
from verification.release_isolation.policy import load_policy


def test_known_lanes() -> None:
    lanes = load_policy().lanes
    assert classify_ref("release/engine-next", lanes) is LaneKind.INTEGRATION
    assert classify_ref("refs/heads/main", lanes) is LaneKind.MAINTENANCE
    assert classify_ref("hotfix/pyyaml", lanes) is LaneKind.HOTFIX
    assert classify_ref("engine/E00.3-integration-hotfix-prerelease-isolation", lanes) is (
        LaneKind.STORY
    )
    assert classify_ref("feature/random", lanes) is LaneKind.UNKNOWN


def test_short_story_branch_rejects_epic_trains() -> None:
    assert story_branch_is_short("engine/E00.3-isolation")
    assert not story_branch_is_short("engine/epic/E00-all")
    assert not story_branch_is_short("release/engine-next")
