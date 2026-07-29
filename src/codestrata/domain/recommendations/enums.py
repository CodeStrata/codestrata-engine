"""Phase 3 recommendation enumerations."""

from __future__ import annotations

from enum import StrEnum


class RecommendationPriority(StrEnum):
    """Deterministic recommendation priority."""

    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationCategory(StrEnum):
    """Category for modernization recommendations."""

    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    TESTING = "testing"
    BUILD = "build"
    DEPENDENCY = "dependency"
    MAINTAINABILITY = "maintainability"
    MODERNIZATION = "modernization"
    UNKNOWN = "unknown"


class RecommendationSource(StrEnum):
    """Origin of a Phase 3 recommendation."""

    FINDING_RULE = "finding_rule"
