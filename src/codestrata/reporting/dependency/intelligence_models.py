"""Dependency Intelligence presentation models (Epic 3 Slice 3.5).

HTML/reporting-layer only. Projects existing DependencyReportSection and
dependency-hygiene findings — does not invent CVE, license, freshness, or
supply-chain health claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

DEPENDENCY_INTELLIGENCE_SECTION_ID = "report.dependency_intelligence"
DEPENDENCY_INTELLIGENCE_SECTION_VERSION = "1.0.0"


class DependencyOverviewFact(BaseModel):
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


class DependencyEcosystemRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    manifest_count: int = Field(ge=0)
    declaration_count: int | None = Field(default=None, ge=0)
    parse_status: str | None = None
    version_availability: str | None = None
    note: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="ecosystem name")

    @field_validator("parse_status", "version_availability", "note", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="ecosystem optional field")


class DependencyManifestRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    ecosystem: str
    manifest_type: str
    parse_status: str | None = None
    limitations: tuple[str, ...] = ()
    finding_count: int | None = Field(default=None, ge=0)

    @field_validator("path", "ecosystem", "manifest_type", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="manifest field")

    @field_validator("parse_status", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="manifest parse status")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyFindingLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    title: str
    severity: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    path: str | None = None
    ecosystem: str | None = None
    rule_id: str

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

    @field_validator("path", "ecosystem", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="finding optional field")

    @field_validator("evidence_ids", "recommendation_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class DependencyRecommendationLink(BaseModel):
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


class DependencyCoverageRow(BaseModel):
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


class DependencyIntelligenceSection(BaseModel):
    """Customer Dependency Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = DEPENDENCY_INTELLIGENCE_SECTION_ID
    section_version: str = DEPENDENCY_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[DependencyOverviewFact, ...] = ()
    ecosystems: tuple[DependencyEcosystemRow, ...] = ()
    manifests: tuple[DependencyManifestRow, ...] = ()
    findings: tuple[DependencyFindingLink, ...] = ()
    recommendations: tuple[DependencyRecommendationLink, ...] = ()
    coverage_rows: tuple[DependencyCoverageRow, ...] = ()
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
        return require_nonblank(str(value), label="dependency intelligence field")

    @field_validator(
        "overview_facts",
        "ecosystems",
        "manifests",
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
