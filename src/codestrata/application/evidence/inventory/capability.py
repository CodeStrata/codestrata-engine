"""Versioned capability manifests for inventory M01–M04 (E05.3).

These are Engine-local descriptors until E01.2 publishes the shared
AnalyzerDescriptor catalog. They declare reads/emits, applicability, depth,
schemas, budgets, network, coverage and failure behavior. Inventory is
descriptive context: no health verdict and no YAML rule evaluation.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.inventory.facts import (
    CAP_M01,
    CAP_M02,
    CAP_M03,
    CAP_M04,
    INVENTORY_FACT_SCHEMA_VERSION,
)

CAPABILITY_MANIFEST_SCHEMA = "codestrata.inventory.capability.v1"
CAPABILITY_MANIFEST_VERSION = "e05.3.v1"
INVENTORY_ENVELOPE_SCHEMA = "codestrata.inventory.envelope.v1"
INVENTORY_COVERAGE_SCHEMA = "codestrata.inventory.coverage.v1"
DEFAULT_MAX_FILE_BYTES = 1_048_576
FACT_KIND_FILE = "inventory.file"
FACT_KIND_COMPONENT = "inventory.component"
FACT_KIND_DECLARATION = "inventory.declaration"
FACT_KIND_RESOLUTION = "inventory.resolution"
FACT_KIND_IMPORT = "inventory.import"
FACT_KIND_SURFACE = "inventory.surface"
FACT_KIND_CI = "inventory.ci_invocation"
FACT_KIND_COVERAGE = "inventory.coverage"


class CapabilityFamily(StrEnum):
    INVENTORY = "inventory"


class CapabilityOutcome(StrEnum):
    CONTEXT = "context"


class CapabilityDirection(StrEnum):
    NEUTRAL = "neutral"


class CapabilityNetwork(StrEnum):
    NONE = "none"


class CapabilityDepth(StrEnum):
    DETECTION = "detection"
    STRUCTURAL = "structural"
    MIXED = "mixed"


class EmptyScopeBehavior(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CapabilityBudget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_file_bytes: int = Field(ge=1)
    yaml_document_bytes: int | None = Field(default=None, ge=1)
    network: CapabilityNetwork = CapabilityNetwork.NONE


class CapabilityManifest(BaseModel):
    """Descriptor a consumer can validate without parser internals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = CAPABILITY_MANIFEST_SCHEMA
    schema_version: str = CAPABILITY_MANIFEST_VERSION
    capability_id: str
    family: CapabilityFamily = CapabilityFamily.INVENTORY
    outcome: CapabilityOutcome = CapabilityOutcome.CONTEXT
    role: str = "contextual"
    version: str = CAPABILITY_MANIFEST_VERSION
    reads: tuple[str, ...] = ()
    emits: tuple[str, ...]
    applicability: str
    depth: CapabilityDepth
    fact_schema: str = INVENTORY_FACT_SCHEMA_VERSION
    coverage_schema: str = INVENTORY_COVERAGE_SCHEMA
    envelope_schema: str = INVENTORY_ENVELOPE_SCHEMA
    budgets: CapabilityBudget
    network: CapabilityNetwork = CapabilityNetwork.NONE
    coverage_unit: str
    coverage_requirement: str
    empty_scope: EmptyScopeBehavior
    direction: CapabilityDirection = CapabilityDirection.NEUTRAL
    comparison_unit: str
    epsilon: str = "0"
    failures: tuple[str, ...] = ()
    health_verdict: bool = False
    yaml_rule: bool = False
    freshness: str = "not_applicable"
    freshness_reason: str = "inventory_is_not_time_sensitive"
    limitations: tuple[str, ...] = ()


_COMMON_BUDGET = CapabilityBudget(max_file_bytes=DEFAULT_MAX_FILE_BYTES)


INVENTORY_CAPABILITY_MANIFESTS: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        capability_id=CAP_M01,
        reads=(),
        emits=(FACT_KIND_FILE, FACT_KIND_COMPONENT, FACT_KIND_COVERAGE),
        applicability="repository_source_tree",
        depth=CapabilityDepth.MIXED,
        budgets=_COMMON_BUDGET,
        coverage_unit="eligible_source_test_files",
        coverage_requirement="supported_eligible_files / eligible_files",
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        comparison_unit="ratio",
        epsilon="0.01",
        failures=("unreadable_subtree", "symlink_escape", "oversize", "binary"),
        limitations=(
            "classification_metric_only_no_health_verdict",
            "detection_is_not_structural_support",
        ),
    ),
    CapabilityManifest(
        capability_id=CAP_M02,
        reads=(FACT_KIND_FILE,),
        emits=(FACT_KIND_DECLARATION, FACT_KIND_RESOLUTION, FACT_KIND_COVERAGE),
        applicability="manifests_and_lockfiles",
        depth=CapabilityDepth.MIXED,
        budgets=_COMMON_BUDGET,
        coverage_unit="declaration_id",
        coverage_requirement="resolved_declaration_ids / eligible_declaration_ids",
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        comparison_unit="count",
        failures=("missing_lock", "unsupported_ecosystem", "corrupt_manifest"),
        limitations=(
            "missing_lock_is_not_resolved_absence",
            "no_invented_health_score",
            "parseable_unsupported_ecosystem_is_detection_only",
        ),
    ),
    CapabilityManifest(
        capability_id=CAP_M03,
        reads=(FACT_KIND_FILE,),
        emits=(FACT_KIND_CI, FACT_KIND_COVERAGE),
        applicability="ci_build_config_source",
        depth=CapabilityDepth.MIXED,
        coverage_unit="ci_invocation",
        coverage_requirement="resolved_invocations / observed_invocations",
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        comparison_unit="count",
        budgets=CapabilityBudget(
            max_file_bytes=DEFAULT_MAX_FILE_BYTES,
            yaml_document_bytes=DEFAULT_MAX_FILE_BYTES,
        ),
        failures=("malformed_yaml", "unresolved_expression", "delegated_script"),
        limitations=(
            "configuration_is_not_execution",
            "no_health_verdict",
        ),
    ),
    CapabilityManifest(
        capability_id=CAP_M04,
        reads=(FACT_KIND_FILE,),
        emits=(FACT_KIND_SURFACE, FACT_KIND_COVERAGE),
        applicability="supported_source_ast_and_config",
        depth=CapabilityDepth.MIXED,
        coverage_unit="api_config_surface",
        coverage_requirement="complete_surfaces / eligible_source_files",
        empty_scope=EmptyScopeBehavior.NOT_APPLICABLE,
        comparison_unit="count",
        budgets=_COMMON_BUDGET,
        failures=("dynamic_route", "unresolved_framework", "parse_failure", "generated_config"),
        limitations=(
            "no_runtime_availability_score",
            "dynamic_or_unsupported_framework_is_unknown",
        ),
    ),
)


def capability_manifest(capability_id: str) -> CapabilityManifest:
    for item in INVENTORY_CAPABILITY_MANIFESTS:
        if item.capability_id == capability_id:
            return item
    raise KeyError(capability_id)


def capability_manifests() -> tuple[CapabilityManifest, ...]:
    return INVENTORY_CAPABILITY_MANIFESTS
