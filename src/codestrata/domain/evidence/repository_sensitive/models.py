"""Typed repository-sensitive evidence models (Phase 4.5.2).

Repository-visible artifact and configuration facts only. No Findings,
severity, vulnerability interpretation, or complete secret values.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ContentClassification,
    DiscoveryBasis,
    InspectionStatus,
    PlaceholderStatus,
    RepositorySensitiveLimitationCategory,
    RepositorySensitiveParseStatus,
    SensitiveArtifactKind,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import (
    REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class SensitiveArtifactEvidence(BaseModel):
    """One discovered potentially sensitive repository artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    kind: SensitiveArtifactKind
    discovery_bases: tuple[DiscoveryBasis, ...] = ()
    inspection_status: InspectionStatus = InspectionStatus.METADATA_ONLY
    content_classifications: tuple[ContentClassification, ...] = ()
    classification: SourceClassification = SourceClassification.SOURCE
    size_bytes: int | None = Field(default=None, ge=0)
    content_fingerprint: str | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="artifact field")
        return text.replace("\\", "/")

    @field_validator("content_fingerprint", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="content_fingerprint")

    @field_validator(
        "discovery_bases",
        "content_classifications",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in sorted(value.items())}


class ConfigurationFactEvidence(BaseModel):
    """One security-relevant configuration literal fact (never a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    classification: SourceClassification = SourceClassification.SOURCE
    format: ConfigurationFormat = ConfigurationFormat.UNKNOWN
    normalized_key: str
    key_family: ConfigurationKeyFamily = ConfigurationKeyFamily.UNKNOWN
    redacted_preview: str
    value_fingerprint: str | None = None
    value_length: int = Field(default=0, ge=0)
    value_kind: ValueKind = ValueKind.UNKNOWN
    placeholder_status: PlaceholderStatus = PlaceholderStatus.NOT_APPLICABLE
    placeholder_kind: str | None = None
    is_empty: bool = False
    literal_boolean: bool | None = None
    is_wildcard_origin: bool = False
    section: str | None = None
    profile: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    parse_status: RepositorySensitiveParseStatus = (
        RepositorySensitiveParseStatus.SUCCEEDED
    )
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "evidence_id",
        "path",
        "normalized_key",
        "redacted_preview",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="configuration fact field")
        return text.replace("\\", "/")

    @field_validator(
        "value_fingerprint",
        "placeholder_kind",
        "section",
        "profile",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional configuration field")

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in sorted(value.items())}


class RepositorySensitiveDiagnostic(BaseModel):
    """Bounded diagnostic (never a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    path: str | None = None
    classification: SourceClassification = SourceClassification.UNKNOWN

    @field_validator("diagnostic_id", "diagnostic_code", "message", mode="before")
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


class RepositorySensitiveLimitation(BaseModel):
    """Structured evidence limitation (not a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: RepositorySensitiveLimitationCategory
    summary: str

    @field_validator("limitation_id", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")


class RepositorySensitiveEvidenceCoverage(BaseModel):
    """Transparent counters for repository-sensitive evidence collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_files_discovered: int = Field(default=0, ge=0)
    files_inspected: int = Field(default=0, ge=0)
    metadata_only_files: int = Field(default=0, ge=0)
    structured_files_parsed: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    unsupported_binaries: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    content_signatures_evaluated: int = Field(default=0, ge=0)
    configuration_facts_collected: int = Field(default=0, ge=0)
    placeholder_facts: int = Field(default=0, ge=0)
    production_artifacts: int = Field(default=0, ge=0)
    test_artifacts: int = Field(default=0, ge=0)
    unknown_artifacts: int = Field(default=0, ge=0)
    formats_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes inspected repository-visible candidates only; "
        "it does not claim a complete security scan of the repository."
    )

    @field_validator("formats_represented", mode="before")
    @classmethod
    def normalize_formats(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()})
        )


class AggregatedRepositorySensitiveEvidence(BaseModel):
    """Top-level aggregated repository-sensitive evidence bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    schema_name: str = REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_NAME
    schema_version: str = REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION
    status: RepositorySensitiveParseStatus = RepositorySensitiveParseStatus.SUCCEEDED
    artifacts: tuple[SensitiveArtifactEvidence, ...] = ()
    configuration_facts: tuple[ConfigurationFactEvidence, ...] = ()
    coverage: RepositorySensitiveEvidenceCoverage = Field(
        default_factory=RepositorySensitiveEvidenceCoverage
    )
    diagnostics: tuple[RepositorySensitiveDiagnostic, ...] = ()
    limitations: tuple[RepositorySensitiveLimitation, ...] = ()
    evidence_fingerprint: str = ""

    @field_validator("repository_id", "schema_name", "schema_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence bundle field")

    @field_validator(
        "artifacts",
        "configuration_facts",
        "diagnostics",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
