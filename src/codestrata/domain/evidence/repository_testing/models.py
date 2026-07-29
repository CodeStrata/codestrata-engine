"""Typed repository-testing evidence models (Phase 4.6.2).

Repository-observable testing structure and configuration facts only.
No Findings, severity, test quality, or runtime coverage percentages.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingLimitationCategory,
    RepositoryTestingParseStatus,
    TestBuildSourceType,
    TestDiscoveryBasis,
    TestFileRole,
    TestFrameworkFamily,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    REPOSITORY_TESTING_EVIDENCE_SCHEMA_NAME,
    REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION,
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


class TestFileCandidateEvidence(BaseModel):
    """One discovered likely test file or related test artifact path."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    role: TestFileRole = TestFileRole.UNKNOWN_TEST
    confirmation_level: EvidenceConfirmationLevel = (
        EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
    )
    discovery_bases: tuple[TestDiscoveryBasis, ...] = ()
    classification: SourceClassification = SourceClassification.TEST
    language_hint: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="test file field")

    @field_validator("language_hint", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="language_hint")

    @field_validator("discovery_bases", mode="before")
    @classmethod
    def normalize_bases(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class StructuralTestFactEvidence(BaseModel):
    """Bounded structural indicators observed inside a candidate test file."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    confirmation_level: EvidenceConfirmationLevel = (
        EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
    )
    framework_hints: tuple[TestFrameworkFamily, ...] = ()
    marker_counts: dict[str, int] = Field(default_factory=dict)
    structural_counts: dict[str, int] = Field(default_factory=dict)
    line_hints: tuple[int, ...] = ()
    classification: SourceClassification = SourceClassification.TEST
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="structural fact field")

    @field_validator("framework_hints", "line_hints", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("marker_counts", "structural_counts", mode="before")
    @classmethod
    def normalize_count_maps(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("count maps must be dictionaries")
        return {
            str(key): int(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class FrameworkFactEvidence(BaseModel):
    """Declared, configured, observed, or invoked framework evidence."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    framework: TestFrameworkFamily
    basis: FrameworkEvidenceBasis
    path: str
    declared_version: str | None = None
    detail: str | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="framework fact field")

    @field_validator("declared_version", "detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional framework field")

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class TestTypeFactEvidence(BaseModel):
    """Convention- or configuration-based test-type indicator."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    test_type: TestFileRole
    path: str
    discovery_bases: tuple[TestDiscoveryBasis, ...] = ()
    detail: str | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="test type field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="detail")

    @field_validator("discovery_bases", mode="before")
    @classmethod
    def normalize_bases(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class BuildConfigurationFactEvidence(BaseModel):
    """Build/manifest fact related to testing tools or tasks."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    source_type: TestBuildSourceType = TestBuildSourceType.UNKNOWN
    fact_kind: str
    detail: str | None = None
    command_projection: str | None = None
    framework: TestFrameworkFamily | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", "fact_kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="build config field")

    @field_validator("detail", "command_projection", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = optional_nonblank(str(value), label="optional build field")
        return None if cleaned is None else cleaned[:400]

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class MarkerFactEvidence(BaseModel):
    """Disabled/ignored/skipped/focused marker observation (never a Finding)."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    marker_type: TestMarkerType
    marker_text: str
    line_start: int | None = Field(default=None, ge=1)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", "marker_text", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="marker field")
        return text.replace("\\", "/")[:200]

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class FixtureFactEvidence(BaseModel):
    """Fixture/support/test-data candidate metadata (no content)."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    role: TestFileRole = TestFileRole.TEST_FIXTURE
    discovery_bases: tuple[TestDiscoveryBasis, ...] = ()
    size_bytes: int | None = Field(default=None, ge=0)
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="fixture field")

    @field_validator("discovery_bases", mode="before")
    @classmethod
    def normalize_bases(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class CoverageFactEvidence(BaseModel):
    """Coverage configuration or report-reference fact (no runtime percentages)."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    fact_type: CoverageFactType = CoverageFactType.UNKNOWN
    tool: TestFrameworkFamily | None = None
    detail: str | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_id", "path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return _normalize_path(value, label="coverage field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = optional_nonblank(str(value), label="detail")
        return None if cleaned is None else cleaned[:400]

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class CiTestInvocationFactEvidence(BaseModel):
    """Local CI workflow fact declaring a test or coverage command."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    path: str
    job_or_step: str
    tool: str
    command_projection: str
    continue_on_error: bool = False
    conditional: bool = False
    framework: TestFrameworkFamily | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "evidence_id",
        "path",
        "job_or_step",
        "tool",
        "command_projection",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="ci fact field")
        return text.replace("\\", "/")[:400]

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_meta(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)


