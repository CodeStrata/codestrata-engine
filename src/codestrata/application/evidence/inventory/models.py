"""Inventory models for E05.1 extractor depth and M01–M03 observation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.repository_graph.enums import InventoryPrimaryClass

CLASSIFIER_VERSION = "codestrata.inventory.m01.v1"
EXTRACTOR_DEPTH_PIN_VERSION = "e05.1.v1"


class SupportKind(StrEnum):
    """Whether an extractor can structurally produce a fact, or only detect it."""

    DETECTION_ONLY = "detection_only"
    STRUCTURAL = "structural"
    UNKNOWN = "unknown"


class InventoryMetricStatus(StrEnum):
    OBSERVED = "observed"
    NOT_APPLICABLE = "not_applicable"


class ResolutionObservation(StrEnum):
    """Declared vs resolved identity — missing lock is not zero dependencies."""

    RESOLVED = "resolved"
    DECLARED_ONLY = "declared_only"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class FileClassificationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str
    primary_class: InventoryPrimaryClass
    language: str | None = None
    content_digest: str = ""
    classifier_version: str = CLASSIFIER_VERSION
    ignore_reason: str | None = None
    manifest_location: str | None = None
    structural_language: str | None = None
    detected: bool = False
    structurally_supported: bool = False
    unread_reason: str | None = None


class ClassificationCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: int = 0
    test: int = 0
    config: int = 0
    infra: int = 0
    docs: int = 0
    generated: int = 0
    vendor: int = 0
    binary: int = 0
    unknown: int = 0

    def for_class(self, primary: InventoryPrimaryClass) -> int:
        return int(getattr(self, primary.value))


class ClassificationMetric(BaseModel):
    """M01 supported fraction. Zero eligible files => NOT_APPLICABLE."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: InventoryMetricStatus
    class_counts: ClassificationCounts
    eligible_files: int = Field(ge=0)
    supported_eligible_files: int = Field(ge=0)
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    ratio: str | None = None
    ignored_in_inventory: int = Field(ge=0, default=0)


class ParserFactMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    extractor_id: str
    parser_output: str
    fact_kind: str
    support: SupportKind
    limitations: str = ""


class ManifestDepthPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ecosystem: str
    detection_basenames: tuple[str, ...]
    lockfile_basenames: tuple[str, ...] = ()
    structural_collector: str | None = None
    structural_provider_id: str | None = None
    support: SupportKind
    resolution: ResolutionObservation
    limitations: str = ""


class CiDepthPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    detection_paths: tuple[str, ...]
    support: SupportKind
    parser: str | None = None
    limitations: str = ""


class ExtractorDepthPin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = EXTRACTOR_DEPTH_PIN_VERSION
    classifier_version: str = CLASSIFIER_VERSION
    languages: tuple[str, ...]
    manifests: tuple[ManifestDepthPin, ...]
    ci: tuple[CiDepthPin, ...]
    fact_mappings: tuple[ParserFactMapping, ...]
    detection_only_languages: tuple[str, ...]
    notes: tuple[str, ...] = ()


class ManifestObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str
    ecosystem: str
    manifest_kind: str
    support: SupportKind
    resolution: ResolutionObservation
    declared_count: int = 0
    resolved_count: int = 0
    parser_version: str | None = None
    duplicate_coordinates: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


class CiInvocationObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

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


class CiDocumentObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    provider: str
    support: SupportKind
    parse_status: str
    invocations: tuple[CiInvocationObservation, ...] = ()
    test_count: int = 0
    coverage_count: int = 0
    lint_count: int = 0
    security_count: int = 0


class RepositoryInventorySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files: tuple[FileClassificationRecord, ...]
    metric: ClassificationMetric
    manifests: tuple[ManifestObservation, ...]
    ci: tuple[CiDocumentObservation, ...]
    executed_repository_code: bool = False
