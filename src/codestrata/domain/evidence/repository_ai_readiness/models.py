"""Typed repository AI-readiness evidence models (Phase 4.8.2).

Repository-observable AI/agent readiness signals only.
No Findings, severity, readiness scores, or recommendations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDiscoveryBasis,
    AiReadinessDocumentationKind,
    AiReadinessEvidenceFamily,
    AiReadinessObservabilityGovernanceKind,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
    EvidenceConfirmationLevel,
    RepositoryAiReadinessLimitationCategory,
    RepositoryAiReadinessParseStatus,
)
from codestrata.domain.evidence.repository_ai_readiness.identifiers import (
    REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION,
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


class AiReadinessFileCandidateEvidence(BaseModel):
    """One discovered AI-readiness-related repository artifact path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    family: AiReadinessEvidenceFamily = AiReadinessEvidenceFamily.UNKNOWN
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    technology_hints: tuple[str, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="ai-readiness file field")

    @field_validator("discovery_bases", "technology_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class AiReadinessApiBoundaryFactEvidence(BaseModel):
    """Observed API/service boundary signal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessApiBoundaryKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="api boundary fact field")

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


class AiReadinessDocumentationFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessDocumentationKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="documentation fact field")

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


class AiReadinessDataRetrievalFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessDataRetrievalKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="data retrieval fact field")

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


class AiReadinessAiIntegrationFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessAiIntegrationKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="ai integration fact field")

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


class AiReadinessToolMcpFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessToolMcpKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="tool mcp fact field")

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


class AiReadinessWorkflowAgentFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessWorkflowAgentKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="workflow agent fact field")

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


class AiReadinessObservabilityGovernanceFactEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    kind: AiReadinessObservabilityGovernanceKind
    path: str
    confirmation_level: EvidenceConfirmationLevel = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    discovery_bases: tuple[AiReadinessDiscoveryBasis, ...] = ()
    detail: str | None = None
    line_hints: tuple[int, ...] = ()
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="observability governance fact field")

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


class RepositoryAiReadinessDiagnostic(BaseModel):
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


class RepositoryAiReadinessLimitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: RepositoryAiReadinessLimitationCategory
    summary: str

    @field_validator("limitation_id", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")


class RepositoryAiReadinessEvidenceCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_files_considered: int = Field(default=0, ge=0)
    candidate_files_discovered: int = Field(default=0, ge=0)
    candidate_files_inspected: int = Field(default=0, ge=0)
    structurally_confirmed_files: int = Field(default=0, ge=0)
    unsupported_candidate_files: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    api_boundary_facts: int = Field(default=0, ge=0)
    documentation_facts: int = Field(default=0, ge=0)
    data_retrieval_facts: int = Field(default=0, ge=0)
    ai_integration_facts: int = Field(default=0, ge=0)
    tool_mcp_facts: int = Field(default=0, ge=0)
    workflow_agent_facts: int = Field(default=0, ge=0)
    observability_governance_facts: int = Field(default=0, ge=0)
    technologies_represented: tuple[str, ...] = ()
    families_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes inspected repository-observable AI-readiness "
        "artifact candidates only; undiscovered AI/agent usage may still exist "
        "and zero evidence does not establish that AI readiness signals are "
        "absent or that the repository is AI ready."
    )

    @field_validator("technologies_represented", "families_represented", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class AggregatedRepositoryAiReadinessEvidence(BaseModel):
    """Top-level aggregated repository AI-readiness evidence bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = ""
    repository_id: str
    schema_name: str = REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_NAME
    schema_version: str = REPOSITORY_AI_READINESS_EVIDENCE_SCHEMA_VERSION
    status: RepositoryAiReadinessParseStatus = RepositoryAiReadinessParseStatus.SUCCEEDED
    file_candidates: tuple[AiReadinessFileCandidateEvidence, ...] = ()
    api_boundary_facts: tuple[AiReadinessApiBoundaryFactEvidence, ...] = ()
    documentation_facts: tuple[AiReadinessDocumentationFactEvidence, ...] = ()
    data_retrieval_facts: tuple[AiReadinessDataRetrievalFactEvidence, ...] = ()
    ai_integration_facts: tuple[AiReadinessAiIntegrationFactEvidence, ...] = ()
    tool_mcp_facts: tuple[AiReadinessToolMcpFactEvidence, ...] = ()
    workflow_agent_facts: tuple[AiReadinessWorkflowAgentFactEvidence, ...] = ()
    observability_governance_facts: tuple[AiReadinessObservabilityGovernanceFactEvidence, ...] = ()
    coverage: RepositoryAiReadinessEvidenceCoverage = Field(
        default_factory=RepositoryAiReadinessEvidenceCoverage
    )
    diagnostics: tuple[RepositoryAiReadinessDiagnostic, ...] = ()
    limitations: tuple[RepositoryAiReadinessLimitation, ...] = ()
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
        "api_boundary_facts",
        "documentation_facts",
        "data_retrieval_facts",
        "ai_integration_facts",
        "tool_mcp_facts",
        "workflow_agent_facts",
        "observability_governance_facts",
        "diagnostics",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
