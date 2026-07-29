"""Architecture assessment section domain models (Phase 4.2.4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.architecture.assessment.enums import (
    ArchitectureAssessmentStatus,
    ArchitectureLimitationCategory,
    CoverageAreaStatus,
    CoverageMaturity,
    TraceabilityRelation,
)
from codestrata.domain.architecture.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ConsolidatedRecommendation,
)
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import RuleConfidence


class ArchitectureExecutionSummary(BaseModel):
    """Bounded technical execution summary for the architecture section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    providers_planned: int = Field(default=0, ge=0)
    providers_executed: int = Field(default=0, ge=0)
    provider_failures: int = Field(default=0, ge=0)
    architecture_rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_insufficient_evidence: int = Field(default=0, ge=0)
    suppressed_finding_count: int = Field(default=0, ge=0)
    visible_finding_count: int = Field(default=0, ge=0)
    conclusion_policies_executed: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_group_count: int = Field(default=0, ge=0)


class ArchitectureCoverageArea(BaseModel):
    """One architecture coverage dimension."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: CoverageAreaStatus = CoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: CoverageMaturity = CoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "architecture_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[ArchitectureCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class ArchitectureFindingReference(BaseModel):
    """Bounded reference to a canonical architecture finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    affected_scope: tuple[str, ...] = ()
    severity: str
    confidence: str = "medium"
    status: str = "visible"
    conclusion_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    evidence_count: int = Field(default=0, ge=0)
    suppression_state: str = "unsuppressed"
    taxonomy_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("architecture",)

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
        "conclusion_ids",
        "recommendation_ids",
        "taxonomy_ids",
        "assessment_dimensions",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureStrength(BaseModel):
    """Positive architecture observation backed by explicit positive evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strength_id: str
    title: str
    summary: str
    evidence_ids: tuple[str, ...] = ()
    affected_scope: tuple[str, ...] = ()
    confidence: RuleConfidence = RuleConfidence.MEDIUM
    coverage: dict[str, str] = Field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    taxonomy_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("architecture",)

    @field_validator("strength_id", "title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="strength field")

    @field_validator(
        "evidence_ids",
        "affected_scope",
        "limitations",
        "taxonomy_ids",
        "assessment_dimensions",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("coverage", mode="before")
    @classmethod
    def normalize_coverage(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("coverage must be a dictionary")
        return {str(key): str(item) for key, item in value.items()}


class ArchitectureLimitation(BaseModel):
    """Structured architecture assessment limitation (not a finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: ArchitectureLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "architecture_assessment"
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


class ArchitectureTraceabilityEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: TraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class ArchitectureTraceabilityIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[ArchitectureTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class ArchitectureAssessmentSection(BaseModel):
    """First-class architecture section of a CodeStrata assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    section_version: str = SECTION_SCHEMA_VERSION
    status: ArchitectureAssessmentStatus
    repository_id: str
    architecture_pack_id: str | None = None
    architecture_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: ArchitectureExecutionSummary = Field(
        default_factory=ArchitectureExecutionSummary
    )
    coverage: ArchitectureCoverageSummary = Field(
        default_factory=ArchitectureCoverageSummary
    )
    finding_ids: tuple[str, ...] = ()
    finding_summaries: tuple[ArchitectureFindingReference, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    conclusions: tuple[ArchitectureConclusion, ...] = ()
    recommendation_group_ids: tuple[str, ...] = ()
    recommendation_groups: tuple[ConsolidatedRecommendation, ...] = ()
    strengths: tuple[ArchitectureStrength, ...] = ()
    limitations: tuple[ArchitectureLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: ArchitectureTraceabilityIndex = Field(
        default_factory=ArchitectureTraceabilityIndex
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
        return require_nonblank(str(value), label="architecture section field")

    @field_validator(
        "architecture_pack_id",
        "architecture_pack_version",
        mode="before",
    )
    @classmethod
    def normalize_optional_pack(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="pack field")

    @field_validator(
        "finding_ids",
        "conclusion_ids",
        "recommendation_group_ids",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_id_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator(
        "finding_summaries",
        "conclusions",
        "recommendation_groups",
        "strengths",
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
