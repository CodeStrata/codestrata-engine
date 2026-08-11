"""Security Intelligence presentation models (Epic 3 Slice 3.6).

HTML/reporting-layer only. Projects existing SecurityReportSection and
security-hygiene findings — does not invent CVE, vulnerability, penetration,
DAST, compliance, or runtime security claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

SECURITY_INTELLIGENCE_SECTION_ID = "report.security_intelligence"
SECURITY_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class SecurityOverviewFact(BaseModel):
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


class SecurityArtifactRow(BaseModel):
    """Sensitive artifact inventory row — classification/kind + relative path only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    classification: str
    path: str | None = None
    kind: str | None = None
    note: str | None = None

    @field_validator("classification", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="artifact classification")

    @field_validator("path", "kind", "note", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="artifact optional field")


class SecurityConfigObservationRow(BaseModel):
    """Configuration observation — fact label + relative path; never raw values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    path: str | None = None
    note: str | None = None
    evidence_id: str | None = None
    redacted_snippet: str | None = None

    @field_validator("label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="config observation label")

    @field_validator("path", "note", "evidence_id", "redacted_snippet", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="config observation optional field")


class SecurityFindingLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    title: str
    severity: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    path: str | None = None
    rule_id: str
    evidence_completeness: str | None = None

    @field_validator(
        "finding_id",
        "title",
        "severity",
        "confidence",
        "rule_id",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding link field")

    @field_validator("path", "evidence_completeness", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="finding optional field")

    @field_validator("evidence_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityRecommendationLink(BaseModel):
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


class SecurityCoverageRow(BaseModel):
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


class SecurityIntelligenceSection(BaseModel):
    """Customer Security Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = SECURITY_INTELLIGENCE_SECTION_ID
    section_version: str = SECURITY_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[SecurityOverviewFact, ...] = ()
    artifacts: tuple[SecurityArtifactRow, ...] = ()
    config_observations: tuple[SecurityConfigObservationRow, ...] = ()
    findings: tuple[SecurityFindingLink, ...] = ()
    recommendations: tuple[SecurityRecommendationLink, ...] = ()
    coverage_rows: tuple[SecurityCoverageRow, ...] = ()
    limitations: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    recommendation_count: int = Field(default=0, ge=0)
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
        return require_nonblank(str(value), label="security intelligence field")

    @field_validator(
        "overview_facts",
        "artifacts",
        "config_observations",
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
