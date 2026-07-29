"""Typed repository-cloud evidence models (Phase 4.7.2).

Repository-observable cloud technology and deployment signals only.
No Findings, severity, readiness scores, or recommendations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudDiscoveryBasis,
    CloudEvidenceFamily,
    CloudIaCKind,
    CloudManagedServiceKind,
    CloudOrchestrationKind,
    CloudPlatformKind,
    CloudServerlessKind,
    EvidenceConfirmationLevel,
    RepositoryCloudLimitationCategory,
    RepositoryCloudParseStatus,
)
from codestrata.domain.evidence.repository_cloud.identifiers import (
    REPOSITORY_CLOUD_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_CLOUD_EVIDENCE_SCHEMA_VERSION,
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


class CloudFileCandidateEvidence(BaseModel):
    """One discovered cloud-related repository artifact path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    family: CloudEvidenceFamily = CloudEvidenceFamily.UNKNOWN
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    technology_hints: tuple[str, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="cloud file field")

    @field_validator("discovery_bases", "technology_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class CloudPlatformFactEvidence(BaseModel):
    """Observed cloud platform signal (AWS / Azure / GCP)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    platform: CloudPlatformKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="platform fact field")

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


class CloudContainerFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: CloudContainerKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="container fact field")

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


class CloudOrchestrationFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: CloudOrchestrationKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="orchestration fact field")

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


class CloudIaCFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: CloudIaCKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="iac fact field")

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


class CloudServerlessFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: CloudServerlessKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="serverless fact field")

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


class CloudManagedServiceFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    service: CloudManagedServiceKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="managed service fact field")

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


class CloudDeploymentFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    system: CloudDeploymentSystem
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[CloudDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="deployment fact field")

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


class RepositoryCloudDiagnostic(BaseModel):
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


class RepositoryCloudLimitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: RepositoryCloudLimitationCategory
    summary: str

    @field_validator("limitation_id", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")


class RepositoryCloudEvidenceCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_files_considered: int = Field(default=0, ge=0)
    candidate_files_discovered: int = Field(default=0, ge=0)
    candidate_files_inspected: int = Field(default=0, ge=0)
    structurally_confirmed_files: int = Field(default=0, ge=0)
    unsupported_candidate_files: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    platform_facts: int = Field(default=0, ge=0)
    container_facts: int = Field(default=0, ge=0)
    orchestration_facts: int = Field(default=0, ge=0)
    iac_facts: int = Field(default=0, ge=0)
    serverless_facts: int = Field(default=0, ge=0)
    managed_service_facts: int = Field(default=0, ge=0)
    deployment_facts: int = Field(default=0, ge=0)
    technologies_represented: tuple[str, ...] = ()
    families_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes inspected repository-observable cloud artifact "
        "candidates only; undiscovered cloud usage may still exist and zero "
        "evidence does not establish that cloud technologies are absent or that "
        "the repository is cloud ready."
    )

    @field_validator("technologies_represented", "families_represented", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class AggregatedRepositoryCloudEvidence(BaseModel):
    """Top-level aggregated repository-cloud evidence bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = ""
    repository_id: str
    schema_name: str = REPOSITORY_CLOUD_EVIDENCE_SCHEMA_NAME
    schema_version: str = REPOSITORY_CLOUD_EVIDENCE_SCHEMA_VERSION
    status: RepositoryCloudParseStatus = RepositoryCloudParseStatus.SUCCEEDED
    file_candidates: tuple[CloudFileCandidateEvidence, ...] = ()
    platform_facts: tuple[CloudPlatformFactEvidence, ...] = ()
    container_facts: tuple[CloudContainerFactEvidence, ...] = ()
    orchestration_facts: tuple[CloudOrchestrationFactEvidence, ...] = ()
    iac_facts: tuple[CloudIaCFactEvidence, ...] = ()
    serverless_facts: tuple[CloudServerlessFactEvidence, ...] = ()
    managed_service_facts: tuple[CloudManagedServiceFactEvidence, ...] = ()
    deployment_facts: tuple[CloudDeploymentFactEvidence, ...] = ()
    coverage: RepositoryCloudEvidenceCoverage = Field(
        default_factory=RepositoryCloudEvidenceCoverage
    )
    diagnostics: tuple[RepositoryCloudDiagnostic, ...] = ()
    limitations: tuple[RepositoryCloudLimitation, ...] = ()
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
        "platform_facts",
        "container_facts",
        "orchestration_facts",
        "iac_facts",
        "serverless_facts",
        "managed_service_facts",
        "deployment_facts",
        "diagnostics",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
