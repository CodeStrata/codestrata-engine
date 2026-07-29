"""AI enrichment enumerations (narrative layer over deterministic findings)."""

from __future__ import annotations

from enum import StrEnum


class EnrichmentPriorityLevel(StrEnum):
    """Priority level for modernization narrative items."""

    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
