"""Domain models for deterministic scan-to-scan comparison and M28 finding lifecycle."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from codestrata.domain.contracts.hotspot import ChangeSummary


class FindingLifecycle(StrEnum):
    """M28 finding lifecycle states over two explicit compatible states."""

    NEW = "new"
    RESOLVED = "resolved"
    IMPROVED = "improved"
    WORSENED = "worsened"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class MetricDelta(BaseModel):
    """A deterministic metric delta between two compatible canonical states."""

    metric_name: str
    unit: str
    scope: str = "repository"
    base_value: float | int | str | None = None
    candidate_value: float | int | str | None = None
    delta: float | int | str | None = None
    direction: str = "neutral"
    compatible: bool = True
    compatibility_reason: str = "compatible"
    formula_version: str = "v1"
    evidence_ids: list[str] = Field(default_factory=list)
    coverage_status: str = "pass"


class ComparedFinding(BaseModel):
    """A finding referenced by a scan comparison."""

    rule_id: str | None = None
    title: str
    category: str
    severity: str
    identity_key: str
    lifecycle: str | None = None
    previous_severity: str | None = None
    current_severity: str | None = None
    previous_magnitude: float | int | str | None = None
    current_magnitude: float | int | str | None = None
    magnitude_delta: float | int | str | None = None
    comparator: str | None = None
    compatibility_status: str | None = None
    compatibility_reasons: list[str] = Field(default_factory=list)
    cause: str | None = None
    is_policy_override: bool = False
    file_path: str | None = None
    rule_version: str | None = None


class SeverityChange(BaseModel):
    """A finding whose severity changed between scans."""

    rule_id: str | None = None
    title: str
    category: str
    identity_key: str
    previous_severity: str
    current_severity: str
    direction: Literal["increased", "decreased"]
    is_policy_override: bool = False
    cause: str = "configuration"


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


class GraphDelta(BaseModel):
    """M29 graph difference between two compatible graphs."""

    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    changed_seeds: list[str] = Field(default_factory=list)
    base_node_count: int = 0
    candidate_node_count: int = 0
    base_edge_count: int = 0
    candidate_edge_count: int = 0
    status: str = "complete"
    graph_ids: dict[str, str] = Field(default_factory=dict)


class StaticBlastRadius(BaseModel):
    """M29 bounded reverse-dependency static blast radius."""

    seeds: list[str] = Field(default_factory=list)
    traversal_direction: str = "reverse"
    max_depth: int = 4
    visited_nodes: int = 0
    visited_edges: int = 0
    cutoff: bool = False
    cutoff_reason: str | None = None
    lower_bound: bool = False
    affected_component_ids: list[str] = Field(default_factory=list)
    affected_component_count: int | None = None
    affected_test_ids: list[str] = Field(default_factory=list)
    affected_test_count: int | None = None
    test_coverage_status: str = "pass"
    boundary_dimension: str | None = None
    boundary_spread_member_ids: list[str] = Field(default_factory=list)
    boundary_spread_count: int | None = None
    boundary_spread_status: str = "pass"
    crossed_boundary_pairs: list[str] = Field(default_factory=list)
    crossed_boundary_count: int | None = None
    crossed_boundary_status: str = "pass"
    edge_witnesses: dict[str, list[str]] = Field(default_factory=dict)
    graph_side: str = "candidate"
    unresolved_mappings: list[str] = Field(default_factory=list)


class ChangeConcern(BaseModel):
    """M29 named contextual change concern joining churn and centrality."""

    subject_id: str
    concern_class: str
    role: str = "context_only"
    changed_lines: int = 0
    churn_p90: int = 0
    centrality: float = 0.0
    centrality_p90: float = 0.0
    centrality_denominator: int = 1
    window: str | None = None
    history_profile_id: str | None = None
    reasons: list[str] = Field(default_factory=list)
    witnesses: list[str] = Field(default_factory=list)
    partial_contributors: bool = False
    ranking_key: list[Any] = Field(default_factory=list)
    deleted: bool = False


class OutcomeDriverMovement(BaseModel):
    """Individual driver qualifying change evaluation under M30."""

    driver_id: str
    family: str
    kind: str = "rule"
    direction: str = "lower_count_favorable"
    unit: str = "count"
    epsilon: float | int = 0
    base_value: float | int | str | None = None
    candidate_value: float | int | str | None = None
    delta: float | int | str | None = None
    movement: str = "stable"
    qualifying: bool = False
    coverage_status: str = "pass"
    notes: str | None = None


class OutcomeMovementVerdict(BaseModel):
    """M30 thresholded outcome movement verdict for a single family or overall."""

    family: str
    verdict: str
    favorable_count: int = 0
    unfavorable_count: int = 0
    stable_count: int = 0
    qualifying_drivers: list[OutcomeDriverMovement] = Field(default_factory=list)
    excluded_contextual: list[str] = Field(default_factory=list)
    threshold_profile: dict[str, Any] = Field(default_factory=dict)
    coverage_status: str = "pass"
    reason: str | None = None


class ControlledRerunReference(BaseModel):
    """Reference to a controlled paired rerun isolating one or more dimensions."""

    rerun_id: str
    isolated_dimension: str
    base_digest: str | None = None
    candidate_digest: str | None = None
    isolated_finding_keys: list[str] = Field(default_factory=list)
    isolated_metric_names: list[str] = Field(default_factory=list)
    attribution: str = "controlled_isolated"
    notes: list[str] = Field(default_factory=list)


class CauseAttribution(BaseModel):
    """M31 attribution across source, feed, configuration, or mixed dimensions."""

    attribution: str = "undetermined"
    label: str = "undetermined"
    changed_dimensions: list[str] = Field(default_factory=list)
    controlled_rerun_performed: bool = False
    controlled_reruns: list[ControlledRerunReference] = Field(default_factory=list)
    controlled_rerun_references: list[str] = Field(default_factory=list)
    isolated_causes: dict[str, list[str]] = Field(default_factory=dict)
    base_digests: dict[str, str | None] = Field(default_factory=dict)
    candidate_digests: dict[str, str | None] = Field(default_factory=dict)
    customer_code_deterioration: bool = False
    is_feed_driven: bool = False
    evidence_notes: list[str] = Field(default_factory=list)


class ComparisonSummary(BaseModel):
    """Deterministic aggregate counts for a scan comparison."""

    new_findings: int = 0
    resolved_findings: int = 0
    worsened_findings: int = 0
    improved_findings: int = 0
    unchanged_findings: int = 0
    unknown_findings: int = 0
    worsened_severities: int = 0
    improved_severities: int = 0
    new_recommendations: int = 0
    resolved_recommendations: int = 0
    worsened_priorities: int = 0
    improved_priorities: int = 0
    fact_changes: int = 0
    metric_deltas: int = 0
    is_empty_outcome: bool = False
    overall_movement: str | None = None
    outcome_verdicts: dict[str, str] = Field(default_factory=dict)
    affected_components: int = 0
    affected_tests: int = 0
    crossed_boundary_count: int = 0
    high_concern_components: int = 0


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
    improved_findings: list[ComparedFinding] = Field(default_factory=list)
    worsened_findings: list[ComparedFinding] = Field(default_factory=list)
    unknown_findings: list[ComparedFinding] = Field(default_factory=list)
    severity_changes: list[SeverityChange] = Field(default_factory=list)
    metric_deltas: list[MetricDelta] = Field(default_factory=list)
    new_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    resolved_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    unchanged_recommendations: list[ComparedRecommendation] = Field(default_factory=list)
    priority_changes: list[PriorityChange] = Field(default_factory=list)
    fact_changes: list[FactChange] = Field(default_factory=list)
    compatibility_status: str = "compatible"
    compatibility_reasons: list[str] = Field(default_factory=list)
    artifact_digests: dict[str, str] = Field(default_factory=dict)
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
    graph_delta: GraphDelta | None = None
    blast_radius: StaticBlastRadius | None = None
    change_summary: ChangeSummary | None = None
    change_concerns: list[ChangeConcern] = Field(default_factory=list)
    outcome_verdicts: dict[str, OutcomeMovementVerdict] = Field(default_factory=dict)
    cause_attribution: CauseAttribution | None = None

    @classmethod
    def unavailable(cls, current_timestamp: str | None = None) -> ScanComparison:
        """Return a comparison result when no baseline is available."""

        return cls(
            baseline_available=False,
            current_timestamp=current_timestamp,
        )
