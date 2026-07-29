"""Technical Debt report presentation models (Phase 4.3.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

TECHNICAL_DEBT_REPORT_SECTION_ID = "report.technical_debt"
TECHNICAL_DEBT_REPORT_SECTION_VERSION = "1.0.0"
TOP_PRODUCTION_HOTSPOTS = 20
TRACE_SAMPLE_LIMIT = 12


class TechnicalDebtReportMetric(BaseModel):
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


class TechnicalDebtReportThemeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    title: str
    rule_id: str
    source_role: str
    finding_count: int = Field(default=0, ge=0)
    high_severity_count: int = Field(default=0, ge=0)
    medium_severity_count: int = Field(default=0, ge=0)

    @field_validator("theme_id", "title", "rule_id", "source_role", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme view field")


class TechnicalDebtReportHotspotView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    path: str
    package: str
    source_unit: str
    source_role: str
    language: str
    finding_count: int = Field(default=0, ge=0)
    highest_severity: str
    rule_ids: tuple[str, ...] = ()
    metric_summary: str = ""
    presentation_order: int = Field(default=1, ge=1)

    @field_validator(
        "hotspot_id",
        "path",
        "package",
        "source_unit",
        "source_role",
        "language",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot view field")

    @field_validator("rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtReportConclusionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    policy_id: str
    kind: str
    audience: str
    title: str
    summary: str
    confidence: str
    source_role: str
    theme_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    hotspot_count: int = Field(default=0, ge=0)
    recommendation_ids: tuple[str, ...] = ()

    @field_validator(
        "conclusion_id",
        "policy_id",
        "kind",
        "audience",
        "title",
        "summary",
        "confidence",
        "source_role",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion view field")

    @field_validator("theme_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtReportRecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    action: str
    rationale: str
    conditional: bool = True
    audience: str
    conclusion_ids: tuple[str, ...] = ()

    @field_validator(
        "recommendation_id",
        "title",
        "action",
        "rationale",
        "audience",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation view field")

    @field_validator("conclusion_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtReportCoverageItem(BaseModel):
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


class TechnicalDebtReportLimitationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: str
    summary: str
    importance: str = "contextual"

    @field_validator("limitation_id", "category", "summary", "importance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation view field")


class TechnicalDebtReportTraceEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation: str
    source_id: str
    target_id: str

    @field_validator("relation", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="trace edge field")


class TechnicalDebtReportTraceabilityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_count: int = Field(default=0, ge=0)
    relation_types: tuple[str, ...] = ()
    sample_edges: tuple[TechnicalDebtReportTraceEdgeView, ...] = ()
    summary: str = ""

    @field_validator("relation_types", mode="before")
    @classmethod
    def normalize_types(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("sample_edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TechnicalDebtReportTestObservation(BaseModel):
    """Separate test-maintainability observation (not production health)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    present: bool = False
    finding_count: int = Field(default=0, ge=0)
    title: str = "No separate test-maintainability observation"
    summary: str = (
        "No test-source complexity findings were recorded for this assessment."
    )
    conclusion_ids: tuple[str, ...] = ()

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="test observation field")

    @field_validator("conclusion_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtReportSection(BaseModel):
    """Presentation-focused Technical Debt report section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = TECHNICAL_DEBT_REPORT_SECTION_ID
    section_version: str = TECHNICAL_DEBT_REPORT_SECTION_VERSION
    title: str = "Technical Debt Assessment"
    status: str
    status_label: str
    status_summary: str
    assessment_scope: str
    repository_name: str
    technical_debt_pack_id: str | None = None
    technical_debt_pack_version: str | None = None
    executive_summary: str
    key_metrics: tuple[TechnicalDebtReportMetric, ...] = ()
    significant_themes: tuple[TechnicalDebtReportThemeView, ...] = ()
    top_production_hotspots: tuple[TechnicalDebtReportHotspotView, ...] = ()
    hotspot_presentation_note: str = (
        "Hotspots are shown in inventory order (highest severity, then finding "
        "count, then path/unit). This is presentation order, not a priority score."
    )
    conclusions: tuple[TechnicalDebtReportConclusionView, ...] = ()
    recommendations: tuple[TechnicalDebtReportRecommendationView, ...] = ()
    test_observation: TechnicalDebtReportTestObservation = Field(
        default_factory=TechnicalDebtReportTestObservation
    )
    coverage_summary: tuple[TechnicalDebtReportCoverageItem, ...] = ()
    limitations: tuple[TechnicalDebtReportLimitationView, ...] = ()
    traceability_summary: TechnicalDebtReportTraceabilityView = Field(
        default_factory=TechnicalDebtReportTraceabilityView
    )
    enterprise_context_used: bool = False
    generated_from_assessment_section_version: str = "1.2.0"
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
        "hotspot_presentation_note",
        "generated_from_assessment_section_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="technical debt report field")

    @field_validator(
        "key_metrics",
        "significant_themes",
        "top_production_hotspots",
        "conclusions",
        "recommendations",
        "coverage_summary",
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
