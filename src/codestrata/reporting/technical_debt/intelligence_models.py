"""Technical Debt Intelligence presentation models (Epic 3 Slice 3.4).

HTML/reporting-layer only. Projects existing TechnicalDebtReportSection and
technical-debt-classified findings — does not invent rewrite, productivity,
or broader debt claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

TECHNICAL_DEBT_INTELLIGENCE_SECTION_ID = "report.technical_debt_intelligence"
TECHNICAL_DEBT_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class TechnicalDebtOverviewFact(BaseModel):
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


class TechnicalDebtMeasurementRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    observed_value: str
    threshold: str | None = None
    operator: str | None = None
    scope: str | None = None
    location: str | None = None
    symbol: str | None = None
    availability: str
    limitations: tuple[str, ...] = ()
    evidence_id: str | None = None
    finding_id: str | None = None

    @field_validator("metric_name", "observed_value", "availability", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="measurement field")

    @field_validator(
        "threshold",
        "operator",
        "scope",
        "location",
        "symbol",
        "evidence_id",
        "finding_id",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="measurement optional field")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtHotspotRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    path: str
    symbol: str
    metric_name: str
    observed_value: str
    threshold: str | None = None
    operator: str | None = None
    severity: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    evidence_completeness: str | None = None
    exceedance_sort_key: float = 0.0

    @field_validator(
        "finding_id",
        "path",
        "symbol",
        "metric_name",
        "observed_value",
        "severity",
        "confidence",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot field")

    @field_validator(
        "threshold",
        "operator",
        "evidence_completeness",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="hotspot optional field")

    @field_validator("evidence_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtFindingLink(BaseModel):
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


class TechnicalDebtRecommendationLink(BaseModel):
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


class TechnicalDebtCoverageRow(BaseModel):
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


class TechnicalDebtIntelligenceSection(BaseModel):
    """Customer Technical Debt Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = TECHNICAL_DEBT_INTELLIGENCE_SECTION_ID
    section_version: str = TECHNICAL_DEBT_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[TechnicalDebtOverviewFact, ...] = ()
    measurements: tuple[TechnicalDebtMeasurementRow, ...] = ()
    hotspots: tuple[TechnicalDebtHotspotRow, ...] = ()
    findings: tuple[TechnicalDebtFindingLink, ...] = ()
    recommendations: tuple[TechnicalDebtRecommendationLink, ...] = ()
    coverage_rows: tuple[TechnicalDebtCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
    measured_evidence_count: int = Field(default=0, ge=0)
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
        return require_nonblank(str(value), label="technical debt intelligence field")

    @field_validator(
        "overview_facts",
        "measurements",
        "hotspots",
        "findings",
        "recommendations",
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