class RepositoryTestingDiagnostic(BaseModel):
    """Bounded diagnostic (never a Finding)."""

    __test__ = False
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


class RepositoryTestingLimitation(BaseModel):
    """Structured evidence limitation (not a Finding)."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: RepositoryTestingLimitationCategory
    summary: str

    @field_validator("limitation_id", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")


class RepositoryTestingEvidenceCoverage(BaseModel):
    """Transparent counters for repository-testing evidence collection."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_files_considered: int = Field(default=0, ge=0)
    candidate_test_files_discovered: int = Field(default=0, ge=0)
    candidate_files_inspected: int = Field(default=0, ge=0)
    structurally_confirmed_test_files: int = Field(default=0, ge=0)
    supported_test_files_parsed: int = Field(default=0, ge=0)
    unsupported_candidate_files: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    build_manifests_inspected: int = Field(default=0, ge=0)
    ci_files_inspected: int = Field(default=0, ge=0)
    frameworks_declared: int = Field(default=0, ge=0)
    frameworks_structurally_observed: int = Field(default=0, ge=0)
    marker_facts: int = Field(default=0, ge=0)
    coverage_configurations: int = Field(default=0, ge=0)
    fixture_support_candidates: int = Field(default=0, ge=0)
    source_roles_represented: tuple[str, ...] = ()
    languages_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes inspected repository-observable testing candidates "
        "only; undiscovered tests may still exist and zero evidence does not "
        "establish that tests are absent or that the repository is release ready."
    )

    @field_validator("source_roles_represented", "languages_represented", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()})
        )


class AggregatedRepositoryTestingEvidence(BaseModel):
    """Top-level aggregated repository-testing evidence bundle."""

    __test__ = False
    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = ""
    repository_id: str
    schema_name: str = REPOSITORY_TESTING_EVIDENCE_SCHEMA_NAME
    schema_version: str = REPOSITORY_TESTING_EVIDENCE_SCHEMA_VERSION
    status: RepositoryTestingParseStatus = RepositoryTestingParseStatus.SUCCEEDED
    file_candidates: tuple[TestFileCandidateEvidence, ...] = ()
    structural_test_facts: tuple[StructuralTestFactEvidence, ...] = ()
    framework_facts: tuple[FrameworkFactEvidence, ...] = ()
    test_type_facts: tuple[TestTypeFactEvidence, ...] = ()
    build_configuration_facts: tuple[BuildConfigurationFactEvidence, ...] = ()
    marker_facts: tuple[MarkerFactEvidence, ...] = ()
    fixture_facts: tuple[FixtureFactEvidence, ...] = ()
    coverage_facts: tuple[CoverageFactEvidence, ...] = ()
    ci_test_invocation_facts: tuple[CiTestInvocationFactEvidence, ...] = ()
    coverage: RepositoryTestingEvidenceCoverage = Field(
        default_factory=RepositoryTestingEvidenceCoverage
    )
    diagnostics: tuple[RepositoryTestingDiagnostic, ...] = ()
    limitations: tuple[RepositoryTestingLimitation, ...] = ()
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
        "structural_test_facts",
        "framework_facts",
        "test_type_facts",
        "build_configuration_facts",
        "marker_facts",
        "fixture_facts",
        "coverage_facts",
        "ci_test_invocation_facts",
        "diagnostics",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
