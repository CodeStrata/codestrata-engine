"""Typed structural complexity evidence models (Phase 4.3.2).

Unsupported metrics use ``MetricAvailability.UNSUPPORTED`` with ``value=None``.
Parse failures use ``UNAVAILABLE``. Measured zeros remain ``AVAILABLE`` with
``value=0``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.complexity.enums import (
    ComplexityCallableKind,
    ComplexityTypeKind,
    MetricAvailability,
)
from codestrata.domain.evidence.language.complexity.identifiers import (
    COMPLEXITY_BUNDLE_SCHEMA_VERSION,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class IntMetric(BaseModel):
    """Integer metric with explicit availability (never encode unsupported as 0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    availability: MetricAvailability
    value: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_availability_value(self) -> IntMetric:
        if self.availability is MetricAvailability.AVAILABLE:
            if self.value is None:
                raise ValueError("available metrics require an integer value")
        elif self.value is not None:
            raise ValueError(
                "unsupported/unavailable metrics must leave value unset (None)"
            )
        return self

    @classmethod
    def available(cls, value: int) -> IntMetric:
        return cls(availability=MetricAvailability.AVAILABLE, value=value)

    @classmethod
    def unsupported(cls) -> IntMetric:
        return cls(availability=MetricAvailability.UNSUPPORTED, value=None)

    @classmethod
    def unavailable(cls) -> IntMetric:
        return cls(availability=MetricAvailability.UNAVAILABLE, value=None)


class SourceSpan(BaseModel):
    """1-based inclusive line span when known."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return require_nonblank(str(value), label="span path").replace("\\", "/")

    @model_validator(mode="after")
    def validate_range(self) -> SourceSpan:
        if self.line_start is None and self.line_end is None:
            return self
        if self.line_start is None or self.line_end is None:
            raise ValueError("line_start and line_end must both be set")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self


class FileComplexityEvidence(BaseModel):
    """Per-file physical complexity facts (source unit for complexity)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    language: str
    path: str
    classification: SourceClassification = SourceClassification.SOURCE
    physical_line_count: IntMetric
    type_count: IntMetric = Field(default_factory=IntMetric.unsupported)
    callable_count: IntMetric = Field(default_factory=IntMetric.unsupported)
    provenance: EvidenceProvenance

    @field_validator("evidence_id", mode="before")
    @classmethod
    def normalize_evidence_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence_id")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return require_nonblank(str(value), label="path").replace("\\", "/")

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> str:
        return require_nonblank(str(value), label="language").lower()


class TypeComplexityEvidence(BaseModel):
    """Class/interface/enum/module size and callable-count facts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    language: str
    path: str
    name: str
    qualified_name: str
    type_kind: ComplexityTypeKind = ComplexityTypeKind.UNKNOWN
    classification: SourceClassification = SourceClassification.SOURCE
    span: SourceSpan
    physical_line_count: IntMetric
    callable_count: IntMetric
    provenance: EvidenceProvenance

    @field_validator("evidence_id", "name", "qualified_name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="type complexity field")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return require_nonblank(str(value), label="path").replace("\\", "/")

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> str:
        return require_nonblank(str(value), label="language").lower()


class CallableComplexityEvidence(BaseModel):
    """Per-callable structural complexity facts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    language: str
    path: str
    name: str
    qualified_signature: str
    callable_kind: ComplexityCallableKind = ComplexityCallableKind.UNKNOWN
    owner_qualified_name: str | None = None
    classification: SourceClassification = SourceClassification.SOURCE
    span: SourceSpan
    physical_line_count: IntMetric
    parameter_count: IntMetric
    branch_point_count: IntMetric
    max_nesting_depth: IntMetric
    provenance: EvidenceProvenance

    @field_validator("evidence_id", "name", "qualified_signature", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="callable complexity field")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return require_nonblank(str(value), label="path").replace("\\", "/")

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> str:
        return require_nonblank(str(value), label="language").lower()

    @field_validator("owner_qualified_name", mode="before")
    @classmethod
    def normalize_owner(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="owner_qualified_name")


class ComplexityEvidenceBundle(BaseModel):
    """Complexity evidence produced by one language collector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_version: str
    language: str
    schema_version: str = COMPLEXITY_BUNDLE_SCHEMA_VERSION
    files: tuple[FileComplexityEvidence, ...] = ()
    types: tuple[TypeComplexityEvidence, ...] = ()
    callables: tuple[CallableComplexityEvidence, ...] = ()
    files_considered: int = Field(default=0, ge=0)
    files_analyzed: int = Field(default=0, ge=0)
    files_excluded: int = Field(default=0, ge=0)
    files_failed: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()

    @field_validator("provider_id", "provider_version", "language", "schema_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="complexity bundle field").lower()

    @field_validator("files", "types", "callables", "diagnostics", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AggregatedComplexityEvidence(BaseModel):
    """Merged multi-language complexity evidence for a repository snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    schema_version: str = COMPLEXITY_BUNDLE_SCHEMA_VERSION
    bundles: tuple[ComplexityEvidenceBundle, ...] = ()
    files: tuple[FileComplexityEvidence, ...] = ()
    types: tuple[TypeComplexityEvidence, ...] = ()
    callables: tuple[CallableComplexityEvidence, ...] = ()
    contributing_provider_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @field_validator("repository_id", "schema_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="aggregated complexity field")

    @field_validator(
        "bundles",
        "files",
        "types",
        "callables",
        "contributing_provider_ids",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
