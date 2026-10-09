"""Capability manifests for M16/M17/M18 structural quality evidence (E08.1)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_MANIFEST_SCHEMA = "codestrata.quality.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e08.1.v1"
QUALITY_ENVELOPE_SCHEMA = "codestrata.quality.envelope.v1"
QUALITY_COVERAGE_SCHEMA = "codestrata.quality.coverage.v1"
CAP_M16 = "quality.m16.size_complexity"
CAP_M17 = "quality.m17.nesting"
CAP_M18 = "quality.m18.clone_indicator"
FACT_KIND_FUNCTION = "quality.function"
FACT_KIND_FILE_SIZE = "quality.file_size"
FACT_KIND_CLONE = "quality.clone_run"
FACT_KIND_COVERAGE = "quality.coverage"


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
    fact_schema: str = "codestrata.quality.facts.v1"
    coverage_schema: str = QUALITY_COVERAGE_SCHEMA
    envelope_schema: str = QUALITY_ENVELOPE_SCHEMA
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
    limitations: tuple[str, ...] = ()


_BUDGET = CapabilityBudget(max_file_bytes=1_048_576)

QUALITY_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M16,
        reads=("supported_ast", "source_tokens"),
        emits=(FACT_KIND_FUNCTION, FACT_KIND_FILE_SIZE, FACT_KIND_COVERAGE),
        applicability="supported Java, JS/TS and Python functions with a frozen branch map",
        coverage_unit="established_function",
        coverage_requirement=(
            "measured functions / functions the parser attempted; unparsed "
            "functions are UNKNOWN, never a cross-language fallback"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        epsilon="0",
        failures=(
            "malformed_syntax",
            "unsupported_language_map",
            "file_over_budget",
            "scan_cutoff",
        ),
        limitations=(
            "no_maintainability_index",
            "language_specific_branch_map",
            "nested_functions_excluded_from_enclosing",
            "heuristic_thresholds",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M17,
        reads=("supported_ast",),
        emits=(FACT_KIND_FUNCTION, FACT_KIND_COVERAGE),
        applicability="supported functions under the declared nesting construct map",
        coverage_unit="established_function",
        coverage_requirement=(
            "unknown parse sections invalidate a negative nesting claim; "
            "absent functions are NOT_APPLICABLE"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_count_favorable",
        comparison_unit="count",
        yaml_rule=True,
        failures=("malformed_syntax", "partial_parse", "scan_cutoff"),
        limitations=(
            "no_maintainability_index",
            "nested_lambda_is_separate_function",
        ),
        budgets=_BUDGET,
    ),
    CapabilityManifest(
        capability_id=CAP_M18,
        reads=("normalized_eligible_source_tokens",),
        emits=(FACT_KIND_CLONE, FACT_KIND_COVERAGE),
        applicability="eligible non-generated source token streams",
        coverage_unit="eligible_source_line",
        coverage_requirement=(
            "duplicated lines after overlap merge / eligible source lines; "
            "unsupported tokenization or scan cutoff is partial, not zero"
        ),
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        direction="lower_ratio_favorable",
        comparison_unit="ratio",
        yaml_rule=True,
        epsilon="0.01",
        failures=("unsupported_tokenization", "scan_cutoff", "no_eligible_lines"),
        limitations=(
            "indicative_clone_not_proof",
            "identifiers_kept_rename_is_not_clone",
            "generated_excluded",
        ),
        budgets=_BUDGET,
    ),
)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return QUALITY_CAPABILITY_MANIFESTS


__all__ = [
    "CAP_M16",
    "CAP_M17",
    "CAP_M18",
    "CAPABILITY_MANIFEST_VERSION",
    "QUALITY_ENVELOPE_SCHEMA",
    "capability_manifests",
]
