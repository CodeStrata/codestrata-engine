"""Versioned inventory facts emitted by E05.2.

These records follow the shared measurement semantics (schema/version, stable
subject ID, evidence, extraction status, coverage). They reuse Repository Graph
identities. E05.3 seals them in an Engine-local envelope; E01.2 shared envelopes
are still not claimed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.inventory.models import (
    ClassificationMetric,
    ResolutionObservation,
    SupportKind,
)
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass
from codestrata.domain.repository_graph.mapping import FileComponentMapping

INVENTORY_FACT_SCHEMA_VERSION = "codestrata.inventory.facts.v1"
INVENTORY_EMITTER_VERSION = "e05.2.v1"

CAP_M01 = "inventory.m01.classification"
CAP_M02 = "inventory.m02.dependencies"
CAP_M03 = "inventory.m03.ci"
CAP_M04 = "inventory.m04.surfaces"


class ExtractionStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class CapabilityApplicability(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class InventoryEvidenceRef(BaseModel):
    """Evidence identity: digest + relative location, never an absolute path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    working_state_digest: str
    source_revision: str
    relative_path: str
    content_digest: str = ""
    extractor_version: str
    line: int | None = Field(default=None, ge=1)
    limitation: str | None = None


class FileSubjectFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_id: str
    relative_path: str
    primary_class: InventoryPrimaryClass
    content_digest: str
    classifier_version: str
    language: str | None = None
    ignore_reason: str | None = None
    unread_reason: str | None = None
    detected: bool = False
    structurally_supported: bool = False
    evidence_id: str


class ComponentSubjectFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_id: str
    component_key: str
    file_ids: tuple[str, ...] = ()


class DependencyDeclarationFact(BaseModel):
    """Declared coordinate. Missing lock is not a resolved-empty set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    declaration_id: str
    subject_id: str
    ecosystem: str
    coordinate: str
    declared_version: str | None = None
    direct: bool = True
    manifest_path: str
    parser_version: str
    support: SupportKind
    resolution: ResolutionObservation
    evidence_id: str
    duplicate: bool = False


class DependencyResolutionOccurrence(BaseModel):
    """One resolved identity/version occurrence. Not the coverage unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: str
    declaration_id: str | None
    subject_id: str
    ecosystem: str
    resolved_identity: str
    resolved_version: str | None = None
    lock_path: str | None = None
    direct: bool = True
    evidence_id: str


class ImportObservationFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str
    source_subject_id: str
    target_subject_id: str
    language: str
    evidence_paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    evidence_id: str
    extraction_status: ExtractionStatus = ExtractionStatus.COMPLETE


class SurfaceDeclarationFact(BaseModel):
    """M04 statically declared API/config/deployment surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str
    subject_id: str
    symbol_id: str | None = None
    declaration_kind: str
    language: str | None = None
    symbol: str
    relative_path: str
    line: int | None = Field(default=None, ge=1)
    value: str
    support: SupportKind
    extraction_status: ExtractionStatus
    evidence_id: str
    limitation: str | None = None


class CiInvocationFact(BaseModel):
    """Configured CI invocation. Never claims the job ran or passed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str
    subject_id: str
    path: str
    line: int | None = None
    job: str | None = None
    literal_command: str | None = None
    condition: str | None = None
    tool_category: str
    target: str | None = None
    parser_rule: str
    unresolved: bool = False
    unresolved_reason: str | None = None
    proves_execution: bool = False
    evidence_id: str


class CapabilityCoverageRecord(BaseModel):
    """Per-capability coverage. Unknown denominator is null, never 0% or 100%."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: str
    version: str
    scope: str
    applicability: CapabilityApplicability
    evaluated: int = Field(ge=0)
    eligible: int = Field(ge=0)
    unknown: int = Field(ge=0, default=0)
    error: int = Field(ge=0, default=0)
    excluded: int = Field(ge=0, default=0)
    coverage_ratio: str | None = None
    coverage_reason: str | None = None
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class InventoryFactBundle(BaseModel):
    """Canonical inventory facts with coverage. No health verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = INVENTORY_FACT_SCHEMA_VERSION
    emitter_version: str = INVENTORY_EMITTER_VERSION
    repository_id: str
    repository_key: str
    source_revision: str
    working_state_digest: str
    classification: ClassificationMetric
    files: tuple[FileSubjectFact, ...] = ()
    components: tuple[ComponentSubjectFact, ...] = ()
    file_component_map: tuple[FileComponentMapping, ...] = ()
    declarations: tuple[DependencyDeclarationFact, ...] = ()
    resolutions: tuple[DependencyResolutionOccurrence, ...] = ()
    imports: tuple[ImportObservationFact, ...] = ()
    surfaces: tuple[SurfaceDeclarationFact, ...] = ()
    ci: tuple[CiInvocationFact, ...] = ()
    evidence: tuple[InventoryEvidenceRef, ...] = ()
    coverage: tuple[CapabilityCoverageRecord, ...] = ()
    executed_repository_code: bool = False
    ci_execution_observed: bool = False
    limitations: tuple[str, ...] = ()

    def to_canonical_dict(self) -> dict[str, object]:
        """Comparison-ready JSON-compatible body without run metadata."""

        return self.model_dump(mode="json")
