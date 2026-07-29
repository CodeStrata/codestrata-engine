"""Technical debt assessment section domain models (Phase 4.3.1 / 4.3.4A).

Inventory and hotspot projections are additive. No composite debt scores,
financial cost, or fabricated priority.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtCoverageAreaStatus,
    TechnicalDebtCoverageMaturity,
    TechnicalDebtLimitationCategory,
    TechnicalDebtSourceRole,
    TechnicalDebtTraceabilityRelation,
)
from codestrata.domain.technical_debt.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.technical_debt.synthesis.models import (
    TechnicalDebtConcentrationFact,
    TechnicalDebtConclusion,
    TechnicalDebtRecommendation,
    TechnicalDebtSynthesisResult,
    TechnicalDebtTheme,
)
from codestrata.domain.technical_debt.taxonomy import TechnicalDebtCategory


class TechnicalDebtExecutionSummary(BaseModel):
    """Bounded technical execution summary for the debt section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    providers_planned: int = Field(default=0, ge=0)
    providers_executed: int = Field(default=0, ge=0)
    provider_failures: int = Field(default=0, ge=0)
    files_parse_failed: int = Field(default=0, ge=0)
    production_parse_failures: int = Field(default=0, ge=0)
    debt_rules_planned: int = Field(default=0, ge=0)
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
    theme_count: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)


class TechnicalDebtCoverageArea(BaseModel):
    """One technical-debt coverage dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: TechnicalDebtCoverageAreaStatus = TechnicalDebtCoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: TechnicalDebtCoverageMaturity = TechnicalDebtCoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "technical_debt_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[TechnicalDebtCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TechnicalDebtFindingReference(BaseModel):
    """Bounded reference to a canonical technical-debt finding.

    Future debt rules emit shared ``Finding`` records; this reference is the
    assessment-section projection and must not invent financial cost or effort.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    debt_category: TechnicalDebtCategory = TechnicalDebtCategory.OTHER
    affected_scope: tuple[str, ...] = ()
    severity: str
    confidence: str = "medium"
    status: str = "visible"
    evidence_count: int = Field(default=0, ge=0)
    suppression_state: str = "unsuppressed"
    taxonomy_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("technical-debt",)
    source_role: TechnicalDebtSourceRole = TechnicalDebtSourceRole.UNKNOWN
    language: str | None = None
    path: str | None = None
    package: str | None = None
    source_unit: str | None = None
    metric: str | None = None
    metric_value: str | None = None
    threshold: str | None = None
    severity_basis: str | None = None

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
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator(
        "language",
        "path",
        "package",
        "source_unit",
        "metric",
        "metric_value",
        "threshold",
        "severity_basis",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="finding reference optional field")


class TechnicalDebtRoleInventory(BaseModel):
    """One source-role partition of the complexity finding inventory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_role: TechnicalDebtSourceRole
    finding_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    unique_file_count: int = Field(default=0, ge=0)
    unique_source_unit_count: int = Field(default=0, ge=0)
    rule_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("rule_counts", "severity_counts", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("count maps must be dictionaries")
        return {str(key): int(item) for key, item in sorted(value.items())}


class TechnicalDebtFindingInventory(BaseModel):
    """Typed complexity finding inventory partitioned by source role.

    ``primary`` is production by default and drives the section's default
    finding_ids / finding_summaries. Test and unknown partitions remain
    fully traceable and transparent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_source_role: TechnicalDebtSourceRole = TechnicalDebtSourceRole.PRODUCTION
    production: TechnicalDebtRoleInventory = Field(
        default_factory=lambda: TechnicalDebtRoleInventory(
            source_role=TechnicalDebtSourceRole.PRODUCTION
        )
    )
    test: TechnicalDebtRoleInventory = Field(
        default_factory=lambda: TechnicalDebtRoleInventory(
            source_role=TechnicalDebtSourceRole.TEST
        )
    )
    unknown: TechnicalDebtRoleInventory = Field(
        default_factory=lambda: TechnicalDebtRoleInventory(
            source_role=TechnicalDebtSourceRole.UNKNOWN
        )
    )
    total_finding_count: int = Field(default=0, ge=0)
    overlapping_source_unit_count: int = Field(default=0, ge=0)


