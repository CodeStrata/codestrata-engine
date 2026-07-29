"""Typed Dependency Evidence models (Phase 4.4.2).

Declared dependency facts only. No resolved/transitive graphs, CVEs, licenses,
or engineering-role classification.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.identifiers import DEPENDENCY_EVIDENCE_SCHEMA_VERSION
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class DependencySourceLocation(BaseModel):
    """Repository-relative source location for a declaration or manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    snippet: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str:
        return require_nonblank(str(value), label="source path").replace("\\", "/")

    @field_validator("snippet", mode="before")
    @classmethod
    def normalize_snippet(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="snippet")

    @model_validator(mode="after")
    def validate_range(self) -> DependencySourceLocation:
        if self.line_start is None and self.line_end is None:
            return self
        if self.line_start is None or self.line_end is None:
            raise ValueError("line_start and line_end must both be set")
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        return self


class DependencyDeclarationEvidence(BaseModel):
    """One declared dependency or plugin entry from a manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    ecosystem: DependencyEcosystem
    manifest_type: DependencyManifestType
    declaration_kind: DependencyDeclarationKind = DependencyDeclarationKind.UNKNOWN
    normalized_identity: str
    original_identity: str
    raw_version: str | None = None
    resolved_version_local: str | None = None
    version_availability: DependencyEvidenceAvailability = (
        DependencyEvidenceAvailability.UNAVAILABLE
    )
    version_resolution_status: DependencyVersionResolutionStatus = (
        DependencyVersionResolutionStatus.NOT_APPLICABLE
    )
    optional: bool = False
    profile: str | None = None
    extras: tuple[str, ...] = ()
    environment_marker: str | None = None
    configuration_name: str | None = None
    group_name: str | None = None
    is_editable: bool = False
    is_local_path: bool = False
    is_dependency_management: bool = False
    unsupported_reason: str | None = None
    source: DependencySourceLocation
    classification: SourceClassification = SourceClassification.SOURCE
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "evidence_id",
        "normalized_identity",
        "original_identity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="declaration field")

    @field_validator(
        "raw_version",
        "resolved_version_local",
        "profile",
        "environment_marker",
        "configuration_name",
        "group_name",
        "unsupported_reason",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional declaration field")

    @field_validator("extras", mode="before")
    @classmethod
    def normalize_extras(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in sorted(value.items())}


class DependencyManifestEvidence(BaseModel):
    """One discovered and parsed (or failed) dependency manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    ecosystem: DependencyEcosystem
    manifest_type: DependencyManifestType
    parse_status: DependencyParseStatus
    classification: SourceClassification = SourceClassification.SOURCE
    declaration_count: int = Field(default=0, ge=0)
    unsupported_constructs: tuple[str, ...] = ()
    unresolved_expressions: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    provenance: EvidenceProvenance

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="manifest field").replace("\\", "/")

    @field_validator(
        "unsupported_constructs",
        "unresolved_expressions",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyEvidenceCoverage(BaseModel):
    """Deterministic coverage counters for a dependency evidence collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifests_discovered: int = Field(default=0, ge=0)
    manifests_supported: int = Field(default=0, ge=0)
    manifests_parsed: int = Field(default=0, ge=0)
    manifests_partially_parsed: int = Field(default=0, ge=0)
    manifests_failed: int = Field(default=0, ge=0)
    manifests_excluded: int = Field(default=0, ge=0)
    declarations_collected: int = Field(default=0, ge=0)
    unsupported_construct_count: int = Field(default=0, ge=0)
    unresolved_expression_count: int = Field(default=0, ge=0)


class DependencyEvidenceBundle(BaseModel):
    """One collector/provider contribution to dependency evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_version: str
    ecosystem: DependencyEcosystem
    schema_version: str = DEPENDENCY_EVIDENCE_SCHEMA_VERSION
    status: DependencyParseStatus = DependencyParseStatus.SUCCEEDED
    manifests: tuple[DependencyManifestEvidence, ...] = ()
    declarations: tuple[DependencyDeclarationEvidence, ...] = ()
    coverage: DependencyEvidenceCoverage = Field(
        default_factory=DependencyEvidenceCoverage
    )
    diagnostics: tuple[str, ...] = ()

    @field_validator("provider_id", "provider_version", "schema_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="bundle field")

    @field_validator("manifests", "declarations", mode="before")
    @classmethod
    def normalize_object_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("diagnostics", mode="before")
    @classmethod
    def normalize_diagnostics(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class AggregatedDependencyEvidence(BaseModel):
    """Repository-level aggregated Dependency Evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    schema_version: str = DEPENDENCY_EVIDENCE_SCHEMA_VERSION
    status: DependencyParseStatus = DependencyParseStatus.NOT_APPLICABLE
    bundles: tuple[DependencyEvidenceBundle, ...] = ()
    manifests: tuple[DependencyManifestEvidence, ...] = ()
    declarations: tuple[DependencyDeclarationEvidence, ...] = ()
    coverage: DependencyEvidenceCoverage = Field(
        default_factory=DependencyEvidenceCoverage
    )
    contributing_provider_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    evidence_fingerprint: str = ""

    @field_validator("repository_id", "schema_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="aggregate field")

    @field_validator("bundles", "manifests", "declarations", mode="before")
    @classmethod
    def normalize_object_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("contributing_provider_ids", "diagnostics", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())
