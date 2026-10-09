"""Application-local structural quality facts for M16/M17/M18 (E08.1)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MetricStatusName(StrEnum):
    VALUE = "value"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class FileRole(StrEnum):
    SOURCE = "source"
    TEST = "test"
    GENERATED = "generated"
    VENDOR = "vendor"
    OTHER = "other"


class FunctionStatus(StrEnum):
    MEASURED = "measured"
    UNKNOWN = "unknown"


class CoverageScope(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class SourceSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class BranchWitness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    syntax: str
    line: int = Field(ge=1)


class FunctionRecord(BaseModel):
    """One established function with versioned cyclomatic/nesting/size."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    function_id: str
    language: str
    path: str
    name: str
    qualified_name: str
    span: SourceSpan
    role: FileRole
    status: FunctionStatus
    cyclomatic: int | None = Field(default=None, ge=1)
    branch_count: int | None = Field(default=None, ge=0)
    nloc: int | None = Field(default=None, ge=0)
    max_nesting_depth: int | None = Field(default=None, ge=0)
    cyclomatic_version: str
    nesting_version: str
    size_version: str
    branch_map_language: str
    branches: tuple[BranchWitness, ...] = ()
    nesting_witness: tuple[BranchWitness, ...] = ()
    unknown_reason: str | None = None


class FileSizeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    language: str | None
    role: FileRole
    nloc: int | None = Field(default=None, ge=0)
    physical_lines: int = Field(ge=0)
    function_count: int = Field(ge=0)
    unknown_functions: int = Field(ge=0)
    size_version: str
    parse_status: MetricStatusName
    unknown_reason: str | None = None


class CloneSpan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    token_count: int = Field(ge=0)


class CloneRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    left: CloneSpan
    right: CloneSpan
    token_count: int = Field(ge=0)
    line_span: int = Field(ge=0)
    normalization_version: str


class CloneMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: MetricStatusName
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    serialized: str | None = None
    full_scope_status: CoverageScope
    reason: str
    normalization_version: str
    formula_version: str
    min_tokens: int = Field(ge=1)
    min_lines: int = Field(ge=1)
    runs: tuple[CloneRun, ...] = ()
    merged_spans: tuple[CloneSpan, ...] = ()
    cutoff: bool = False
    unsupported_files: int = Field(ge=0, default=0)


class FunctionDistribution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    measured: int = Field(ge=0, default=0)
    unknown: int = Field(ge=0, default=0)
    languages: tuple[str, ...] = ()


class QualityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    complexity: int = Field(default=15, ge=1)
    function_lines: int = Field(default=80, ge=1)
    nesting: int = Field(default=4, ge=1)
    clone_ratio: str = "0.100000"


class QualityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    functions: tuple[FunctionRecord, ...] = ()
    files: tuple[FileSizeRecord, ...] = ()
    distribution: FunctionDistribution = Field(default_factory=FunctionDistribution)
    clone: CloneMetric
    thresholds: QualityThresholds = Field(default_factory=QualityThresholds)
    executed_repository_code: bool = False
    live_lookup: bool = False
    limitations: tuple[str, ...] = ()


__all__ = [
    "BranchWitness",
    "CloneMetric",
    "CloneRun",
    "CloneSpan",
    "CoverageScope",
    "FileRole",
    "FileSizeRecord",
    "FunctionDistribution",
    "FunctionRecord",
    "FunctionStatus",
    "MetricStatusName",
    "QualityEvidence",
    "QualityThresholds",
    "SourceSpan",
]
