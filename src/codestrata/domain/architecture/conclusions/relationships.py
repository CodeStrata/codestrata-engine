"""Finding relationship and cluster models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.architecture.conclusions.enums import FindingRelationshipType
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import RuleConfidence


class FindingRelationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_type: FindingRelationshipType
    source_finding_id: str
    target_finding_id: str
    reason_code: str
    supporting_subject: str | None = None
    confidence: RuleConfidence = RuleConfidence.MEDIUM
    provenance: str = "architecture_conclusion_relationship_catalog"

    @field_validator(
        "source_finding_id",
        "target_finding_id",
        "reason_code",
        "provenance",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="relationship field")

    @field_validator("supporting_subject", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="supporting_subject")


class FindingCluster(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: str
    category: str
    finding_ids: tuple[str, ...] = ()
    affected_scope: tuple[str, ...] = ()
    relationship_reason_codes: tuple[str, ...] = ()
    primary_finding_id: str | None = None

    @field_validator("cluster_id", "category", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="cluster field")

    @field_validator(
        "finding_ids",
        "affected_scope",
        "relationship_reason_codes",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))

    @field_validator("primary_finding_id", mode="before")
    @classmethod
    def normalize_primary(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="primary_finding_id")


class SeveritySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    highest_severity: str
    severity_counts: dict[str, int] = Field(default_factory=dict)
    primary_finding_severity: str | None = None
    source_finding_count: int = Field(default=0, ge=0)

    @field_validator("highest_severity", mode="before")
    @classmethod
    def normalize_highest(cls, value: object) -> str:
        return require_nonblank(str(value), label="highest_severity").lower()
