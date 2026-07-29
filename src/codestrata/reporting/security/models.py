"""Security report presentation models (Phase 4.5.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

SECURITY_REPORT_SECTION_ID = "report.security"
SECURITY_REPORT_SECTION_VERSION = "1.0.0"
THEME_DISPLAY_LIMIT = 12
CONCLUSION_DISPLAY_LIMIT = 12
RECOMMENDATION_DISPLAY_LIMIT = 12
HOTSPOT_DISPLAY_LIMIT = 20
FINDING_DISPLAY_LIMIT = 20
DIAGNOSTIC_DISPLAY_LIMIT = 20
LIMITATION_DISPLAY_LIMIT = 12
TRACE_SAMPLE_LIMIT = 12


class SecurityReportCountBucket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    count: int = Field(ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return require_nonblank(str(value), label="bucket key")


class SecurityReportFindingView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    source_role: str
    category: str
    path: str | None = None
    explanation: str | None = None
    remediation: str | None = None

    @field_validator(
        "finding_id",
        "rule_id",
        "title",
        "severity",
        "confidence",
        "source_role",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding view field")

    @field_validator("path", "explanation", "remediation", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="optional finding field")
        return text.replace("\\", "/") if text else None


class SecurityReportFindingSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    production_finding_count: int = Field(default=0, ge=0)
    test_finding_count: int = Field(default=0, ge=0)
    unknown_finding_count: int = Field(default=0, ge=0)
    all_finding_count: int = Field(default=0, ge=0)
    hotspot_count: int = Field(default=0, ge=0)
    locations_represented: int = Field(default=0, ge=0)
    by_severity: tuple[SecurityReportCountBucket, ...] = ()
    by_category: tuple[SecurityReportCountBucket, ...] = ()
    by_rule: tuple[SecurityReportCountBucket, ...] = ()
    production_findings: tuple[SecurityReportFindingView, ...] = ()
    production_findings_displayed: int = Field(default=0, ge=0)
    additional_observations: tuple[SecurityReportFindingView, ...] = ()
    additional_observations_displayed: int = Field(default=0, ge=0)
    none_detected_statement: str | None = None

    @field_validator(
        "by_severity",
        "by_category",
        "by_rule",
        "production_findings",
        "additional_observations",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityReportCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_status: str = ""
    evidence_schema_name: str = ""
    evidence_schema_version: str = ""
    candidate_artifacts_discovered: int = Field(default=0, ge=0)
    artifacts_inspected: int = Field(default=0, ge=0)
    structured_files_parsed: int = Field(default=0, ge=0)
    configuration_facts_collected: int = Field(default=0, ge=0)
    rules_registered: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    unsupported_binaries: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    source_roles_represented: tuple[str, ...] = ()
    formats_represented: tuple[str, ...] = ()
    note: str = (
        "Coverage describes supported repository-sensitive evidence only. "
        "Candidate artifacts are not proof of secrets. Zero findings are scoped "
        "to supported evidence; runtime and Git history are not assessed."
    )

    @field_validator("source_roles_represented", "formats_represented", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()})
        )


class SecurityReportThemeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    kind: str
    title: str
    summary: str
    scope: str
    source_role: str
    finding_count: int = Field(default=0, ge=0)
    rule_ids: tuple[str, ...] = ()

    @field_validator(
        "theme_id",
        "kind",
        "title",
        "summary",
        "scope",
        "source_role",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme view field")

    @field_validator("rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityReportConclusionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    kind: str
    audience: str
    title: str
    summary: str
    confidence: str
    theme_ids: tuple[str, ...] = ()
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

    @field_validator("theme_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityReportRecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    kind: str
    title: str
    action: str
    rationale: str
    audience: str
    presentation_group: str
    conclusion_ids: tuple[str, ...] = ()
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

    @field_validator("conclusion_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityReportRecommendationGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group: str
    recommendations: tuple[SecurityReportRecommendationView, ...] = ()

    @field_validator("group", mode="before")
    @classmethod
    def normalize_group(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation group")

    @field_validator("recommendations", mode="before")
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityReportHotspotView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    path: str
    label: str = "Security finding hotspot"
    total_finding_count: int = Field(default=0, ge=0)
    production_finding_count: int = Field(default=0, ge=0)
    test_finding_count: int = Field(default=0, ge=0)
    unknown_finding_count: int = Field(default=0, ge=0)
    highest_severity: str
    rule_ids: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    presentation_order: int = Field(default=1, ge=1)

    @field_validator(
        "hotspot_id",
        "path",
        "label",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="hotspot view field")
        return text.replace("\\", "/")

    @field_validator("rule_ids", "categories", "finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityReportDiagnosticView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    origin: str
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
        return require_nonblank(str(value), label="diagnostic view field")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="diagnostic path")
        return text.replace("\\", "/") if text else None


class SecurityReportLimitationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: str
    summary: str
    importance: str = "contextual"

    @field_validator("limitation_id", "category", "summary", "importance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation view field")


class SecurityReportTraceEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation: str
    source_id: str
    target_id: str

    @field_validator("relation", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="trace edge field")


class SecurityReportTraceabilityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_count: int = Field(default=0, ge=0)
    sample_edges: tuple[SecurityReportTraceEdgeView, ...] = ()
    summary: str = ""

    @field_validator("sample_edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityReportSection(BaseModel):
    """Presentation-focused Security Intelligence report section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECURITY_REPORT_SECTION_ID
    section_version: str = SECURITY_REPORT_SECTION_VERSION
    schema_name: str = "report.security"
    title: str = "Security Intelligence"
    status: str
    status_label: str
    status_summary: str
    assessment_status: str
    synthesis_status: str
    assessment_scope: str
    repository_name: str
    security_pack_id: str | None = None
    security_pack_version: str | None = None
    executive_summary: str
    coverage_summary: SecurityReportCoverageSummary = Field(
        default_factory=SecurityReportCoverageSummary
    )
    finding_summary: SecurityReportFindingSummary = Field(
        default_factory=SecurityReportFindingSummary
    )
    themes: tuple[SecurityReportThemeView, ...] = ()
    themes_displayed: int = Field(default=0, ge=0)
    themes_total: int = Field(default=0, ge=0)
    conclusions: tuple[SecurityReportConclusionView, ...] = ()
    conclusions_displayed: int = Field(default=0, ge=0)
    conclusions_total: int = Field(default=0, ge=0)
    recommendations: tuple[SecurityReportRecommendationView, ...] = ()
    recommendation_groups: tuple[SecurityReportRecommendationGroup, ...] = ()
    recommendations_displayed: int = Field(default=0, ge=0)
    recommendations_total: int = Field(default=0, ge=0)
    hotspots: tuple[SecurityReportHotspotView, ...] = ()
    hotspots_displayed: int = Field(default=0, ge=0)
    hotspots_total: int = Field(default=0, ge=0)
    hotspot_presentation_note: str = (
        "Hotspots order repository locations by finding concentration for "
        "presentation only. They do not assert risk, vulnerability, or priority."
    )
    diagnostics: tuple[SecurityReportDiagnosticView, ...] = ()
    diagnostics_displayed: int = Field(default=0, ge=0)
    diagnostics_total: int = Field(default=0, ge=0)
    limitations: tuple[SecurityReportLimitationView, ...] = ()
    limitations_displayed: int = Field(default=0, ge=0)
    limitations_total: int = Field(default=0, ge=0)
    traceability: SecurityReportTraceabilityView = Field(
        default_factory=SecurityReportTraceabilityView
    )
    generated_from_assessment_section_version: str = "1.3.0"
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
        "hotspot_presentation_note",
        "generated_from_assessment_section_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="security report field")

    @field_validator(
        "themes",
        "conclusions",
        "recommendations",
        "recommendation_groups",
        "hotspots",
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
