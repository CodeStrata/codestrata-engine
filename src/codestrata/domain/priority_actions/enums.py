"""Priority Action enumerations (Epic 2 Slice 2.4)."""

from __future__ import annotations

from enum import StrEnum


class PriorityActionType(StrEnum):
    """Lightweight Priority Action classification."""

    RECOMMENDATION_BACKED = "recommendation_backed"
    MERGED = "merged"
    LEGACY = "legacy"
