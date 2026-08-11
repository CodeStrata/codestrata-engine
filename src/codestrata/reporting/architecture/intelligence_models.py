"""Architecture Intelligence presentation models (Epic 3 Slice 3.3).

HTML/reporting-layer only. Projects existing ArchitectureReportSection and
architecture-classified findings — does not invent runtime topology or
modernity claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

ARCHITECTURE_INTELLIGENCE_SECTION_ID = "report.architecture_intelligence"
ARCHITECTURE_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class ArchitectureOverviewFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    note: str | None = None

    @field_validator("label", "value", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="overview fact field")

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="overview note")


class ArchitectureInventoryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: str
    detail: str | None = None
    source: str | None = None

    @field_validator("name", "kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="inventory item field")

    @field_validator("detail", "source", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="inventory optional field")


class ArchitectureFindingLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    title: str
    severity: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    affected_scope: tuple[str, ...] = ()

    @field_validator("finding_id", "title", "severity", "confidence", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding link field")

    @field_validator("evidence_ids", "recommendation_ids", "affected_scope", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureRecommendationLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    priority: str | None = None
    finding_ids: tuple[str, ...] = ()
    objective: str | None = None

    @field_validator("recommendation_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation link field")

    @field_validator("finding_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("priority", "objective", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="recommendation optional field")


class ArchitectureConclusionLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    title: str
    summary: str
    confidence: str
    primary_finding_id: str | None = None
    supporting_finding_ids: tuple[str, ...] = ()
    recommendation_group_ids: tuple[str, ...] = ()
    affected_scope: tuple[str, ...] = ()
    severity_summary: str | None = None

    @field_validator("conclusion_id", "title", "summary", "confidence", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion link field")

    @field_validator(
        "supporting_finding_ids",
        "recommendation_group_ids",
        "affected_scope",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureGraphEvidenceRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: str
    relationship_type: str | None = None
    reference_kind: str | None = None
    cycle_id: str | None = None
    location: str | None = None
    graph_artifact_ref: str | None = None
    finding_id: str | None = None
    evidence_id: str | None = None

    @field_validator("identity", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph evidence identity")

    @field_validator(
        "relationship_type",
        "reference_kind",
        "cycle_id",
        "location",
        "graph_artifact_ref",
        "finding_id",
        "evidence_id",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="graph evidence optional field")


class ArchitectureMeasurementRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    observed_value: str
    threshold: str | None = None
    operator: str | None = None
    scope: str | None = None
    limitations: tuple[str, ...] = ()
    evidence_id: str | None = None
    finding_id: str | None = None

    @field_validator("metric_name", "observed_value", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="measurement field")

    @field_validator("threshold", "operator", "scope", "evidence_id", "finding_id", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="measurement optional field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class ArchitectureCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    status: str
    display: str
    note: str | None = None

    @field_validator("label", "status", "display", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage row field")

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="coverage note")


class ArchitectureIntelligenceSection(BaseModel):
    """Customer Architecture Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = ARCHITECTURE_INTELLIGENCE_SECTION_ID
    section_version: str = ARCHITECTURE_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[ArchitectureOverviewFact, ...] = ()
    inventory_items: tuple[ArchitectureInventoryItem, ...] = ()
    findings: tuple[ArchitectureFindingLink, ...] = ()
    recommendations: tuple[ArchitectureRecommendationLink, ...] = ()
    conclusions: tuple[ArchitectureConclusionLink, ...] = ()
    graph_evidence: tuple[ArchitectureGraphEvidenceRow, ...] = ()
    measurements: tuple[ArchitectureMeasurementRow, ...] = ()
    coverage_rows: tuple[ArchitectureCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    graph_available: bool = False
    empty_findings_message: str | None = None

    @field_validator(
        "section_id",
        "section_version",
        "status",
        "status_label",
        "status_summary",
        "confidence",
        "confidence_label",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="architecture intelligence field")

    @field_validator(
        "overview_facts",
        "inventory_items",
        "findings",
        "recommendations",
        "conclusions",
        "graph_evidence",
        "measurements",
        "coverage_rows",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("empty_findings_message", mode="before")
    @classmethod
    def normalize_message(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="empty findings message")
