"""Cloud report presentation models (Phase 4.7.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank

CLOUD_REPORT_SECTION_ID = "report.cloud"
CLOUD_REPORT_SECTION_VERSION = "1.0.0"
THEME_DISPLAY_LIMIT = 12
CONCLUSION_DISPLAY_LIMIT = 12
RECOMMENDATION_DISPLAY_LIMIT = 12
FINDING_ID_DISPLAY_LIMIT = 32
DIAGNOSTIC_DISPLAY_LIMIT = 20
LIMITATION_DISPLAY_LIMIT = 12
TRACE_SAMPLE_LIMIT = 12
TECHNOLOGY_FAMILY_DISPLAY_LIMIT = 12


class CloudReportCountBucket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    count: int = Field(ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return require_nonblank(str(value), label="bucket key")


class CloudReportInventorySummary(BaseModel):
    """Finding ID references and rollup counts (no Finding duplication)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_count: int = Field(default=0, ge=0)
    finding_ids: tuple[str, ...] = ()
    finding_ids_displayed: int = Field(default=0, ge=0)
    by_rule: tuple[CloudReportCountBucket, ...] = ()
    by_severity: tuple[CloudReportCountBucket, ...] = ()
    by_confidence: tuple[CloudReportCountBucket, ...] = ()
    none_detected_statement: str | None = None

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("by_rule", "by_severity", "by_confidence", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportTechnologyFamilyEntry(BaseModel):
    """One technology family coverage row for presentation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family_id: str
    observed: bool = False
    finding_count: int = Field(default=0, ge=0)
    finding_ids: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()

    @field_validator("family_id", mode="before")
    @classmethod
    def normalize_family(cls, value: object) -> str:
        return require_nonblank(str(value), label="family_id")

    @field_validator("finding_ids", "technologies", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class CloudReportTechnologyFamilySummary(BaseModel):
    """Technology family inventory projection (Finding-derived)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    families_observed: int = Field(default=0, ge=0)
    families_total: int = Field(default=0, ge=0)
    entries: tuple[CloudReportTechnologyFamilyEntry, ...] = ()
    note: str = (
        "Technology families summarize Finding-derived cloud signal groups "
        "only. They do not establish cloud readiness or portability."
    )

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportRuleEntryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    finding_count: int = Field(default=0, ge=0)

    @field_validator("rule_id", "evaluation_status", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule entry field")


class CloudReportExecutionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_failed: int = Field(default=0, ge=0)
    total_finding_count: int = Field(default=0, ge=0)
    theme_count: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    entries: tuple[CloudReportRuleEntryView, ...] = ()
    note: str = (
        "Rule execution summarizes registered Cloud Hygiene rules only. "
        "Zero findings are a bounded inventory outcome and do not establish "
        "cloud readiness."
    )

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportCoverageAreaView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: str
    numerator: int | None = None
    denominator: int | None = None
    maturity: str = "unknown"

    @field_validator("area_id", "status", "maturity", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")


class CloudReportCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_pipeline: str = ""
    evidence_status: str = ""
    areas: tuple[CloudReportCoverageAreaView, ...] = ()
    note: str = (
        "Coverage describes Cloud assessment capability areas only. Provider "
        "APIs, readiness scores, and portability verdicts are not measured."
    )

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportThemeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    kind: str
    title: str
    summary: str
    scope: str
    finding_count: int = Field(default=0, ge=0)
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()

    @field_validator("theme_id", "kind", "title", "summary", "scope", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme view field")

    @field_validator("finding_ids", "rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class CloudReportConclusionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    kind: str
    audience: str
    title: str
    summary: str
    confidence: str
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    recommendation_ids: tuple[str, ...] = ()

    @field_validator(
        "conclusion_id",
        "kind",
        "audience",
        "title",
        "summary",
        "confidence",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion view field")

    @field_validator(
        "theme_ids",
        "finding_ids",
        "recommendation_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class CloudReportRecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    kind: str
    title: str
    action: str
    rationale: str
    audience: str
    presentation_group: str
    conclusion_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    conditional: bool = True

    @field_validator(
        "recommendation_id",
        "kind",
        "title",
        "action",
        "rationale",
        "audience",
        "presentation_group",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation view field")

    @field_validator("conclusion_ids", "finding_ids", "rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class CloudReportRecommendationGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group: str
    recommendations: tuple[CloudReportRecommendationView, ...] = ()

    @field_validator("group", mode="before")
    @classmethod
    def normalize_group(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation group")

    @field_validator("recommendations", mode="before")
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportDiagnosticView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    origin: str
    diagnostic_code: str
    message: str

    @field_validator(
        "diagnostic_id",
        "origin",
        "diagnostic_code",
        "message",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic view field")


class CloudReportLimitationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: str
    summary: str

    @field_validator("limitation_id", "category", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation view field")


class CloudReportTraceEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: str
    source_id: str
    target_id: str

    @field_validator("edge_id", "relation", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="trace edge field")


class CloudReportTraceabilityView(BaseModel):
    """Traceability projection using Finding IDs and relationship edges only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = ""
    finding_ids: tuple[str, ...] = ()
    sample_edges: tuple[CloudReportTraceEdgeView, ...] = ()
    edge_count: int = Field(default=0, ge=0)

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("sample_edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class CloudReportSection(BaseModel):
    """Presentation-focused Cloud Intelligence report section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = CLOUD_REPORT_SECTION_ID
    section_version: str = CLOUD_REPORT_SECTION_VERSION
    schema_name: str = "report.cloud"
    title: str = "Cloud Intelligence"
    status: str
    status_label: str
    status_summary: str
    assessment_status: str
    synthesis_status: str
    assessment_scope: str
    repository_name: str
    cloud_pack_id: str | None = None
    cloud_pack_version: str | None = None
    overall_posture_summary: str = ""
    executive_summary: str
    coverage_summary: CloudReportCoverageSummary = Field(default_factory=CloudReportCoverageSummary)
    execution_summary: CloudReportExecutionSummary = Field(
        default_factory=CloudReportExecutionSummary
    )
    inventory_summary: CloudReportInventorySummary = Field(
        default_factory=CloudReportInventorySummary
    )
    technology_family_summary: CloudReportTechnologyFamilySummary = Field(
        default_factory=CloudReportTechnologyFamilySummary
    )
    themes: tuple[CloudReportThemeView, ...] = ()
    themes_displayed: int = Field(default=0, ge=0)
    themes_total: int = Field(default=0, ge=0)
    conclusions: tuple[CloudReportConclusionView, ...] = ()
    conclusions_displayed: int = Field(default=0, ge=0)
    conclusions_total: int = Field(default=0, ge=0)
    recommendations: tuple[CloudReportRecommendationView, ...] = ()
    recommendation_groups: tuple[CloudReportRecommendationGroup, ...] = ()
    recommendations_displayed: int = Field(default=0, ge=0)
    recommendations_total: int = Field(default=0, ge=0)
    diagnostics: tuple[CloudReportDiagnosticView, ...] = ()
    diagnostics_displayed: int = Field(default=0, ge=0)
    diagnostics_total: int = Field(default=0, ge=0)
    limitations: tuple[CloudReportLimitationView, ...] = ()
    limitations_displayed: int = Field(default=0, ge=0)
    limitations_total: int = Field(default=0, ge=0)
    traceability: CloudReportTraceabilityView = Field(default_factory=CloudReportTraceabilityView)
    generated_from_assessment_section_version: str = "1.2.0"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "section_version",
        "schema_name",
        "title",
        "status",
        "status_label",
        "status_summary",
        "assessment_status",
        "synthesis_status",
        "assessment_scope",
        "repository_name",
        "executive_summary",
        "generated_from_assessment_section_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="cloud report field")

    @field_validator("overall_posture_summary", mode="before")
    @classmethod
    def normalize_posture(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator(
        "themes",
        "conclusions",
        "recommendations",
        "recommendation_groups",
        "diagnostics",
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
