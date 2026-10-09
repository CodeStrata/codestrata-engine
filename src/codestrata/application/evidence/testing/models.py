"""Application-local testing facts for M19/M20/M21 (E08.2).

Static inventory, skip markers and declared CI gaps. This is not measured
runtime test coverage and never invents a coverage percentage.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MetricStatusName(StrEnum):
    VALUE = "value"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CoverageScope(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class AssociationMethod(StrEnum):
    IMPORT_REFERENCE = "import_reference"
    NAMING_CONVENTION = "naming_convention"
    AMBIGUOUS = "ambiguous"
    GENERATED = "generated"
    UNSUPPORTED = "unsupported"


class AssociationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SkipKind(StrEnum):
    EXPLICIT_DISABLED = "explicit_disabled"
    CONDITIONAL = "conditional"
    UNKNOWN_ELIGIBILITY = "unknown_eligibility"
    ENABLED = "enabled"
    UNSUPPORTED_DECORATOR = "unsupported_decorator"


class GapStatus(StrEnum):
    INVOKED = "invoked"
    PROVEN_ABSENT = "proven_absent"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class SourceSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class FrameworkCount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    framework: str
    count: int = Field(ge=0)


class TestDeclaration(BaseModel):
    """One statically observed test function/method. Not a runtime result."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    test_id: str
    path: str
    name: str
    framework: str
    language: str
    span: SourceSpan
    generated: bool = False
    unsupported_framework: bool = False


class AssociationRecord(BaseModel):
    """Source-to-test link with method and evidence strength."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    association_id: str
    production_path: str
    test_path: str
    test_id: str | None = None
    method: AssociationMethod
    confidence: AssociationConfidence
    witness: str
    formula_version: str


class AssociationMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MetricStatusName
    associated: int | None = Field(default=None, ge=0)
    eligible: int | None = Field(default=None, ge=0)
    serialized: str | None = None
    full_scope_status: CoverageScope
    reason: str
    formula_version: str
    runtime_coverage: None = None
    framework_counts: tuple[FrameworkCount, ...] = ()
    associations: tuple[AssociationRecord, ...] = ()
    unassociated: tuple[str, ...] = ()
    unsupported_frameworks: tuple[str, ...] = ()
    generated_tests: int = Field(ge=0, default=0)


class SkipRecord(BaseModel):
    """Explicit skip/disable observation. Conditional vs dynamic stay distinct."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skip_id: str
    test_id: str
    path: str
    name: str
    kind: SkipKind
    annotation: str
    span: SourceSpan
    reason: str | None = None
    static_condition: str | None = None
    formula_version: str


class SkipMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MetricStatusName
    explicit_disabled: int | None = Field(default=None, ge=0)
    conditional: int = Field(ge=0, default=0)
    unknown_eligibility: int = Field(ge=0, default=0)
    enabled: int = Field(ge=0, default=0)
    unsupported_decorator: int = Field(ge=0, default=0)
    full_scope_status: CoverageScope
    reason: str
    formula_version: str
    records: tuple[SkipRecord, ...] = ()


class DeclaredCapability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    kind: str
    tool: str
    path: str
    detail: str


class InvocationWitness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line: int | None = None
    job: str | None = None
    literal_command: str | None = None
    condition: str | None = None
    tool_category: str
    parser_rule: str
    unresolved: bool = False
    unresolved_reason: str | None = None


class CiGapRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gap_id: str
    capability_id: str
    kind: str
    tool: str
    status: GapStatus
    reason: str
    checked_scope: str
    invocations: tuple[InvocationWitness, ...] = ()


class CiGapMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MetricStatusName
    proven_absent: int | None = Field(default=None, ge=0)
    unknown: int = Field(ge=0, default=0)
    invoked: int = Field(ge=0, default=0)
    full_scope_status: CoverageScope
    reason: str
    formula_version: str
    coverage_percent: None = None
    declared: tuple[DeclaredCapability, ...] = ()
    gaps: tuple[CiGapRecord, ...] = ()
    ci_documents: int = Field(ge=0, default=0)


class TestingThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    disabled_low_min: int = Field(default=1, ge=1)
    disabled_medium_min: int = Field(default=10, ge=1)


class TestingEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    repository_id: str
    tests: tuple[TestDeclaration, ...] = ()
    association: AssociationMetric
    skipped: SkipMetric
    ci_gap: CiGapMetric
    thresholds: TestingThresholds = Field(default_factory=TestingThresholds)
    executed_repository_code: bool = False
    live_lookup: bool = False
    runtime_coverage: None = None
    coverage_percent: None = None
    limitations: tuple[str, ...] = ()


__all__ = [
    "AssociationConfidence",
    "AssociationMethod",
    "AssociationMetric",
    "AssociationRecord",
    "CiGapMetric",
    "CiGapRecord",
    "CoverageScope",
    "DeclaredCapability",
    "FrameworkCount",
    "GapStatus",
    "InvocationWitness",
    "MetricStatusName",
    "SkipKind",
    "SkipMetric",
    "SkipRecord",
    "SourceSpan",
    "TestDeclaration",
    "TestingEvidence",
    "TestingThresholds",
]
