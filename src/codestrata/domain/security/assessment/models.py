"""Security assessment section domain models (Phase 4.5.4).

Additive inventory / hotspot contract on schema 1.2.0. No themes, conclusions,
recommendations, CVE/OWASP mappings, or risk scores.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.security.assessment.enums import (
    SecurityAssessmentStatus,
    SecurityCoverageAreaStatus,
    SecurityCoverageMaturity,
    SecurityLimitationCategory,
    SecuritySourceRole,
    SecurityTraceabilityRelation,
)
from codestrata.domain.security.assessment.identifiers import (
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.security.synthesis.models import (
    SecurityConcentrationFact,
    SecurityConclusion,
    SecurityRecommendation,
    SecuritySynthesisResult,
    SecurityTheme,
)
from codestrata.domain.security.taxonomy import SecurityCategory


class SecurityExecutionSummary(BaseModel):
    """Bounded technical execution summary for the security section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    security_rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_insufficient_evidence: int = Field(default=0, ge=0)
    rules_failed: int = Field(default=0, ge=0)
    suppressed_finding_count: int = Field(default=0, ge=0)
    visible_finding_count: int = Field(default=0, ge=0)
    total_finding_count: int = Field(default=0, ge=0)
    findings_by_rule: dict[str, int] = Field(default_factory=dict)
    pack_id: str = ""
    pack_version: str = ""
    pack_enabled: bool = False
    theme_count: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)

    @field_validator("findings_by_rule", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("findings_by_rule must be a dictionary")
        return {
            str(key): int(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }


class SecurityCoverageArea(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: SecurityCoverageAreaStatus = SecurityCoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: SecurityCoverageMaturity = SecurityCoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "security_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[SecurityCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityFindingReference(BaseModel):
    """Bounded reference to a canonical security finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    security_category: SecurityCategory = SecurityCategory.UNKNOWN
    finding_category: str = "security"
    source_role: SecuritySourceRole = SecuritySourceRole.UNKNOWN
    affected_scope: tuple[str, ...] = ()
    severity: str
    confidence: str = "medium"
    status: str = "visible"
    evidence_count: int = Field(default=0, ge=0)
    suppression_state: str = "unsuppressed"
    taxonomy_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("security",)
    path: str | None = None
    location: str | None = None
    explanation: str | None = None
    remediation: str | None = None
    evidence_ids: tuple[str, ...] = ()

    @field_validator(
        "finding_id",
        "rule_id",
        "title",
        "severity",
        "confidence",
        "status",
        "suppression_state",
        "finding_category",
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

    @field_validator(
        "path",
        "location",
        "explanation",
        "remediation",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="optional finding field")
        if text is None:
            return None
        return text.replace("\\", "/")


class SecurityLimitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: SecurityLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "security_assessment"
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


class SecurityTraceabilityEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: SecurityTraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class SecurityTraceabilityIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[SecurityTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class SecurityEvidenceSummary(BaseModel):
    """Bounded projection of repository-sensitive evidence (not full evidence)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_schema_name: str = ""
    evidence_schema_version: str = ""
    evidence_fingerprint: str = ""
    collection_status: str = "not_configured"
    candidate_artifacts_discovered: int = Field(default=0, ge=0)
    artifacts_inspected: int = Field(default=0, ge=0)
    metadata_only_artifacts: int = Field(default=0, ge=0)
    private_key_signatures_observed: int = Field(default=0, ge=0)
    public_certificate_signatures_observed: int = Field(default=0, ge=0)
    structured_files_parsed: int = Field(default=0, ge=0)
    configuration_facts_collected: int = Field(default=0, ge=0)
    credential_sensitive_facts: int = Field(default=0, ge=0)
    environment_reference_facts: int = Field(default=0, ge=0)
    placeholder_facts: int = Field(default=0, ge=0)
    malformed_files: int = Field(default=0, ge=0)
    unsupported_binaries: int = Field(default=0, ge=0)
    skipped_files: int = Field(default=0, ge=0)
    source_roles_represented: tuple[str, ...] = ()
    formats_represented: tuple[str, ...] = ()
    evidence_diagnostic_count: int = Field(default=0, ge=0)
    evidence_limitation_count: int = Field(default=0, ge=0)
    note: str = (
        "Evidence summary projects repository-sensitive coverage only; "
        "zero signatures or findings do not prove the repository is secure."
    )

    @field_validator(
        "source_roles_represented",
        "formats_represented",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()})
        )


class SecurityRoleFindingInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_role: SecuritySourceRole
    finding_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    rule_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("rule_counts", "severity_counts", "category_counts", mode="before")
    @classmethod
    def normalize_maps(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("inventory counts must be dictionaries")
        return {
            str(key): int(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }


class SecurityFindingInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_source_role: SecuritySourceRole = SecuritySourceRole.PRODUCTION
    production: SecurityRoleFindingInventory = Field(
        default_factory=lambda: SecurityRoleFindingInventory(
            source_role=SecuritySourceRole.PRODUCTION
        )
    )
    test: SecurityRoleFindingInventory = Field(
        default_factory=lambda: SecurityRoleFindingInventory(
            source_role=SecuritySourceRole.TEST
        )
    )
    unknown: SecurityRoleFindingInventory = Field(
        default_factory=lambda: SecurityRoleFindingInventory(
            source_role=SecuritySourceRole.UNKNOWN
        )
    )
    total_finding_count: int = Field(default=0, ge=0)


class SecurityRuleInventoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    finding_count: int = Field(default=0, ge=0)
    production_finding_count: int = Field(default=0, ge=0)
    test_finding_count: int = Field(default=0, ge=0)
    unknown_finding_count: int = Field(default=0, ge=0)
    diagnostic_count: int = Field(default=0, ge=0)

    @field_validator("rule_id", "evaluation_status", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule inventory field")


class SecurityRuleInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[SecurityRuleInventoryEntry, ...] = ()

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityCountBucket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    count: int = Field(default=0, ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return require_nonblank(str(value), label="bucket key")


class SecurityCategoryInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[SecurityCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecuritySeverityInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[SecurityCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityConfidenceInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[SecurityCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityEvidenceTypeInventory(BaseModel):
    """Bounded evidence-type counts (facts, not interpretation)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_candidates: int = Field(default=0, ge=0)
    private_key_material: int = Field(default=0, ge=0)
    certificates: int = Field(default=0, ge=0)
    metadata_only_keystores: int = Field(default=0, ge=0)
    credential_configuration_facts: int = Field(default=0, ge=0)
    transport_configuration_facts: int = Field(default=0, ge=0)
    authentication_configuration_facts: int = Field(default=0, ge=0)
    cors_configuration_facts: int = Field(default=0, ge=0)
    debug_configuration_facts: int = Field(default=0, ge=0)
    placeholders: int = Field(default=0, ge=0)
    environment_references: int = Field(default=0, ge=0)


class SecurityHotspot(BaseModel):
    """Repository location with Security finding concentration (not risk wording)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspot_id: str
    path: str
    label: str = "Security finding hotspot"
    total_finding_count: int = Field(default=0, ge=0)
    production_finding_count: int = Field(default=0, ge=0)
    test_finding_count: int = Field(default=0, ge=0)
    unknown_finding_count: int = Field(default=0, ge=0)
    rule_ids: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    highest_severity: str = "informational"
    finding_ids: tuple[str, ...] = ()

    @field_validator(
        "hotspot_id",
        "path",
        "label",
        "highest_severity",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        text = require_nonblank(str(value), label="hotspot field")
        return text.replace("\\", "/")

    @field_validator("rule_ids", "categories", "finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityHotspotInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hotspots: tuple[SecurityHotspot, ...] = ()
    note: str = (
        "Hotspots order repository locations by finding concentration for "
        "presentation only. They do not assert risk, vulnerability, or severity "
        "beyond observed Finding facts."
    )

    @field_validator("hotspots", mode="before")
    @classmethod
    def normalize_hotspots(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityDiagnosticRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_id: str
    diagnostic_code: str
    message: str
    origin: str = "assessment"
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
        return require_nonblank(str(value), label="diagnostic field")

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        if value is None:
            return None
        text = optional_nonblank(str(value), label="diagnostic path")
        return text.replace("\\", "/") if text else None


class SecurityDiagnosticsSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_diagnostics: tuple[SecurityDiagnosticRecord, ...] = ()
    rule_diagnostics: tuple[SecurityDiagnosticRecord, ...] = ()
    assessment_diagnostics: tuple[SecurityDiagnosticRecord, ...] = ()

    @field_validator(
        "evidence_diagnostics",
        "rule_diagnostics",
        "assessment_diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_records(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class SecurityAssessmentSection(BaseModel):
    """First-class security section of a CodeStrata assessment (schema 1.2.0).

    Production-primary finding views plus complete inventories and hotspots.
    No synthesis, conclusions, recommendations, scores, or report projection.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    schema_name: str = SCHEMA_NAME
    section_version: str = SECTION_SCHEMA_VERSION
    assessment_id: str
    status: SecurityAssessmentStatus
    repository_id: str
    security_pack_id: str | None = None
    security_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: SecurityExecutionSummary = Field(
        default_factory=SecurityExecutionSummary
    )
    evidence_summary: SecurityEvidenceSummary = Field(
        default_factory=SecurityEvidenceSummary
    )
    coverage: SecurityCoverageSummary = Field(default_factory=SecurityCoverageSummary)
    finding_ids: tuple[str, ...] = ()
    finding_summaries: tuple[SecurityFindingReference, ...] = ()
    all_finding_ids: tuple[str, ...] = ()
    all_finding_summaries: tuple[SecurityFindingReference, ...] = ()
    finding_inventory: SecurityFindingInventory = Field(
        default_factory=SecurityFindingInventory
    )
    rule_inventory: SecurityRuleInventory = Field(default_factory=SecurityRuleInventory)
    category_inventory: SecurityCategoryInventory = Field(
        default_factory=SecurityCategoryInventory
    )
    severity_inventory: SecuritySeverityInventory = Field(
        default_factory=SecuritySeverityInventory
    )
    confidence_inventory: SecurityConfidenceInventory = Field(
        default_factory=SecurityConfidenceInventory
    )
    evidence_type_inventory: SecurityEvidenceTypeInventory = Field(
        default_factory=SecurityEvidenceTypeInventory
    )
    hotspot_inventory: SecurityHotspotInventory = Field(
        default_factory=SecurityHotspotInventory
    )
    diagnostics_summary: SecurityDiagnosticsSummary = Field(
        default_factory=SecurityDiagnosticsSummary
    )
    synthesis: SecuritySynthesisResult = Field(
        default_factory=SecuritySynthesisResult
    )
    themes: tuple[SecurityTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    concentration_facts: tuple[SecurityConcentrationFact, ...] = ()
    conclusions: tuple[SecurityConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[SecurityRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    limitations: tuple[SecurityLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: SecurityTraceabilityIndex = Field(
        default_factory=SecurityTraceabilityIndex
    )
    enterprise_context_used: bool = False
    business_impact: str = "unknown"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "schema_name",
        "section_version",
        "assessment_id",
        "repository_id",
        "business_impact",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="security section field")

    @field_validator(
        "security_pack_id",
        "security_pack_version",
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
        "diagnostics",
        "theme_ids",
        "conclusion_ids",
        "recommendation_ids",
        mode="before",
    )
    @classmethod
    def normalize_id_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator(
        "finding_summaries",
        "all_finding_summaries",
        "limitations",
        "themes",
        "concentration_facts",
        "conclusions",
        "recommendations",
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
        return {str(key): str(item) for key, item in sorted(value.items())}
