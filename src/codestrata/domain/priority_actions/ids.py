"""Deterministic Priority Action identity helpers.

Presentation IDs remain recommendation IDs when a Priority Action is backed by
exactly one Recommendation (Slice 2.4 compatibility).
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank


def build_priority_action_id(
    *,
    primary_recommendation_id: str,
    supporting_recommendation_ids: Sequence[str] = (),
) -> str:
    """Preserve presentation ID as the primary recommendation ID when possible.

    Single-recommendation actions keep ``action_id == recommendation_id``.
    Merged actions still use the deterministically selected primary
    recommendation ID so customer anchors remain stable.
    """

    primary = require_nonblank(primary_recommendation_id, label="primary_recommendation_id")
    supporting = tuple(
        sorted({require_nonblank(item, label="recommendation_id") for item in supporting_recommendation_ids})
    )
    if supporting and primary not in supporting:
        raise ValueError("primary_recommendation_id must be in supporting_recommendation_ids")
    return primary
