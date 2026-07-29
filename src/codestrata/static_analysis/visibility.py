"""Customer visibility and modernization-relevance classifications."""

from __future__ import annotations

from enum import StrEnum


class CustomerVisibility(StrEnum):
    """How a finding or observation should appear in customer reports."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"
    INFORMATIONAL = "informational"
    SUPPRESSED_FROM_HTML = "suppressed_from_html"


class ModernizationRelevance(StrEnum):
    """How relevant an observation is to modernization planning."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
