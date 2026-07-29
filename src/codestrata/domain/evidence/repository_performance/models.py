"""Typed repository performance evidence models (Phase 4.9.2).

Repository-observable performance signals only.
No Findings, severity, performance scores, or recommendations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_performance.enums import (
    EvidenceConfirmationLevel,
    PerformanceBlockingKind,
    PerformanceCachingKind,
    PerformanceConcurrencyKind,
    PerformanceConfigurationKind,
    PerformanceDataAccessKind,
    PerformanceDiscoveryBasis,
    PerformanceEvidenceFamily,
    PerformanceFrontendKind,
    PerformanceObservabilityKind,
    PerformanceResourceKind,
    RepositoryPerformanceLimitationCategory,
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.identifiers import (
    REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


def _normalize_path(value: object, *, label: str) -> str:
    return require_nonblank(str(value), label=label).replace("\\", "/")


def _normalize_metadata(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata must be a dictionary")
    return {str(key): str(item) for key, item in sorted(value.items())}


class PerformanceFileCandidateEvidence(BaseModel):
    """One discovered performance-related repository artifact path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    family: PerformanceEvidenceFamily = PerformanceEvidenceFamily.UNKNOWN
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    technology_hints: tuple[str, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="performance file field")

    @field_validator("discovery_bases", "technology_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceDataAccessFactEvidence(BaseModel):
    """Observed data-access performance signal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceDataAccessKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="data access fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceBlockingFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceBlockingKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="blocking fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceCachingFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceCachingKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="caching fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceConcurrencyFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceConcurrencyKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="concurrency fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceResourceFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceResourceKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="resource fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceFrontendFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceFrontendKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="frontend fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceObservabilityFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceObservabilityKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="observability fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class PerformanceConfigurationFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: PerformanceConfigurationKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[PerformanceDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="configuration fact field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="detail")
        return None if text is None else text[:400]

    @field_validator("discovery_bases", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class RepositoryPerformanceDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    origin: str = "orchestration"
    path: str | None = None

    @field_validator(
        "diagnostic_id",
        "diagnostic_code",
        "message",
        "origin",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic field")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="diagnostic path")
        return text.replace("\\", "/") if text else None


class RepositoryPerformanceLimitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: RepositoryPerformanceLimitationCategory
    summary: str

    @field_validator("limitation_id", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")


class RepositoryPerformanceEvidenceCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_files_considered: int = Field(default=0, ge=0)
    candidate_files_discovered: int = Field(default=0, ge=0)
    candidate_files_inspected: int = Field(default=0, ge=0)
    structurally_confirmed_files: int = Field(default=0, ge=0)
    unsupported_candidate_files: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    data_access_facts: int = Field(default=0, ge=0)
    blocking_operations_facts: int = Field(default=0, ge=0)
    caching_facts: int = Field(default=0, ge=0)
    concurrency_async_facts: int = Field(default=0, ge=0)
    resource_management_facts: int = Field(default=0, ge=0)
    frontend_performance_facts: int = Field(default=0, ge=0)
    observability_profiling_facts: int = Field(default=0, ge=0)
    configuration_controls_facts: int = Field(default=0, ge=0)
    technologies_represented: tuple[str, ...] = ()
    families_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes inspected repository-observable performance "
        "artifact candidates only; undiscovered performance signals may still "
        "exist and zero evidence does not establish that performance risks are "
        "absent or that the repository is performant."
    )

    @field_validator("technologies_represented", "families_represented", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class AggregatedRepositoryPerformanceEvidence(BaseModel):
    """Top-level aggregated repository performance evidence bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = ""
    repository_id: str
    schema_name: str = REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_NAME
    schema_version: str = REPOSITORY_PERFORMANCE_EVIDENCE_SCHEMA_VERSION
    status: RepositoryPerformanceParseStatus = RepositoryPerformanceParseStatus.SUCCEEDED
    file_candidates: tuple[PerformanceFileCandidateEvidence, ...] = ()
    data_access_facts: tuple[PerformanceDataAccessFactEvidence, ...] = ()
    blocking_operations_facts: tuple[PerformanceBlockingFactEvidence, ...] = ()
    caching_facts: tuple[PerformanceCachingFactEvidence, ...] = ()
    concurrency_async_facts: tuple[PerformanceConcurrencyFactEvidence, ...] = ()
    resource_management_facts: tuple[PerformanceResourceFactEvidence, ...] = ()
    frontend_performance_facts: tuple[PerformanceFrontendFactEvidence, ...] = ()
    observability_profiling_facts: tuple[PerformanceObservabilityFactEvidence, ...] = ()
    configuration_controls_facts: tuple[PerformanceConfigurationFactEvidence, ...] = ()
    coverage: RepositoryPerformanceEvidenceCoverage = Field(
        default_factory=RepositoryPerformanceEvidenceCoverage
    )
    diagnostics: tuple[RepositoryPerformanceDiagnostic, ...] = ()
    limitations: tuple[RepositoryPerformanceLimitation, ...] = ()
    evidence_fingerprint: str = ""

    @field_validator(
        "repository_id",
        "schema_name",
        "schema_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence bundle field")

    @field_validator(
        "file_candidates",
        "data_access_facts",
        "blocking_operations_facts",
        "caching_facts",
        "concurrency_async_facts",
        "resource_management_facts",
        "frontend_performance_facts",
        "observability_profiling_facts",
        "configuration_controls_facts",
        "diagnostics",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
