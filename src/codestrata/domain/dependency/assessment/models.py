"""Dependency assessment section domain models (Phase 4.4.1 / 4.4.4 / 4.4.5).

Inventory (1.1.0) plus deterministic synthesis (1.2.0). No composite scores,
CVE/license fields, or framework classifications.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencyCoverageAreaStatus,
    DependencyCoverageMaturity,
    DependencyLimitationCategory,
    DependencySourceRole,
    DependencyTraceabilityRelation,
)
from codestrata.domain.dependency.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.dependency.synthesis.models import (
    DependencyConcentrationFact,
    DependencyConclusion,
    DependencyRecommendation,
    DependencySynthesisResult,
    DependencyTheme,
)
from codestrata.domain.dependency.taxonomy import DependencyRole
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


def _normalize_count_map(value: object) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("count maps must be dictionaries")
    return {str(key): int(item) for key, item in sorted(value.items())}


class DependencyExecutionSummary(BaseModel):
    """Bounded technical execution summary for the dependency section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    providers_planned: int = Field(default=0, ge=0)
    providers_executed: int = Field(default=0, ge=0)
    provider_failures: int = Field(default=0, ge=0)
    dependency_rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_insufficient_evidence: int = Field(default=0, ge=0)
    suppressed_finding_count: int = Field(default=0, ge=0)
    visible_finding_count: int = Field(default=0, ge=0)
    production_finding_count: int = Field(default=0, ge=0)
    test_finding_count: int = Field(default=0, ge=0)
    unknown_finding_count: int = Field(default=0, ge=0)
    total_finding_count: int = Field(default=0, ge=0)
    production_parse_failures: int = Field(default=0, ge=0)
    test_fixture_parse_failures: int = Field(default=0, ge=0)
    unknown_parse_failures: int = Field(default=0, ge=0)
    theme_count: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)


