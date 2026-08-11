"""Cloud Readiness Intelligence presentation models (Epic 3 Slice 3.7).

HTML/reporting-layer only. Projects existing CloudReportSection and
cloud-hygiene findings — does not invent cloud-ready, migration-ready,
production-ready, or live-deployment claims.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

CLOUD_INTELLIGENCE_SECTION_ID = "report.cloud_intelligence"
CLOUD_INTELLIGENCE_SECTION_VERSION = "1.0.0"

CloudSignalFamily = Literal[
    "platforms",
    "containers",
    "orchestration",
    "iac",
    "serverless",
    "managed_services",
    "deployment_pipelines",
    "other",
]


class CloudOverviewFact(BaseModel):
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


class CloudSignalRow(BaseModel):
    """Repository-observable cloud signal — never a readiness verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    family: CloudSignalFamily
    path: str | None = None
    evidence_ids: tuple[str, ...] = ()
    finding_id: str | None = None
    note: str | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("label", "family", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="signal row field")

    @field_validator("path", "finding_id", "note", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="signal optional field")

    @field_validator("evidence_ids", "limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class CloudSignalGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: str
    title: str
    signals: tuple[CloudSignalRow, ...] = ()

    @field_validator("group_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="signal group field")

    @field_validator("signals", mode="before")
    @classmethod
    def normalize_signals(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class CloudFindingLink(BaseModel):
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


class CloudRecommendationLink(BaseModel):
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


class CloudCoverageRow(BaseModel):
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


class CloudIntelligenceSection(BaseModel):
    """Customer Cloud Readiness Intelligence section payload (HTML view-model)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = CLOUD_INTELLIGENCE_SECTION_ID
    section_version: str = CLOUD_INTELLIGENCE_SECTION_VERSION
    status: str
    status_label: str
    status_summary: str
    confidence: str
    confidence_label: str
    overview_facts: tuple[CloudOverviewFact, ...] = ()
    signal_groups: tuple[CloudSignalGroup, ...] = ()
    findings: tuple[CloudFindingLink, ...] = ()
    recommendations: tuple[CloudRecommendationLink, ...] = ()
    coverage_rows: tuple[CloudCoverageRow, ...] = ()
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
        return require_nonblank(str(value), label="cloud intelligence field")

    @field_validator(
        "overview_facts",
        "signal_groups",
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
