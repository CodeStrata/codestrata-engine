"""Test assessment domain models (Phase 4.6.5).

Additive inventory + synthesis contract on schema 1.2.0. No report projection
fields.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.testing.assessment.enums import (
    TestAssessmentStatus,
    TestCoverageAreaStatus,
    TestCoverageMaturity,
    TestLimitationCategory,
    TestTraceabilityRelation,
)
from codestrata.domain.testing.assessment.identifiers import (
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.testing.synthesis.models import (
    TestConclusion,
    TestingSynthesisResult,
    TestRecommendation,
    TestTheme,
)


class TestExecutionSummary(BaseModel):
    """Bounded technical execution summary for the Test section."""

    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    testing_rules_planned: int = Field(default=0, ge=0)
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


class TestCoverageArea(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    area_id: str
    status: TestCoverageAreaStatus = TestCoverageAreaStatus.UNKNOWN
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    maturity: TestCoverageMaturity = TestCoverageMaturity.UNKNOWN
    limitations: tuple[str, ...] = ()
    provenance: str = "testing_assessment"

    @field_validator("area_id", "provenance", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage area field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TestCoverageSummary(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    areas: tuple[TestCoverageArea, ...] = ()

    @field_validator("areas", mode="before")
    @classmethod
    def normalize_areas(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TestLimitation(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    limitation_id: str
    category: TestLimitationCategory
    summary: str
    affected_capability: str
    importance: str = "contextual"
    provenance: str = "testing_assessment"
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


class TestTraceabilityEdge(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relation: TestTraceabilityRelation
    source_id: str
    target_id: str

    @field_validator("edge_id", "source_id", "target_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="traceability field")


class TestTraceabilityIndex(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    edges: tuple[TestTraceabilityEdge, ...] = ()

    @field_validator("edges", mode="before")
    @classmethod
    def normalize_edges(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class TestCountBucket(BaseModel):
    """Deterministic count bucket for inventory aggregations."""

    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    count: int = Field(default=0, ge=0)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return require_nonblank(str(value), label="bucket key")


class TestFindingInventory(BaseModel):
    """Finding ID references and rollup counts (no Finding duplication)."""

    __test__ = False

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


class TestRuleInventoryEntry(BaseModel):
    """Per-rule execution and finding-count inventory entry."""

    __test__ = False

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


class TestRuleInventory(BaseModel):
    """Registered Test Hygiene rule inventory (applicable vs matched)."""

    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[TestRuleInventoryEntry, ...] = ()
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


class TestSeverityInventory(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[TestCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TestConfidenceInventory(BaseModel):
    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    buckets: tuple[TestCountBucket, ...] = ()

    @field_validator("buckets", mode="before")
    @classmethod
    def normalize_buckets(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class TestAssessmentSection(BaseModel):
    """First-class Test section of a CodeStrata assessment (schema 1.2.0).

    Inventory + deterministic synthesis. No report projection.
    """

    __test__ = False

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECTION_ID
    schema_name: str = SCHEMA_NAME
    section_version: str = SECTION_SCHEMA_VERSION
    assessment_id: str
    status: TestAssessmentStatus
    capability: str = "testing"
    repository_id: str
    testing_pack_id: str | None = None
    testing_pack_version: str | None = None
    evidence_pipeline: str = "not_configured"
    graph_fingerprint: str = ""
    evidence_fingerprint: str = ""
    configuration_fingerprint: str = ""
    execution_summary: TestExecutionSummary = Field(default_factory=TestExecutionSummary)
    coverage: TestCoverageSummary = Field(default_factory=TestCoverageSummary)
    finding_inventory: TestFindingInventory = Field(default_factory=TestFindingInventory)
    rule_inventory: TestRuleInventory = Field(default_factory=TestRuleInventory)
    severity_inventory: TestSeverityInventory = Field(default_factory=TestSeverityInventory)
    confidence_inventory: TestConfidenceInventory = Field(default_factory=TestConfidenceInventory)
    synthesis: TestingSynthesisResult = Field(default_factory=TestingSynthesisResult)
    themes: tuple[TestTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    conclusions: tuple[TestConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[TestRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    all_finding_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    limitations: tuple[TestLimitation, ...] = ()
    diagnostics: tuple[str, ...] = ()
    traceability: TestTraceabilityIndex = Field(default_factory=TestTraceabilityIndex)
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
        return require_nonblank(str(value), label="testing section field")

    @field_validator("testing_pack_id", "testing_pack_version", mode="before")
    @classmethod
    def normalize_optional_pack(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="pack field")

    @field_validator(
        "finding_ids",
        "all_finding_ids",
        "findings",
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
