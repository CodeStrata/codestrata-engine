"""Architecture report presentation models (Phase 4.2.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

ARCHITECTURE_REPORT_SECTION_ID = "report.architecture"
ARCHITECTURE_REPORT_SECTION_VERSION = "1.0.0"


class ArchitectureReportMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    value: str
    note: str | None = None

    @field_validator("key", "label", "value", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="metric field")

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="metric note")


class ArchitectureReportCoverageItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    label: str
    status: str
    display: str
    ratio: float | None = None
    note: str | None = None

    @field_validator("area_id", "label", "status", "display", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage item field")


class ArchitectureReportConclusionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    title: str
    category: str
    summary: str
    materiality: str
    confidence: str
    affected_scope: tuple[str, ...] = ()
    severity_summary: str
    primary_finding_id: str | None = None
    supporting_finding_count: int = Field(default=0, ge=0)
    modernization_relevance: str
    business_impact: str
    recommendation_group_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator(
        "conclusion_id",
        "title",
        "category",
        "summary",
        "materiality",
        "confidence",
        "severity_summary",
        "modernization_relevance",
        "business_impact",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion view field")

    @field_validator(
        "affected_scope",
        "recommendation_group_ids",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureReportFindingView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    title: str
    rule_id: str
    severity: str
    confidence: str
    affected_scope: tuple[str, ...] = ()
    summary: str
    conclusion_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    evidence_count: int = Field(default=0, ge=0)
    status: str = "visible"
    linked_to_conclusion: bool = False

    @field_validator(
        "finding_id",
        "title",
        "rule_id",
        "severity",
        "confidence",
        "summary",
        "status",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding view field")

    @field_validator("affected_scope", "conclusion_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureReportRecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_group_id: str
    title: str
    objective: str
    rationale: str
    source_conclusion_ids: tuple[str, ...] = ()
    source_finding_ids: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    validation_steps: tuple[str, ...] = ()
    modernization_wave: str
    prerequisites: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator(
        "recommendation_group_id",
        "title",
        "objective",
        "rationale",
        "modernization_wave",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation view field")

    @field_validator(
        "source_conclusion_ids",
        "source_finding_ids",
        "recommended_actions",
        "validation_steps",
        "prerequisites",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureReportLimitationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: str
    summary: str
    importance: str = "contextual"

    @field_validator("limitation_id", "category", "summary", "importance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation view field")


class ArchitectureReportTraceEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation: str
    source_id: str
    target_id: str

    @field_validator("relation", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="trace edge field")


class ArchitectureReportTraceabilityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_count: int = Field(default=0, ge=0)
    relation_types: tuple[str, ...] = ()
    sample_edges: tuple[ArchitectureReportTraceEdgeView, ...] = ()
    summary: str = ""

    @field_validator("relation_types", mode="before")
    @classmethod
    def normalize_types(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("sample_edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class ArchitectureReportSection(BaseModel):
    """Presentation-focused architecture report section (not the assessment domain model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = ARCHITECTURE_REPORT_SECTION_ID
    section_version: str = ARCHITECTURE_REPORT_SECTION_VERSION
    title: str = "Architecture Assessment"
    status: str
    status_label: str
    status_summary: str
    assessment_scope: str
    repository_name: str
    architecture_pack_id: str | None = None
    architecture_pack_version: str | None = None
    executive_summary: str
    key_metrics: tuple[ArchitectureReportMetric, ...] = ()
    coverage_summary: tuple[ArchitectureReportCoverageItem, ...] = ()
    conclusions: tuple[ArchitectureReportConclusionView, ...] = ()
    findings: tuple[ArchitectureReportFindingView, ...] = ()
    recommendation_groups: tuple[ArchitectureReportRecommendationView, ...] = ()
    strengths: tuple[str, ...] = ()
    limitations: tuple[ArchitectureReportLimitationView, ...] = ()
    traceability_summary: ArchitectureReportTraceabilityView = Field(
        default_factory=ArchitectureReportTraceabilityView
    )
    enterprise_context_used: bool = False
    generated_from_assessment_section_version: str = "1.0.0"
    include_strengths_heading: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "section_version",
        "title",
        "status",
        "status_label",
        "status_summary",
        "assessment_scope",
        "repository_name",
        "executive_summary",
        "generated_from_assessment_section_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="architecture report field")

    @field_validator(
        "key_metrics",
        "coverage_summary",
        "conclusions",
        "findings",
        "recommendation_groups",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_object_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("strengths", mode="before")
    @classmethod
    def normalize_strengths(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in value.items()}
