"""AnalyzerDescriptor: reads, emits, applicability, depth, schemas, budgets, network."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.enums import NetworkMode
from codestrata.domain.graph.validation import as_tuple, require_nonblank

DESCRIPTOR_SCHEMA = "codestrata.analyzer-descriptor.v1"
DESCRIPTOR_VERSION = "1.0.0"


class DepthPinRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    launch_tier: str
    current_verified: str


class BudgetRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    yaml_document_bytes: int
    yaml_max_nesting: int
    yaml_aliases_enabled: bool
    rule_soft_budget_seconds: int
    rule_hard_deadline_seconds: int
    cancellation_grace_seconds: int
    regex_match_timeout_milliseconds: int
    regex_max_steps: int
    process_enforced_hard_cap: bool


class NetworkPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: NetworkMode
    silent_online_fallback: bool = False
    notes: str


class CoverageDeclaration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    required_capability_ids: tuple[str, ...]
    unknown_denominator_is_unknown: bool = True
    cannot_prove_clean_when_incomplete: bool = True


class FailureDeclaration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    meaning: str
    safe_status: str


class SchemaRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    path: str


class AnalyzerDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = DESCRIPTOR_SCHEMA
    schema_version: str = DESCRIPTOR_VERSION
    descriptor_id: str
    family: str
    reads: tuple[str, ...]
    emits: tuple[str, ...]
    applicability: str
    depth: tuple[DepthPinRef, ...]
    schemas: tuple[SchemaRef, ...]
    budgets: BudgetRef
    network: NetworkPolicy
    coverage: CoverageDeclaration
    failures: tuple[FailureDeclaration, ...]
    no_opaque_score: bool = True

    @field_validator("descriptor_id", "family", "applicability", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="descriptor field")

    @field_validator("reads", "emits", mode="before")
    @classmethod
    def normalize_lists(cls, value: object) -> tuple[str, ...]:
        items = [require_nonblank(str(item), label="descriptor list") for item in as_tuple(value)]
        if not items:
            raise ValueError("reads/emits must be non-empty")
        return tuple(items)

    @field_validator("no_opaque_score")
    @classmethod
    def require_no_score(cls, value: bool) -> bool:
        if not value:
            raise ValueError("descriptors must freeze no-opaque-score")
        return value


def budgets_from_ratification() -> BudgetRef:
    budgets = load_launch_ratification().budgets
    return BudgetRef(
        yaml_document_bytes=budgets.yaml_document_bytes,
        yaml_max_nesting=budgets.yaml_max_nesting,
        yaml_aliases_enabled=budgets.yaml_aliases_enabled,
        rule_soft_budget_seconds=budgets.rule_soft_budget_seconds,
        rule_hard_deadline_seconds=budgets.rule_hard_deadline_seconds,
        cancellation_grace_seconds=budgets.cancellation_grace_seconds,
        regex_match_timeout_milliseconds=budgets.regex_match_timeout_milliseconds,
        regex_max_steps=budgets.regex_max_steps,
        process_enforced_hard_cap=budgets.process_enforced_hard_cap,
    )


def depth_from_ratification() -> tuple[DepthPinRef, ...]:
    return tuple(
        DepthPinRef(
            language=pin.language,
            launch_tier=pin.launch_tier.value,
            current_verified=pin.current_verified,
        )
        for pin in load_launch_ratification().depth_matrix
    )


def _schemas(*names: str) -> tuple[SchemaRef, ...]:
    return tuple(
        SchemaRef(
            name=name,
            version="1.0.0",
            path=f"engine/schemas/contracts/codestrata.io/v1.2/{name}.json",
        )
        for name in names
    )


_FAILURES = (
    FailureDeclaration(
        code="budget_exceeded",
        meaning="YAML, regex, memory or wall budget stopped evaluation.",
        safe_status="error",
    ),
    FailureDeclaration(
        code="unsupported_syntax",
        meaning="Declared syntax is outside the verified depth pin.",
        safe_status="unknown",
    ),
    FailureDeclaration(
        code="missing_input",
        meaning="Required fact, feed or Git window is absent.",
        safe_status="unknown",
    ),
    FailureDeclaration(
        code="parse_error",
        meaning="Input parsing failed; retain safe reason and affected scope.",
        safe_status="error",
    ),
    FailureDeclaration(
        code="unknown_fields",
        meaning="Consumer payload contained fields outside the versioned schema.",
        safe_status="error",
    ),
    FailureDeclaration(
        code="unsupported_major_version",
        meaning="Envelope or descriptor major version is not in the supported set.",
        safe_status="error",
    ),
)

_NETWORK = NetworkPolicy(
    mode=NetworkMode.OFFLINE,
    silent_online_fallback=False,
    notes="No silent online fallback. Feed and Git inputs are pinned local snapshots.",
)


def launch_descriptors() -> tuple[AnalyzerDescriptor, ...]:
    budgets = budgets_from_ratification()
    depth = depth_from_ratification()
    shared_emits = (
        "CanonicalEnvelope",
        "FactRecord",
        "EvidenceRecord",
        "GraphRecord",
        "EngineeringHotspot",
        "OwnershipConcentration",
        "ChangeSummary",
        "CapabilityCoverage",
    )
    return (
        AnalyzerDescriptor(
            descriptor_id="codestrata.analyzer.inventory.v1",
            family="inventory",
            reads=("source_tree", "exclusions", "manifests", "lockfiles", "ci_config"),
            emits=shared_emits,
            applicability="Every assessed repository; detection is not structural support.",
            depth=depth,
            schemas=_schemas(*shared_emits, "AnalyzerDescriptor"),
            budgets=budgets,
            network=_NETWORK,
            coverage=CoverageDeclaration(
                required_capability_ids=(
                    "inventory.m01.classification",
                    "inventory.m02.dependencies",
                    "inventory.m03.ci",
                    "inventory.m04.surfaces",
                )
            ),
            failures=_FAILURES,
        ),
        AnalyzerDescriptor(
            descriptor_id="codestrata.analyzer.architecture.v1",
            family="architecture",
            reads=("module_graph", "declared_boundaries", "direction_constraints"),
            emits=shared_emits,
            applicability="When a resolved module graph exists.",
            depth=depth,
            schemas=_schemas(*shared_emits, "AnalyzerDescriptor"),
            budgets=budgets,
            network=_NETWORK,
            coverage=CoverageDeclaration(
                required_capability_ids=(
                    "architecture.m05.cycles",
                    "architecture.m06.coupling",
                    "architecture.m07.boundaries",
                    "architecture.m09.centrality",
                )
            ),
            failures=_FAILURES,
        ),
        AnalyzerDescriptor(
            descriptor_id="codestrata.analyzer.security.v1",
            family="security",
            reads=("source_tree", "config_files", "pinned_osv_snapshot"),
            emits=shared_emits,
            applicability=(
                "Secret/config rules always; vulnerability matching requires a pinned feed."
            ),
            depth=depth,
            schemas=_schemas(*shared_emits, "AnalyzerDescriptor"),
            budgets=budgets,
            network=_NETWORK,
            coverage=CoverageDeclaration(
                required_capability_ids=(
                    "security.m10.secrets",
                    "security.m11.insecure-config",
                    "security.m13.vulnerabilities",
                )
            ),
            failures=_FAILURES,
        ),
        AnalyzerDescriptor(
            descriptor_id="codestrata.analyzer.quality.v1",
            family="quality",
            reads=("source_tree", "complexity_extractors", "git_history_window"),
            emits=shared_emits,
            applicability="Supported languages at their ratified depth pins.",
            depth=depth,
            schemas=_schemas(*shared_emits, "AnalyzerDescriptor"),
            budgets=budgets,
            network=_NETWORK,
            coverage=CoverageDeclaration(
                required_capability_ids=(
                    "quality.m16.complexity",
                    "quality.m22.hotspots",
                    "quality.m25.ownership",
                )
            ),
            failures=_FAILURES,
        ),
        AnalyzerDescriptor(
            descriptor_id="codestrata.analyzer.maintainability.v1",
            family="maintainability",
            reads=(
                "git_history_window",
                "module_graph",
                "test_associations",
                "supplied_pr_context",
            ),
            emits=shared_emits,
            applicability="When a pinned history window or change set is supplied.",
            depth=depth,
            schemas=_schemas(*shared_emits, "AnalyzerDescriptor"),
            budgets=budgets,
            network=_NETWORK,
            coverage=CoverageDeclaration(
                required_capability_ids=(
                    "maintainability.m24.churn",
                    "maintainability.m27.change-summary",
                    "maintainability.m29.blast-radius",
                )
            ),
            failures=_FAILURES,
        ),
    )
