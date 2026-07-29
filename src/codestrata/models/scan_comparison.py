"""Domain models for deterministic scan-to-scan comparison."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ComparedFinding(BaseModel):
    """A finding referenced by a scan comparison."""

    rule_id: str | None = None
    title: str
    category: str
    severity: str
    identity_key: str


class SeverityChange(BaseModel):
    """A finding whose severity changed between scans."""

    rule_id: str | None = None
    title: str
    category: str
    identity_key: str
    previous_severity: str
    current_severity: str
    direction: Literal["increased", "decreased"]


class ComparedRecommendation(BaseModel):
    """A recommendation referenced by a scan comparison."""

    rule_id: str
    title: str
    priority: str
    category: str


class PriorityChange(BaseModel):
    """A recommendation whose priority changed between scans."""

    rule_id: str
    title: str
    category: str
    previous_priority: str
    current_priority: str
    direction: Literal["increased", "decreased"]


class FactChange(BaseModel):
    """A normalized repository-fact change between scans."""

    path: str
    change_type: Literal["changed", "added", "removed"]
    previous_value: Any = None
    current_value: Any = None
    added_values: list[str] = Field(default_factory=list)
    removed_values: list[str] = Field(default_factory=list)
    summary: str | None = None

    def display_text(self) -> str:
        """Return a concise, client-facing description of the change."""

        if self.summary:
            return self.summary

        if self.added_values or self.removed_values:
            added = ", ".join(self.added_values)
            removed = ", ".join(self.removed_values)
            return f"added=[{added}]; removed=[{removed}]"

        if self.change_type == "added":
            return f"added {self.current_value!s}"

        if self.change_type == "removed":
            return f"removed {self.previous_value!s}"

        return f"{self.previous_value!s} → {self.current_value!s}"


class ComparisonSummary(BaseModel):
    """Deterministic aggregate counts for a scan comparison."""

    new_findings: int = 0
    resolved_findings: int = 0
    worsened_findings: int = 0
    improved_findings: int = 0
    new_recommendations: int = 0
    resolved_recommendations: int = 0
    worsened_priorities: int = 0
    improved_priorities: int = 0
    fact_changes: int = 0


class ScanComparison(BaseModel):
    """Structured comparison between the current scan and a prior baseline."""

    baseline_available: bool = False
    baseline_timestamp: str | None = None
    current_timestamp: str | None = None
    baseline_analyzer_version: str | None = None
    current_analyzer_version: str | None = None
    baseline_ruleset_version: str | None = None
    current_ruleset_version: str | None = None
    notes: list[str] = Field(default_factory=list)
    new_findings: list[ComparedFinding] = Field(default_factory=list)
    resolved_findings: list[ComparedFinding] = Field(default_factory=list)
    unchanged_findings: list[ComparedFinding] = Field(default_factory=list)
    severity_changes: list[SeverityChange] = Field(default_factory=list)
    new_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    resolved_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    unchanged_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    priority_changes: list[PriorityChange] = Field(default_factory=list)
    fact_changes: list[FactChange] = Field(default_factory=list)
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)

    @classmethod
    def unavailable(cls, current_timestamp: str | None = None) -> ScanComparison:
        """Return a comparison result when no baseline is available."""

        return cls(
            baseline_available=False,
            current_timestamp=current_timestamp,
        )