class DependencyCoverageArea(BaseModel):
    """One dependency coverage dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: DependencyCoverageAreaStatus = DependencyCoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: DependencyCoverageMaturity = DependencyCoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "dependency_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[DependencyCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyFindingReference(BaseModel):
    """Bounded reference to a canonical dependency finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    dependency_role: DependencyRole = DependencyRole.UNKNOWN
    source_role: DependencySourceRole = DependencySourceRole.UNKNOWN
    affected_scope: tuple[str, ...] = ()
    severity: str
    confidence: str = "medium"
    status: str = "visible"
    evidence_count: int = Field(default=0, ge=0)
    suppression_state: str = "unsuppressed"
    taxonomy_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("dependency",)
    path: str | None = None
    ecosystem: str | None = None
    normalized_identity: str | None = None
    evidence_ids: tuple[str, ...] = ()

    @field_validator(
        "finding_id",
        "rule_id",
        "title",
        "severity",
        "confidence",
        "status",
        "suppression_state",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding reference field")

    @field_validator(
        "affected_scope",
        "taxonomy_ids",
        "assessment_dimensions",
        "evidence_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("path", "ecosystem", "normalized_identity", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="optional finding field")
        if text is None:
            return None
        return text.replace("\\", "/")


class DependencyLimitation(BaseModel):
    """Structured dependency assessment limitation (not a finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: DependencyLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "dependency_assessment"
    remediation_guidance: str | None = None

    @field_validator(
        "limitation_id",
        "summary",
        "affected_capability",
        "importance",
        "provenance",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation field")

    @field_validator("remediation_guidance", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="remediation_guidance")


class DependencyTraceabilityEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: DependencyTraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class DependencyTraceabilityIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[DependencyTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class DependencyEvidenceSummary(BaseModel):
    """Transparent Dependency Evidence projection for the assessment section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = ""
    evidence_fingerprint: str = ""
    evidence_status: str = "not_configured"
    manifests_discovered: int = Field(default=0, ge=0)
    manifests_supported: int = Field(default=0, ge=0)
    manifests_parsed: int = Field(default=0, ge=0)
    manifests_partially_parsed: int = Field(default=0, ge=0)
    manifests_failed: int = Field(default=0, ge=0)
    manifests_excluded: int = Field(default=0, ge=0)
    declarations_collected: int = Field(default=0, ge=0)
    ecosystems: tuple[str, ...] = ()
    unsupported_construct_count: int = Field(default=0, ge=0)
    proven_unresolved_count: int = Field(default=0, ge=0)
    unsupported_resolution_count: int = Field(default=0, ge=0)
    local_or_editable_count: int = Field(default=0, ge=0)
    production_declaration_count: int = Field(default=0, ge=0)
    test_declaration_count: int = Field(default=0, ge=0)
    unknown_declaration_count: int = Field(default=0, ge=0)

    @field_validator("ecosystems", mode="before")
    @classmethod
    def normalize_ecosystems(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class DependencyRoleFindingInventory(BaseModel):
    """One source-role partition of dependency findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_role: DependencySourceRole
    finding_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    unique_manifest_count: int = Field(default=0, ge=0)
    rule_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("rule_counts", "severity_counts", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        return _normalize_count_map(value)


class DependencyFindingInventory(BaseModel):
    """Role-partitioned finding inventory; production is primary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_source_role: DependencySourceRole = DependencySourceRole.PRODUCTION
    production: DependencyRoleFindingInventory = Field(
        default_factory=lambda: DependencyRoleFindingInventory(
            source_role=DependencySourceRole.PRODUCTION
        )
    )
    test: DependencyRoleFindingInventory = Field(
        default_factory=lambda: DependencyRoleFindingInventory(
            source_role=DependencySourceRole.TEST
        )
    )
    unknown: DependencyRoleFindingInventory = Field(
        default_factory=lambda: DependencyRoleFindingInventory(
            source_role=DependencySourceRole.UNKNOWN
        )
    )
    total_finding_count: int = Field(default=0, ge=0)


class DependencyRoleDeclarationInventory(BaseModel):
    """Declaration counts for one source-role partition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_role: DependencySourceRole
    declaration_count: int = Field(default=0, ge=0)
    active_declaration_count: int = Field(default=0, ge=0)
    dependency_management_count: int = Field(default=0, ge=0)
    plugin_count: int = Field(default=0, ge=0)
    test_or_development_count: int = Field(default=0, ge=0)
    local_or_editable_count: int = Field(default=0, ge=0)
    kind_counts: dict[str, int] = Field(default_factory=dict)
    ecosystem_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("kind_counts", "ecosystem_counts", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        return _normalize_count_map(value)


class DependencyDeclarationInventory(BaseModel):
    """Role-partitioned declaration inventory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    production: DependencyRoleDeclarationInventory = Field(
        default_factory=lambda: DependencyRoleDeclarationInventory(
            source_role=DependencySourceRole.PRODUCTION
        )
    )
    test: DependencyRoleDeclarationInventory = Field(
        default_factory=lambda: DependencyRoleDeclarationInventory(
            source_role=DependencySourceRole.TEST
        )
    )
    unknown: DependencyRoleDeclarationInventory = Field(
        default_factory=lambda: DependencyRoleDeclarationInventory(
            source_role=DependencySourceRole.UNKNOWN
        )
    )
    total_declaration_count: int = Field(default=0, ge=0)


class DependencyManifestInventoryEntry(BaseModel):
    """One discovered/supported manifest in the assessment inventory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_inventory_id: str
    path: str
    source_role: DependencySourceRole
    ecosystem: str
    manifest_type: str
    parse_status: str
    evidence_id: str = ""
    declaration_count: int = Field(default=0, ge=0)
    active_declaration_count: int = Field(default=0, ge=0)
    dependency_management_count: int = Field(default=0, ge=0)
    plugin_count: int = Field(default=0, ge=0)
    test_or_development_count: int = Field(default=0, ge=0)
    kind_counts: dict[str, int] = Field(default_factory=dict)
    unsupported_construct_count: int = Field(default=0, ge=0)
    proven_unresolved_count: int = Field(default=0, ge=0)
    unsupported_resolution_count: int = Field(default=0, ge=0)
    hygiene_finding_ids: tuple[str, ...] = ()
    diagnostic_references: tuple[str, ...] = ()

    @field_validator(
        "manifest_inventory_id",
        "path",
        "ecosystem",
        "manifest_type",
        "parse_status",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="manifest inventory field")
        return text.replace("\\", "/")

    @field_validator("evidence_id", mode="before")
    @classmethod
    def normalize_evidence_id(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("kind_counts", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        return _normalize_count_map(value)

    @field_validator("hygiene_finding_ids", "diagnostic_references", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyManifestInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[DependencyManifestInventoryEntry, ...] = ()

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyCountBucket(BaseModel):
    """One labeled aggregation bucket with transparent counts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    count: int = Field(default=0, ge=0)
    source_role: DependencySourceRole | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("key", "label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="count bucket field")

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in sorted(value.items())}


class DependencyAggregationInventory(BaseModel):
    """Transparent ecosystem / kind / resolution aggregations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    by_ecosystem: tuple[DependencyCountBucket, ...] = ()
    by_manifest_type: tuple[DependencyCountBucket, ...] = ()
    by_declaration_kind: tuple[DependencyCountBucket, ...] = ()
    by_source_role: tuple[DependencyCountBucket, ...] = ()
    by_version_resolution_status: tuple[DependencyCountBucket, ...] = ()

    @field_validator(
        "by_ecosystem",
        "by_manifest_type",
        "by_declaration_kind",
        "by_source_role",
        "by_version_resolution_status",
        mode="before",
    )
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyHotspot(BaseModel):
    """Deterministic manifest-level hotspot (presentation ordering, not priority)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    manifest_inventory_id: str
    path: str
    source_role: DependencySourceRole
    ecosystem: str
    manifest_type: str
    declaration_count: int = Field(default=0, ge=0)
    active_declaration_count: int = Field(default=0, ge=0)
    dependency_management_count: int = Field(default=0, ge=0)
    plugin_count: int = Field(default=0, ge=0)
    hygiene_finding_count: int = Field(default=0, ge=0)
    distinct_rule_ids: tuple[str, ...] = ()
    highest_severity: str = "informational"
    affected_package_identities: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    diagnostics_count: int = Field(default=0, ge=0)
    proven_unresolved_count: int = Field(default=0, ge=0)
    unsupported_resolution_count: int = Field(default=0, ge=0)

    @field_validator(
        "hotspot_id",
        "manifest_inventory_id",
        "path",
        "ecosystem",
        "manifest_type",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="hotspot field")
        return text.replace("\\", "/")

    @field_validator(
        "distinct_rule_ids",
        "affected_package_identities",
        "finding_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyHotspotInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    production: tuple[DependencyHotspot, ...] = ()
    test: tuple[DependencyHotspot, ...] = ()
    unknown: tuple[DependencyHotspot, ...] = ()

    @field_validator("production", "test", "unknown", mode="before")
    @classmethod
    def normalize_hotspots(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyDiagnosticRecord(BaseModel):
    """Bounded diagnostic projection (never a finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    path: str | None = None
    source_role: DependencySourceRole = DependencySourceRole.UNKNOWN
    ecosystem: str | None = None

    @field_validator("diagnostic_id", "diagnostic_code", "message", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic field")

    @field_validator("path", "ecosystem", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="optional diagnostic field")
        return text.replace("\\", "/") if text else None


class DependencyDiagnosticsSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    records: tuple[DependencyDiagnosticRecord, ...] = ()
    production_count: int = Field(default=0, ge=0)
    test_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)

    @field_validator("records", mode="before")
    @classmethod
    def normalize_records(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyAssessmentSection(BaseModel):
    """First-class dependency section of a CodeStrata assessment.

    Phase 4.4.4 inventories are retained. Phase 4.4.5 adds deterministic
    themes/conclusions/recommendations. Composite scores, CVE/license fields,
    and framework classifications remain intentionally absent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    section_version: str = SECTION_SCHEMA_VERSION
    status: DependencyAssessmentStatus
    repository_id: str
    dependency_pack_id: str | None = None
    dependency_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: DependencyExecutionSummary = Field(
        default_factory=DependencyExecutionSummary
    )
    coverage: DependencyCoverageSummary = Field(
        default_factory=DependencyCoverageSummary
    )
    evidence_summary: DependencyEvidenceSummary = Field(
        default_factory=DependencyEvidenceSummary
    )
    declaration_inventory: DependencyDeclarationInventory = Field(
        default_factory=DependencyDeclarationInventory
    )
    manifest_inventory: DependencyManifestInventory = Field(
        default_factory=DependencyManifestInventory
    )
    aggregation_inventory: DependencyAggregationInventory = Field(
        default_factory=DependencyAggregationInventory
    )
    finding_inventory: DependencyFindingInventory = Field(
        default_factory=DependencyFindingInventory
    )
    hotspot_inventory: DependencyHotspotInventory = Field(
        default_factory=DependencyHotspotInventory
    )
    diagnostics_summary: DependencyDiagnosticsSummary = Field(
        default_factory=DependencyDiagnosticsSummary
    )
    # Production-primary finding view.
    finding_ids: tuple[str, ...] = ()
    finding_summaries: tuple[DependencyFindingReference, ...] = ()
    # Complete finding view (production + test + unknown).
    all_finding_ids: tuple[str, ...] = ()
    all_finding_summaries: tuple[DependencyFindingReference, ...] = ()
    # Phase 4.4.5 synthesis (additive).
    synthesis: DependencySynthesisResult = Field(
        default_factory=DependencySynthesisResult
    )
    themes: tuple[DependencyTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    concentration_facts: tuple[DependencyConcentrationFact, ...] = ()
    conclusions: tuple[DependencyConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[DependencyRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    limitations: tuple[DependencyLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: DependencyTraceabilityIndex = Field(
        default_factory=DependencyTraceabilityIndex
    )
    enterprise_context_used: bool = False
    business_impact: str = "unknown"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "section_version",
        "repository_id",
        "business_impact",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency section field")

    @field_validator(
        "dependency_pack_id",
        "dependency_pack_version",
        mode="before",
    )
    @classmethod
    def normalize_optional_pack(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="pack field")

    @field_validator(
        "finding_ids",
        "all_finding_ids",
        "theme_ids",
        "conclusion_ids",
        "recommendation_ids",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_id_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator(
        "finding_summaries",
        "all_finding_summaries",
        "themes",
        "concentration_facts",
        "conclusions",
        "recommendations",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_object_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in value.items()}
