"""Normalized inputs and mapping helpers for the Modernization Roadmap Engine."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.roadmap.constants import (
    PHASE_SEQUENCE,
)
from codestrata.domain.roadmap.enums import (
    RoadmapEffort,
    RoadmapPhaseName,
    RoadmapPriority,
    RoadmapRisk,
)

# Category → phase (string keys normalize Phase 1 + Phase 3 category values).
_STABILIZE_CATEGORIES = frozenset(
    {
        "testing",
        "build",
        "documentation",
        "governance",
        "configuration",
        "operational_readiness",
        "reliability",
        "ci_cd",
    }
)
_SECURE_CATEGORIES = frozenset({"security"})
_OPTIMIZE_CATEGORIES = frozenset({"performance"})

_PRIORITY_RANK = {
    RoadmapPriority.CRITICAL: 0,
    RoadmapPriority.HIGH: 1,
    RoadmapPriority.MEDIUM: 2,
    RoadmapPriority.LOW: 3,
}
_EFFORT_RANK = {
    RoadmapEffort.XS: 0,
    RoadmapEffort.S: 1,
    RoadmapEffort.M: 2,
    RoadmapEffort.L: 3,
    RoadmapEffort.XL: 4,
}
_RISK_RANK = {
    RoadmapRisk.LOW: 0,
    RoadmapRisk.MEDIUM: 1,
    RoadmapRisk.HIGH: 2,
}


class RoadmapSourceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap source evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional roadmap source evidence")


class RoadmapSourceFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    severity: str
    category: str
    evidence: tuple[RoadmapSourceEvidence, ...] = ()

    @field_validator("id", "title", "severity", "category", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap source finding field")

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RoadmapSourceRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    summary: str
    priority: str
    category: str
    related_finding_ids: tuple[str, ...] = ()
    evidence: tuple[RoadmapSourceEvidence, ...] = ()
    action_count: int = Field(default=0, ge=0)
    effort: str | None = None
    risk: str | None = None

    @field_validator("id", "title", "summary", "priority", "category", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="roadmap source recommendation field")

    @field_validator("related_finding_ids", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("effort", "risk", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional roadmap source field")


def normalize_category(value: str) -> str:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "dependencies": "dependency",
        "cloud_readiness": "cloud",
        "ci/cd": "ci_cd",
        "cicd": "ci_cd",
        "tech_debt": "technical_debt",
        "technicaldebt": "technical_debt",
    }
    return aliases.get(key, key)


def map_phase(category: str) -> RoadmapPhaseName:
    key = normalize_category(category)
    if key in _STABILIZE_CATEGORIES:
        return RoadmapPhaseName.STABILIZE
    if key in _SECURE_CATEGORIES:
        return RoadmapPhaseName.SECURE
    if key in _OPTIMIZE_CATEGORIES:
        return RoadmapPhaseName.OPTIMIZE
    return RoadmapPhaseName.MODERNIZE


def map_priority(value: str) -> RoadmapPriority:
    key = value.strip().lower()
    if key in {"immediate", "critical"}:
        return RoadmapPriority.CRITICAL
    if key == "high":
        return RoadmapPriority.HIGH
    if key == "medium":
        return RoadmapPriority.MEDIUM
    return RoadmapPriority.LOW


def map_effort_from_actions(action_count: int) -> RoadmapEffort:
    if action_count <= 1:
        return RoadmapEffort.XS
    if action_count == 2:
        return RoadmapEffort.S
    if action_count <= 4:
        return RoadmapEffort.M
    if action_count <= 7:
        return RoadmapEffort.L
    return RoadmapEffort.XL


def map_effort(value: str | None, *, action_count: int) -> RoadmapEffort:
    if value is None:
        return map_effort_from_actions(action_count)
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "xs": RoadmapEffort.XS,
        "extra_small": RoadmapEffort.XS,
        "s": RoadmapEffort.S,
        "small": RoadmapEffort.S,
        "m": RoadmapEffort.M,
        "medium": RoadmapEffort.M,
        "l": RoadmapEffort.L,
        "large": RoadmapEffort.L,
        "xl": RoadmapEffort.XL,
        "extra_large": RoadmapEffort.XL,
        "unknown": map_effort_from_actions(action_count),
    }
    return mapping.get(key, map_effort_from_actions(action_count))


def map_risk_from_priority(priority: RoadmapPriority) -> RoadmapRisk:
    if priority in {RoadmapPriority.CRITICAL, RoadmapPriority.HIGH}:
        return RoadmapRisk.HIGH
    if priority == RoadmapPriority.MEDIUM:
        return RoadmapRisk.MEDIUM
    return RoadmapRisk.LOW


def map_risk(
    value: str | None,
    *,
    priority: RoadmapPriority,
    finding_severities: Sequence[str] = (),
) -> RoadmapRisk:
    candidates = [map_risk_from_priority(priority)]
    if value is not None:
        key = value.strip().lower()
        if key == "high":
            candidates.append(RoadmapRisk.HIGH)
        elif key == "medium":
            candidates.append(RoadmapRisk.MEDIUM)
        elif key == "low":
            candidates.append(RoadmapRisk.LOW)
    for severity in finding_severities:
        sev = severity.strip().lower()
        if sev in {"critical", "high"}:
            candidates.append(RoadmapRisk.HIGH)
        elif sev == "medium":
            candidates.append(RoadmapRisk.MEDIUM)
    return max_risk(candidates)


def max_priority(values: Sequence[RoadmapPriority]) -> RoadmapPriority:
    if not values:
        return RoadmapPriority.LOW
    return min(values, key=_PRIORITY_RANK.__getitem__)


def max_effort(values: Sequence[RoadmapEffort]) -> RoadmapEffort:
    if not values:
        return RoadmapEffort.M
    return max(values, key=_EFFORT_RANK.__getitem__)


def max_risk(values: Sequence[RoadmapRisk]) -> RoadmapRisk:
    if not values:
        return RoadmapRisk.LOW
    return max(values, key=_RISK_RANK.__getitem__)


def priority_rank(value: RoadmapPriority) -> int:
    return _PRIORITY_RANK[value]


def prerequisite_phases(phase: RoadmapPhaseName) -> tuple[RoadmapPhaseName, ...]:
    index = PHASE_SEQUENCE.index(phase)
    return PHASE_SEQUENCE[:index]
