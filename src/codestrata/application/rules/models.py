"""Application DTOs for Shared Rule Platform planning and execution."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus, RuleSkipReason
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult


class RuleInspectionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: RuleMetadata
    production: bool = True


class RulePlanEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    selected: bool
    skip_reason: RuleSkipReason | None = None
    message: str | None = None
    invalidation_fingerprint: str | None = None


class RuleExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selected_rule_ids: tuple[str, ...] = ()
    skipped: tuple[RulePlanEntry, ...] = ()
    execution_order: tuple[str, ...] = ()
    incremental_mode: str = "conservative_recompute"
    reuse_claimed: bool = False
    full_execution_fallback_reason: str | None = "phase_4_1_conservative_recompute"


class RuleTelemetry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    registered_rules: int = 0
    planned_rules: int = 0
    executed_rules: int = 0
    matched_rules: int = 0
    matches_produced: int = 0
    not_applicable_rules: int = 0
    suppressed_rules: int = 0
    failed_rules: int = 0
    duration_ms: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    actual_reuse_count: int = 0
    fallback_count: int = 0
    validation_failures: int = 0


class RuleRuleResultRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    status: RuleResultStatus
    evaluation: SharedRuleEvaluationResult
    category: RuleCategory | None = None


class RulePlatformExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: RuleExecutionPlan
    records: tuple[RuleRuleResultRecord, ...] = ()
    matches: tuple[RuleMatch, ...] = ()
    suppressed_matches: tuple[RuleMatch, ...] = ()
    suppressions: tuple[RuleSuppression, ...] = ()
    telemetry: RuleTelemetry = Field(default_factory=RuleTelemetry)
    validation_summary: str = "ok"


class RuleExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    reason_code: str
    message: str
    details: dict[str, str] = Field(default_factory=dict)