class TechnicalDebtObservedMetric(BaseModel):
    """One observed metric on a hotspot (no composite score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str
    value: str
    threshold: str | None = None
    rule_id: str
    finding_id: str

    @field_validator("metric", "value", "rule_id", "finding_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="observed metric field")

    @field_validator("threshold", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="threshold")


class TechnicalDebtHotspot(BaseModel):
    """Deterministic source-unit hotspot grouping (no fabricated priority)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    source_unit_key: str
    path: str
    package: str
    source_unit: str
    source_role: TechnicalDebtSourceRole
    language: str
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    highest_severity: str
    observed_metrics: tuple[TechnicalDebtObservedMetric, ...] = ()

    @field_validator(
        "hotspot_id",
        "source_unit_key",
        "path",
        "package",
        "source_unit",
        "language",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot field")

    @field_validator("finding_ids", "rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("observed_metrics", mode="before")
    @classmethod
    def normalize_metrics(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TechnicalDebtHotspotInventory(BaseModel):
    """Hotspot inventories partitioned by source role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    production: tuple[TechnicalDebtHotspot, ...] = ()
    test: tuple[TechnicalDebtHotspot, ...] = ()
    unknown: tuple[TechnicalDebtHotspot, ...] = ()

    @field_validator("production", "test", "unknown", mode="before")
    @classmethod
    def normalize_hotspots(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TechnicalDebtLimitation(BaseModel):
    """Structured technical-debt assessment limitation (not a finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: TechnicalDebtLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "technical_debt_assessment"
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


class TechnicalDebtTraceabilityEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: TechnicalDebtTraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class TechnicalDebtTraceabilityIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[TechnicalDebtTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class TechnicalDebtAssessmentSection(BaseModel):
    """First-class technical debt section of a CodeStrata assessment.

    Phase 4.3.4A: production-primary inventory and hotspot grouping. Unsupported
    claims such as financial cost, engineering hours, or modernization percentage
    remain intentionally absent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    section_version: str = SECTION_SCHEMA_VERSION
    status: TechnicalDebtAssessmentStatus
    repository_id: str
    technical_debt_pack_id: str | None = None
    technical_debt_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: TechnicalDebtExecutionSummary = Field(
        default_factory=TechnicalDebtExecutionSummary
    )
    coverage: TechnicalDebtCoverageSummary = Field(
        default_factory=TechnicalDebtCoverageSummary
    )
    finding_ids: tuple[str, ...] = ()
    finding_summaries: tuple[TechnicalDebtFindingReference, ...] = ()
    all_finding_ids: tuple[str, ...] = ()
    all_finding_summaries: tuple[TechnicalDebtFindingReference, ...] = ()
    finding_inventory: TechnicalDebtFindingInventory = Field(
        default_factory=TechnicalDebtFindingInventory
    )
    hotspot_inventory: TechnicalDebtHotspotInventory = Field(
        default_factory=TechnicalDebtHotspotInventory
    )
    synthesis: TechnicalDebtSynthesisResult = Field(
        default_factory=TechnicalDebtSynthesisResult
    )
    themes: tuple[TechnicalDebtTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    concentration_facts: tuple[TechnicalDebtConcentrationFact, ...] = ()
    conclusions: tuple[TechnicalDebtConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[TechnicalDebtRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    limitations: tuple[TechnicalDebtLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: TechnicalDebtTraceabilityIndex = Field(
        default_factory=TechnicalDebtTraceabilityIndex
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
        return require_nonblank(str(value), label="technical debt section field")

    @field_validator(
        "technical_debt_pack_id",
        "technical_debt_pack_version",
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
