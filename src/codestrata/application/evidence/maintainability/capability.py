"""Capability manifests for M22 hotspots and M23 staleness/ordering (E08.3)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_MANIFEST_SCHEMA = "codestrata.maintainability.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e08.3.v1"
MAINTAINABILITY_ENVELOPE_SCHEMA = "codestrata.maintainability.envelope.v1"
MAINTAINABILITY_COVERAGE_SCHEMA = "codestrata.maintainability.coverage.v1"
CAP_M22 = "maintainability.m22.hotspot"
CAP_M23 = "maintainability.m23.dependency_age"
HOTSPOT_FORMULA_VERSION = "hotspot.complexity_churn.v1"
STALENESS_FORMULA_VERSION = "dependency.age.v1"
CONCERN_ORDER_VERSION = "concern.order.v1"
EVIDENCE_CLASS_ORDER_VERSION = "evidence_class.order.v1"
HISTORY_PROFILE_V1 = "m24.history.profile.v1"
COMPLEXITY_MEASUREMENT_VERSION = "cyclomatic.v1"


class CapabilityFamily(StrEnum):
    MAINTAINABILITY = "maintainability"


class CapabilityOutcome(StrEnum):
    MAINTAINABILITY = "maintainability"


class CapabilityNetwork(StrEnum):
    NONE = "none"


class EmptyScopeBehavior(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CapabilityBudget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_file_bytes: int = Field(ge=1)
    network: CapabilityNetwork = CapabilityNetwork.NONE


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = CAPABILITY_MANIFEST_SCHEMA
    schema_version: str = CAPABILITY_MANIFEST_VERSION
    capability_id: str
    family: CapabilityFamily = CapabilityFamily.MAINTAINABILITY
    outcome: CapabilityOutcome = CapabilityOutcome.MAINTAINABILITY
    role: str = "flagship"
    version: str = CAPABILITY_MANIFEST_VERSION
    reads: tuple[str, ...]
    emits: tuple[str, ...]
    applicability: str
    fact_schema: str = "codestrata.maintainability.facts.v1"
    coverage_schema: str = MAINTAINABILITY_COVERAGE_SCHEMA
    envelope_schema: str = MAINTAINABILITY_ENVELOPE_SCHEMA
    budgets: CapabilityBudget
    network: CapabilityNetwork = CapabilityNetwork.NONE
    coverage_unit: str
    coverage_requirement: str
    empty_scope: EmptyScopeBehavior = EmptyScopeBehavior.UNKNOWN
    direction: str
    comparison_unit: str
    epsilon: str = "0"
    failures: tuple[str, ...] = ()
    health_verdict: bool = False
    yaml_rule: bool = False
    live_lookup: bool = False
    opaque_score: bool = False
    limitations: tuple[str, ...] = ()


_BUDGET = CapabilityBudget(max_file_bytes=1_048_576)

MAINTAINABILITY_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M22,
        reads=("m16_function_complexity", "m24_pinned_history", "component_mapping"),
        emits=("engineering_hotspot", "priority_explanation", "coverage"),
        applicability=(
            "components with supported function complexity and pinned M24 "
            "history in the same repository/window"
        ),
        coverage_unit="component",
        coverage_requirement=(
            "complete comparable rank requires known complexity sum and known "
            "component changed lines; partial/UNKNOWN stay in a separate list "
            "ordered by subject ID; context_only contributors never change rank"
        ),
        direction="descriptive",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "missing_history",
            "partial_history",
            "partial_complexity",
            "missing_structure",
            "dangling_finding_reference",
        ),
        limitations=(
            "ranking_is_complexity_times_churn_only",
            "no_opaque_score",
            "no_runtime_failure_probability",
            "no_cost_to_fix",
            "no_developer_blame",
            "context_only_cannot_change_rank",
            "file_ownership_is_not_file_hotspot_ranking",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M23,
        reads=("pinned_release_date_metadata", "m10_m22", "pinned_evaluation_time"),
        emits=("staleness_days", "concern_tuple", "coverage"),
        applicability=(
            "resolved installed versions with permitted pinned publication "
            "times and an explicit evaluation_time"
        ),
        coverage_unit="resolved_package",
        coverage_requirement=(
            "staleness days only when both timestamps are known and valid; "
            "missing or future dates are UNKNOWN. Concern order is severity, "
            "evidence class, comparable hotspot, finding ID"
        ),
        direction="descriptive",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "missing_timestamp",
            "future_or_invalid_timestamp",
            "unpinned_evaluation_time",
        ),
        limitations=(
            "age_does_not_prove_insecure_or_unsupported",
            "no_weighted_overall_score",
            "incomparable_hotspots_sort_after_comparable",
            "html_does_not_recompute_priority",
        ),
        budgets=_BUDGET,
    ),
)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return MAINTAINABILITY_CAPABILITY_MANIFESTS


__all__ = [
    "CAP_M22",
    "CAP_M23",
    "CAPABILITY_MANIFEST_VERSION",
    "COMPLEXITY_MEASUREMENT_VERSION",
    "CONCERN_ORDER_VERSION",
    "EVIDENCE_CLASS_ORDER_VERSION",
    "HISTORY_PROFILE_V1",
    "HOTSPOT_FORMULA_VERSION",
    "MAINTAINABILITY_ENVELOPE_SCHEMA",
    "STALENESS_FORMULA_VERSION",
    "capability_manifests",
]
