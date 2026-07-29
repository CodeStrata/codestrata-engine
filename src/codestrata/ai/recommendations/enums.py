"""Provider-neutral AI recommendation contract enums."""

from __future__ import annotations

from enum import StrEnum


class AIRecommendationPriority(StrEnum):
    """Priority assigned to an AI modernization recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AIRecommendationEffort(StrEnum):
    """Estimated implementation effort."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


class AIRecommendationImpact(StrEnum):
    """Expected modernization impact."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AIRecommendationConfidence(StrEnum):
    """Confidence in the recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
