"""Roadmap domain enumerations (Phase 5.10)."""

from __future__ import annotations

from enum import StrEnum


class RoadmapPhaseName(StrEnum):
    STABILIZE = "stabilize"
    SECURE = "secure"
    MODERNIZE = "modernize"
    OPTIMIZE = "optimize"


class RoadmapPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RoadmapEffort(StrEnum):
    XS = "xs"
    S = "s"
    M = "m"
    L = "l"
    XL = "xl"


class RoadmapRisk(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RoadmapConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class RoadmapStatus(StrEnum):
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    DISABLED = "disabled"
    FAILED = "failed"
