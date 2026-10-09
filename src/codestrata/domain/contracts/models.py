"""Typed records for the E01.1 launch ratification."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.contracts.enums import (
    ConfidenceContractLevel,
    ContributorRole,
    DepthTier,
    DriverKind,
    FreshnessState,
    MetricStatus,
    OutcomeFamily,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class MetricComputation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MetricStatus
    numerator: int | None = None
    denominator: int | None = None
    value: Decimal | None = None
    serialized: str | None = None
    reason: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class MeasurementEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    family: str
    outcome_role: str
    subject: str
    inputs: tuple[str, ...]
    formula: str
    formula_version: str
    evidence: tuple[str, ...]
    missing_data: str
    fixtures: tuple[str, ...]
    owning_stories: tuple[str, ...]
    driver_kind: DriverKind | None = None
    opaque_score: bool = False
    notes: tuple[str, ...] = ()

    @field_validator(
        "id",
        "name",
        "family",
        "outcome_role",
        "subject",
        "formula",
        "formula_version",
        "missing_data",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="measurement field")

    @field_validator("inputs", "evidence", "fixtures", "owning_stories", mode="before")
    @classmethod
    def normalize_required_seq(cls, value: object) -> tuple[str, ...]:
        items = [
            require_nonblank(str(item), label="measurement list item") for item in as_tuple(value)
        ]
        if not items:
            raise ValueError("measurement lists must be non-empty")
        return tuple(items)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> tuple[str, ...]:
        return tuple(
            require_nonblank(str(item), label="note")
            for item in as_tuple(value)
            if str(item).strip()
        )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value.startswith("M") or not value[1:].isdigit():
            raise ValueError("measurement id must be Mnn")
        number = int(value[1:])
        if number < 1 or number > 33:
            raise ValueError("measurement id must be M01-M33")
        return f"M{number:02d}"

    @field_validator("opaque_score")
    @classmethod
    def forbid_opaque_score(cls, value: bool) -> bool:
        if value:
            raise ValueError("opaque scores are not permitted")
        return value


class LanguageDepthPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    launch_tier: DepthTier
    detection: bool
    structural: str
    complexity: str
    frameworks: str
    current_verified: str
    promotion_rule: str


class FeedPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_name: str
    cache_kind: str
    redistribution: str
    range_semantics: str
    freshness_max_age_days: int = Field(ge=1)
    evaluation_time_binding: str
    silent_online_fallback: bool
    unavailable_behavior: str
    stale_behavior: str
    license_metadata: str


class HistoryProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    version: str
    traversal: str
    merge_policy: str
    window_days: int
    max_commits: int
    order: str
    root_diff: str
    future_timestamp: str
    rename_policy: str
    mailmap_policy: str
    bugfix_markers: tuple[str, ...]
    bugfix_markers_are_proven_defects: bool


class BudgetLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    yaml_document_bytes: int
    yaml_max_nesting: int
    yaml_aliases_enabled: bool
    ruleset_parent_depth: int
    max_effective_rules: int
    graph_max_depth: int
    graph_default_impact_depth: int
    graph_max_visited_nodes: int
    graph_max_visited_edges: int
    rule_soft_budget_seconds: int
    rule_hard_deadline_seconds: int
    cancellation_grace_seconds: int
    regex_match_timeout_milliseconds: int
    regex_max_steps: int
    max_source_file_bytes: int
    max_memory_rss_bytes_tier_10k: int
    max_memory_rss_bytes_tier_100k: int
    max_output_artifact_bytes: int
    wall_seconds_tier_10k: int
    wall_seconds_tier_100k: int
    process_enforced_hard_cap: bool
    cooperative_callback_only_forbidden: bool


class CoverageFreshnessReason(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    applies_to: str
    meaning: str
    cannot_prove_clean: bool = True


class ConfidenceMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    existing_token: str
    existing_enum: str
    contract_level: ConfidenceContractLevel
    notes: str


class SeverityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_and_effective_preserved: bool
    hidden_rewrite_after_override_forbidden: bool
    context_derived_default_must_be_versioned: bool
    existing_calibrator: str
    launch_rule: str


class RuleIdGrammar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    shared_pattern: str
    legacy_pattern: str
    incompatible_restriction_invented: bool
    notes: str


class OutcomeDriver(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: DriverKind
    family: OutcomeFamily
    outcome_or_context_role: str
    applicability: str
    direction: str
    comparison_unit: str
    epsilon: str
    coverage_requirement: str
    empty_scope: str
    contributor_role: ContributorRole | None = None


class M22Roles(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ranking_value: str
    ranking_contributors: tuple[str, ...]
    context_only_contributors: tuple[str, ...]
    tie_break: str
    missing_required: str
    contextual_missing_does_not_invalidate_rank: bool
    no_hidden_weights: bool


class M29Predicate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    high_churn: str
    high_centrality: str
    ranking: str
    default_role: str
    verdict_requires_yaml: bool
    no_composite_score: bool


class NoOpaqueScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_health_score: bool
    compatibility_numeric_requires_published_formula: bool
    unpublished_derivation: str


class FormulaFixture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    measurement_id: str
    case: str
    expected_status: MetricStatus
    expected_numerator: int | None = None
    expected_denominator: int | None = None
    expected_serialized: str | None = None
    expected_reason: str | None = None
    expected_extra: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class LaunchRatification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ratification_id: str
    package_revision: str
    contract_version: str
    proposed_by: str
    independent_reviewer: str
    reviewer_status: str
    no_opaque_score: NoOpaqueScore
    measurements: tuple[MeasurementEntry, ...]
    depth_matrix: tuple[LanguageDepthPin, ...]
    feed: FeedPolicy
    history: HistoryProfile
    budgets: BudgetLimits
    coverage_freshness_reasons: tuple[CoverageFreshnessReason, ...]
    confidence_map: tuple[ConfidenceMapping, ...]
    severity: SeverityPolicy
    rule_id_grammar: RuleIdGrammar
    outcome_drivers: tuple[OutcomeDriver, ...]
    m22_roles: M22Roles
    m29_predicate: M29Predicate
    formula_fixtures: tuple[FormulaFixture, ...]
    retained_existing_rule_ids: tuple[str, ...]
    freshness_states: tuple[FreshnessState, ...] = tuple(FreshnessState)

    @field_validator("measurements")
    @classmethod
    def require_all_measurements(
        cls, value: tuple[MeasurementEntry, ...]
    ) -> tuple[MeasurementEntry, ...]:
        ids = [item.id for item in value]
        expected = [f"M{i:02d}" for i in range(1, 34)]
        if ids != expected:
            raise ValueError(f"measurements must be exactly M01-M33 in order, got {ids}")
        return value
