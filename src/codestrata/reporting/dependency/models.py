"""Dependency report presentation models (Phase 4.4.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

DEPENDENCY_REPORT_SECTION_ID = "report.dependency"
DEPENDENCY_REPORT_SECTION_VERSION = "1.0.0"
TOP_MANIFEST_HOTSPOTS = 20
FINDING_DISPLAY_LIMIT = 20
DIAGNOSTIC_SAMPLE_LIMIT = 20
TRACE_SAMPLE_LIMIT = 12


class DependencyReportMetric(BaseModel):
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


class DependencyReportLandscapeCount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    count: int = Field(ge=0)
    group: str = "general"

    @field_validator("key", "label", "group", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="landscape count field")


class DependencyReportFindingView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    source_role: str
    path: str | None = None
    ecosystem: str | None = None
    normalized_identity: str | None = None
    explanation: str
    remediation: str
    original_declaration: str | None = None
    declaration_context: str | None = None
    evidence_ids: tuple[str, ...] = ()
    evidence_count: int = Field(default=0, ge=0)

    @field_validator(
        "finding_id",
        "rule_id",
        "title",
        "severity",
        "confidence",
        "source_role",
        "explanation",
        "remediation",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding view field")

    @field_validator("original_declaration", "declaration_context", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional finding field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyReportHotspotView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    path: str
    source_role: str
    ecosystem: str
    manifest_type: str
    active_declaration_count: int = Field(default=0, ge=0)
    dependency_management_count: int = Field(default=0, ge=0)
    plugin_count: int = Field(default=0, ge=0)
    hygiene_finding_count: int = Field(default=0, ge=0)
    distinct_rule_count: int = Field(default=0, ge=0)
    highest_severity: str
    diagnostics_count: int = Field(default=0, ge=0)
    presentation_order: int = Field(default=1, ge=1)

    @field_validator(
        "hotspot_id",
        "path",
        "source_role",
        "ecosystem",
        "manifest_type",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot view field")


class DependencyReportConclusionView(BaseModel):
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


class DependencyReportRecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    kind: str
    title: str
    action: str
    rationale: str
    conditional: bool = True
    audience: str
    conclusion_ids: tuple[str, ...] = ()

    @field_validator(
        "recommendation_id",
        "kind",
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


class DependencyReportAudienceGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audience: str
    conclusions: tuple[DependencyReportConclusionView, ...] = ()
    recommendations: tuple[DependencyReportRecommendationView, ...] = ()

    @field_validator("audience", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="audience")

    @field_validator("conclusions", "recommendations", mode="before")
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyReportDiagnosticView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    path: str | None = None
    source_role: str
    ecosystem: str | None = None

    @field_validator(
        "diagnostic_id",
        "diagnostic_code",
        "message",
        "source_role",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic view field")


class DependencyReportCoverageView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_schema_version: str = ""
    evidence_fingerprint: str = ""
    evidence_status: str = ""
    manifests_discovered: int = Field(default=0, ge=0)
    manifests_supported: int = Field(default=0, ge=0)
    manifests_parsed: int = Field(default=0, ge=0)
    manifests_partially_parsed: int = Field(default=0, ge=0)
    manifests_failed: int = Field(default=0, ge=0)
    production_parse_failures: int = Field(default=0, ge=0)
    test_fixture_parse_failures: int = Field(default=0, ge=0)
    unsupported_construct_count: int = Field(default=0, ge=0)
    proven_unresolved_count: int = Field(default=0, ge=0)
    unsupported_resolution_count: int = Field(default=0, ge=0)
    diagnostic_total: int = Field(default=0, ge=0)
    diagnostic_samples: tuple[DependencyReportDiagnosticView, ...] = ()
    note: str = (
        "Diagnostics are coverage signals, not hygiene findings."
    )

    @field_validator("diagnostic_samples", mode="before")
    @classmethod
    def normalize_samples(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyReportLimitationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: str
    summary: str
    importance: str = "contextual"

    @field_validator("limitation_id", "category", "summary", "importance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="limitation view field")


class DependencyReportTraceEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation: str
    source_id: str
    target_id: str

    @field_validator("relation", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="trace edge field")


class DependencyReportTraceabilityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_count: int = Field(default=0, ge=0)
    relation_types: tuple[str, ...] = ()
    sample_edges: tuple[DependencyReportTraceEdgeView, ...] = ()
    summary: str = ""

    @field_validator("relation_types", mode="before")
    @classmethod
    def normalize_types(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("sample_edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class DependencyReportProductionHealth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_count: int = Field(default=0, ge=0)
    findings_displayed: int = Field(default=0, ge=0)
    findings_total: int = Field(default=0, ge=0)
    none_detected_statement: str | None = None
    findings: tuple[DependencyReportFindingView, ...] = ()
    affected_manifests: tuple[str, ...] = ()
    conclusions: tuple[DependencyReportConclusionView, ...] = ()
    recommendations: tuple[DependencyReportRecommendationView, ...] = ()

    @field_validator(
        "findings",
        "conclusions",
        "recommendations",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("affected_manifests", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        return tuple(
            str(item).strip().replace("\\", "/")
            for item in as_tuple(value)
            if str(item).strip()
        )


class DependencyReportTestObservations(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    present: bool = False
    finding_count: int = Field(default=0, ge=0)
    findings_displayed: int = Field(default=0, ge=0)
    findings_total: int = Field(default=0, ge=0)
    title: str = "No separate test/fixture observations"
    summary: str = (
        "No test/fixture dependency hygiene findings were recorded for this assessment."
    )
    findings: tuple[DependencyReportFindingView, ...] = ()
    affected_manifests: tuple[str, ...] = ()
    conclusions: tuple[DependencyReportConclusionView, ...] = ()
    recommendations: tuple[DependencyReportRecommendationView, ...] = ()

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="test observation field")

    @field_validator(
        "findings",
        "conclusions",
        "recommendations",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("affected_manifests", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        return tuple(
            str(item).strip().replace("\\", "/")
            for item in as_tuple(value)
            if str(item).strip()
        )


class DependencyReportSection(BaseModel):
    """Presentation-focused Dependency report section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = DEPENDENCY_REPORT_SECTION_ID
    section_version: str = DEPENDENCY_REPORT_SECTION_VERSION
    title: str = "Dependency Assessment"
    status: str
    status_label: str
    status_summary: str
    assessment_scope: str
    repository_name: str
    dependency_pack_id: str | None = None
    dependency_pack_version: str | None = None
    executive_summary: str
    landscape: tuple[DependencyReportLandscapeCount, ...] = ()
    production_health: DependencyReportProductionHealth = Field(
        default_factory=DependencyReportProductionHealth
    )
    test_observations: DependencyReportTestObservations = Field(
        default_factory=DependencyReportTestObservations
    )
    hygiene_findings: tuple[DependencyReportFindingView, ...] = ()
    hygiene_findings_displayed: int = Field(default=0, ge=0)
    hygiene_findings_total: int = Field(default=0, ge=0)
    manifest_hotspots: tuple[DependencyReportHotspotView, ...] = ()
    hotspot_presentation_note: str = (
        "Hotspots are shown in inventory presentation order "
        "(production before test/fixture before unknown; then highest severity, "
        "distinct rules, finding count, path). This is not a risk or priority ranking."
    )
    conclusions: tuple[DependencyReportConclusionView, ...] = ()
    recommendations: tuple[DependencyReportRecommendationView, ...] = ()
    conclusion_groups: tuple[DependencyReportAudienceGroup, ...] = ()
    recommendation_groups: tuple[DependencyReportAudienceGroup, ...] = ()
    coverage: DependencyReportCoverageView = Field(
        default_factory=DependencyReportCoverageView
    )
    diagnostics: tuple[DependencyReportDiagnosticView, ...] = ()
    diagnostics_total: int = Field(default=0, ge=0)
    limitations: tuple[DependencyReportLimitationView, ...] = ()
    traceability: DependencyReportTraceabilityView = Field(
        default_factory=DependencyReportTraceabilityView
    )
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
        return require_nonblank(str(value), label="dependency report field")

    @field_validator(
        "landscape",
        "hygiene_findings",
        "manifest_hotspots",
        "conclusions",
        "recommendations",
        "conclusion_groups",
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
