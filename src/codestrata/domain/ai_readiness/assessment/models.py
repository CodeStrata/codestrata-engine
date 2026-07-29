"""AI Readiness assessment domain models (Phase 4.8.5).

Schema 1.2.0 adds deterministic synthesis (themes, conclusions,
recommendations) over AI Readiness inventories. No report projection fields.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.ai_readiness.assessment.enums import (
    AiReadinessAssessmentStatus,
    AiReadinessCoverageAreaStatus,
    AiReadinessCoverageMaturity,
    AiReadinessLimitationCategory,
    AiReadinessTraceabilityRelation,
)
from codestrata.domain.ai_readiness.assessment.identifiers import (
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.ai_readiness.synthesis.models import (
    AiReadinessConclusion,
    AiReadinessRecommendation,
    AiReadinessSynthesisResult,
    AiReadinessTheme,
)
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class AiReadinessExecutionSummary(BaseModel):
    """Bounded technical execution summary for the AI Readiness section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ai_readiness_rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_failed: int = Field(default=0, ge=0)
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


class AiReadinessCoverageArea(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: AiReadinessCoverageAreaStatus = AiReadinessCoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: AiReadinessCoverageMaturity = AiReadinessCoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "ai_readiness_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class AiReadinessCoverageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[AiReadinessCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AiReadinessLimitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: AiReadinessLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "ai_readiness_assessment"
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


class AiReadinessTraceabilityEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: AiReadinessTraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class AiReadinessTraceabilityIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[AiReadinessTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class AiReadinessCountBucket(BaseModel):
    """Deterministic count bucket for inventory aggregations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    count: int = Field(default=0, ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return require_nonblank(str(value), label="bucket key")


class AiReadinessFindingInventory(BaseModel):
    """Finding ID references and rollup counts (no Finding duplication)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    rule_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    confidence_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))

    @field_validator(
        "rule_counts",
        "severity_counts",
        "confidence_counts",
        mode="before",
    )
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("inventory counts must be dictionaries")
        return {
            str(key): int(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }


class AiReadinessRuleInventoryEntry(BaseModel):
    """Per-rule execution and finding-count inventory entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    finding_count: int = Field(default=0, ge=0)
    diagnostic_count: int = Field(default=0, ge=0)

    @field_validator("rule_id", "evaluation_status", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule inventory field")


class AiReadinessRuleInventory(BaseModel):
    """Registered AI Readiness Hygiene rule inventory (applicable vs matched)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[AiReadinessRuleInventoryEntry, ...] = ()
    rules_planned: int = Field(default=0, ge=0)
    rules_executed: int = Field(default=0, ge=0)
    rules_matched: int = Field(default=0, ge=0)
    rules_not_matched: int = Field(default=0, ge=0)
    rules_not_applicable: int = Field(default=0, ge=0)
    rules_failed: int = Field(default=0, ge=0)

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AiReadinessSeverityInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[AiReadinessCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AiReadinessConfidenceInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[AiReadinessCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AiReadinessCapabilityFamilyEntry(BaseModel):
    """One AI readiness capability family coverage row (Finding-derived)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family_id: str
    observed: bool = False
    finding_count: int = Field(default=0, ge=0)
    finding_ids: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()

    @field_validator("family_id", mode="before")
    @classmethod
    def normalize_family(cls, value: object) -> str:
        return require_nonblank(str(value), label="family_id")

    @field_validator("finding_ids", "signals", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class AiReadinessCapabilityFamilyInventory(BaseModel):
    """Coverage of API boundaries / documentation / data retrieval / AI
    integrations / tool-MCP / workflow-agents / observability-governance
    derived from Findings only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[AiReadinessCapabilityFamilyEntry, ...] = ()
    families_observed: int = Field(default=0, ge=0)
    families_total: int = Field(default=0, ge=0)

    @field_validator("entries", mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AiReadinessAssessmentSection(BaseModel):
    """First-class AI Readiness section of a CodeStrata assessment (schema 1.2.0).

    Inventory + deterministic synthesis. No report projection fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    schema_name: str = SCHEMA_NAME
    section_version: str = SECTION_SCHEMA_VERSION
    assessment_id: str
    status: AiReadinessAssessmentStatus
    capability: str = "ai_readiness"
    repository_id: str
    ai_readiness_pack_id: str | None = None
    ai_readiness_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: AiReadinessExecutionSummary = Field(
        default_factory=AiReadinessExecutionSummary
    )
    coverage: AiReadinessCoverageSummary = Field(default_factory=AiReadinessCoverageSummary)
    finding_inventory: AiReadinessFindingInventory = Field(
        default_factory=AiReadinessFindingInventory
    )
    rule_inventory: AiReadinessRuleInventory = Field(default_factory=AiReadinessRuleInventory)
    severity_inventory: AiReadinessSeverityInventory = Field(
        default_factory=AiReadinessSeverityInventory
    )
    confidence_inventory: AiReadinessConfidenceInventory = Field(
        default_factory=AiReadinessConfidenceInventory
    )
    capability_family_inventory: AiReadinessCapabilityFamilyInventory = Field(
        default_factory=AiReadinessCapabilityFamilyInventory
    )
    synthesis: AiReadinessSynthesisResult = Field(default_factory=AiReadinessSynthesisResult)
    themes: tuple[AiReadinessTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    conclusions: tuple[AiReadinessConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[AiReadinessRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    all_finding_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    limitations: tuple[AiReadinessLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: AiReadinessTraceabilityIndex = Field(default_factory=AiReadinessTraceabilityIndex)
    enterprise_context_used: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "section_id",
        "schema_name",
        "section_version",
        "assessment_id",
        "capability",
        "repository_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="ai readiness section field")

    @field_validator("ai_readiness_pack_id", "ai_readiness_pack_version", mode="before")
    @classmethod
    def normalize_optional_pack(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="pack field")

    @field_validator(
        "evidence_pipeline",
        "graph_fingerprint",
        "evidence_fingerprint",
        "configuration_fingerprint",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator(
        "finding_ids",
        "all_finding_ids",
        "findings",
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
        "limitations",
        "themes",
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
