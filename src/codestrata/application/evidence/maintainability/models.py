"""Application-local M22/M23 facts. Ranking is complexity × churn only."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.contracts.hotspot import EngineeringHotspot


class MetricStatusName(StrEnum):
    VALUE = "value"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CoverageScope(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"


class FindingLifecycle(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    EXEMPT = "exempt"


class EvidenceClass(StrEnum):
    """Versioned M23 evidence-class order is declared in ordering.py."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class FileChurnRecord(BaseModel):
    """Pinned M24 file churn. Binary/unknown lines stay None, never zero."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    changed_lines: int | None = Field(default=None, ge=0)
    renamed_from: str | None = None
    coverage_reason: str | None = None


class HistoryWindow(BaseModel):
    """Consumed M24 profile. This module does not extract Git history."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    window: str
    head_sha: str
    coverage: CoverageScope
    coverage_reason: str
    evaluation_time_unix: int | None = None
    included_commit_count: int = Field(default=0, ge=0)
    disclosed_exclusions: tuple[str, ...] = ()
    file_churn: tuple[FileChurnRecord, ...] = ()
    rename_pairs: tuple[tuple[str, str], ...] = ()


class ComponentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str
    file_paths: tuple[str, ...]


class OwnershipReference(BaseModel):
    """M25 scoped concentration. File drill-down is not a file hotspot rank."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: str
    subject_id: str
    serialized_ratio: str | None = None
    status: str
    history_profile_id: str
    notes: str = ""


class FindingReferenceInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    subject_id: str
    state: FindingLifecycle
    evidence_class: EvidenceClass = EvidenceClass.HIGH
    effective_severity: str = "medium"
    present_in_state: bool = True


class FindingRejection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    subject_id: str
    reason: str


class DependencyReleaseRecord(BaseModel):
    """Permitted pinned release-date metadata. No live lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    ecosystem: str
    installed_version: str
    publication_time_unix: int | None = None
    source_snapshot_id: str
    source_kind: str = "pinned_release_index"


class StalenessRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    installed_version: str
    status: MetricStatusName
    days: int | None = Field(default=None, ge=0)
    evaluation_time_unix: int | None = None
    publication_time_unix: int | None = None
    source_snapshot_id: str
    reason: str
    formula_version: str


class ConcernRecord(BaseModel):
    """M23 finding-concern tuple. Separate from the M22 hotspot list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    effective_severity: str
    evidence_class: str
    hotspot_comparable: bool
    hotspot_value: str | None = None
    hotspot_subject_id: str | None = None
    ranking_inputs: tuple[str, ...]
    context_only: tuple[str, ...]
    explanation: str


class MaintainabilityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dependency_age_days: int = Field(default=730, ge=1)
    hotspot_min_value: int = Field(default=0, ge=0)


class MaintainabilityEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    input_state_digest: str
    history: HistoryWindow | None
    complete_hotspots: tuple[EngineeringHotspot, ...] = ()
    partial_hotspots: tuple[EngineeringHotspot, ...] = ()
    static_function_ids: tuple[str, ...] = ()
    staleness: tuple[StalenessRecord, ...] = ()
    concerns: tuple[ConcernRecord, ...] = ()
    finding_rejections: tuple[FindingRejection, ...] = ()
    thresholds: MaintainabilityThresholds = Field(
        default_factory=MaintainabilityThresholds
    )
    metadata_snapshot_digest: str = ""
    executed_repository_code: bool = False
    live_lookup: bool = False
    opaque_score: bool = False
    limitations: tuple[str, ...] = ()


__all__ = [
    "ComponentSpec",
    "ConcernRecord",
    "CoverageScope",
    "DependencyReleaseRecord",
    "EvidenceClass",
    "FileChurnRecord",
    "FindingLifecycle",
    "FindingReferenceInput",
    "FindingRejection",
    "HistoryWindow",
    "MaintainabilityEvidence",
    "MaintainabilityThresholds",
    "MetricStatusName",
    "OwnershipReference",
    "StalenessRecord",
]
