"""Capability manifests for M19/M20/M21 testing evidence (E08.2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_MANIFEST_SCHEMA = "codestrata.testing.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e08.2.v1"
TESTING_ENVELOPE_SCHEMA = "codestrata.testing.envelope.v1"
TESTING_COVERAGE_SCHEMA = "codestrata.testing.coverage.v1"
CAP_M19 = "quality.m19.test_association"
CAP_M20 = "testing.m20.disabled"
CAP_M21 = "testing.m21.ci_gap"
FACT_KIND_TEST = "testing.declaration"
FACT_KIND_ASSOCIATION = "testing.association"
FACT_KIND_SKIP = "testing.skip"
FACT_KIND_CI_GAP = "testing.ci_gap"
FACT_KIND_COVERAGE = "testing.coverage"
ASSOCIATION_FORMULA_VERSION = "test.association.v1"
SKIP_FORMULA_VERSION = "testing.disabled.v1"
CI_GAP_FORMULA_VERSION = "testing.ci_gap.v1"
SUPPORTED_TEST_LANGUAGES = frozenset({"java", "javascript", "typescript", "python"})


class CapabilityFamily(StrEnum):
    QUALITY = "quality"


class CapabilityOutcome(StrEnum):
    QUALITY = "quality"


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
    family: CapabilityFamily = CapabilityFamily.QUALITY
    outcome: CapabilityOutcome = CapabilityOutcome.QUALITY
    role: str = "flagship"
    version: str = CAPABILITY_MANIFEST_VERSION
    reads: tuple[str, ...]
    emits: tuple[str, ...]
    applicability: str
    fact_schema: str = "codestrata.testing.facts.v1"
    coverage_schema: str = TESTING_COVERAGE_SCHEMA
    envelope_schema: str = TESTING_ENVELOPE_SCHEMA
    budgets: CapabilityBudget
    network: CapabilityNetwork = CapabilityNetwork.NONE
    coverage_unit: str
    coverage_requirement: str
    empty_scope: EmptyScopeBehavior = EmptyScopeBehavior.NOT_APPLICABLE
    direction: str
    comparison_unit: str
    epsilon: str = "0"
    failures: tuple[str, ...] = ()
    health_verdict: bool = False
    yaml_rule: bool = False
    live_lookup: bool = False
    runtime_coverage: bool = False
    limitations: tuple[str, ...] = ()


_BUDGET = CapabilityBudget(max_file_bytes=1_048_576)

TESTING_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M19,
        reads=("test_declarations", "imports", "naming_conventions"),
        emits=(FACT_KIND_TEST, FACT_KIND_ASSOCIATION, FACT_KIND_COVERAGE),
        applicability=(
            "supported Java, JS/TS and Python production units with static "
            "test association"
        ),
        coverage_unit="eligible_production_unit",
        coverage_requirement=(
            "production units with a supported static association / eligible "
            "production units; import/reference is high, naming convention is "
            "medium; this is not measured runtime test coverage"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="higher_ratio_favorable",
        comparison_unit="ratio",
        yaml_rule=True,
        epsilon="0.01",
        failures=(
            "unsupported_framework",
            "generated_tests",
            "ambiguous_association",
            "file_over_budget",
        ),
        limitations=(
            "static_association_not_runtime_coverage",
            "unsupported_framework_unknown_scope",
            "generated_tests_unknown_scope",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M20,
        reads=("supported_test_source_syntax",),
        emits=(FACT_KIND_SKIP, FACT_KIND_COVERAGE),
        applicability="supported test source with skip/disable syntax",
        coverage_unit="declared_test",
        coverage_requirement=(
            "explicit disabled/skipped tests with static literal reason where "
            "present; conditional skips are distinct; dynamic skip conditions "
            "are unknown eligibility, not unconditional disabled"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "dynamic_skip_condition",
            "unsupported_decorator",
            "file_over_budget",
        ),
        limitations=(
            "static_markers_only",
            "conditional_skips_are_not_unconditional_disabled",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M21,
        reads=("m03_ci_observations", "test_coverage_configuration"),
        emits=(FACT_KIND_CI_GAP, FACT_KIND_COVERAGE),
        applicability="declared test/coverage tools plus inspected CI/build config",
        coverage_unit="declared_capability",
        coverage_requirement=(
            "declared test/coverage capabilities with no statically observed "
            "invocation in complete supported CI; medium only when absence is "
            "proven; otherwise UNKNOWN. A missing coverage report is not 0%"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        failures=(
            "external_workflow_not_inspected",
            "delegated_script_body_not_inspected",
            "conditional_job_uncertainty",
            "no_ci_applicability",
        ),
        limitations=(
            "static_invocation_not_runtime_pass_fail",
            "missing_coverage_report_is_not_zero_percent",
            "conditional_job_uncertainty_visible",
        ),
        budgets=_BUDGET,
    ),
)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return TESTING_CAPABILITY_MANIFESTS


__all__ = [
    "ASSOCIATION_FORMULA_VERSION",
    "CAP_M19",
    "CAP_M20",
    "CAP_M21",
    "CAPABILITY_MANIFEST_VERSION",
    "CI_GAP_FORMULA_VERSION",
    "SKIP_FORMULA_VERSION",
    "SUPPORTED_TEST_LANGUAGES",
    "TESTING_ENVELOPE_SCHEMA",
    "capability_manifests",
]
