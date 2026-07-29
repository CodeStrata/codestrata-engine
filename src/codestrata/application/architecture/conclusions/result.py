"""Architecture conclusion service result and telemetry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.architecture.conclusions.enums import ConclusionPolicyStatus
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ArchitectureSummary,
    ConsolidatedRecommendation,
)
from codestrata.domain.architecture.conclusions.relationships import (
    FindingCluster,
    FindingRelationship,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class ConclusionPolicyExecutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    status: ConclusionPolicyStatus
    message: str | None = None
    conclusion_count: int = Field(default=0, ge=0)

    @field_validator("policy_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="policy_id")


class ArchitectureConclusionTelemetry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    relationship_count: int = Field(default=0, ge=0)
    cluster_count: int = Field(default=0, ge=0)
    conclusion_count: int = Field(default=0, ge=0)
    recommendation_group_count: int = Field(default=0, ge=0)
    policy_records: tuple[ConclusionPolicyExecutionRecord, ...] = ()
    duration_ms: int = Field(default=0, ge=0)
    configuration_fingerprint: str = ""
    graph_fingerprint: str = ""
    enterprise_context_used: bool = False
    failure_count: int = Field(default=0, ge=0)

    @field_validator("policy_records", mode="before")
    @classmethod
    def normalize_records(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class ArchitectureConclusionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    relationships: tuple[FindingRelationship, ...] = ()
    clusters: tuple[FindingCluster, ...] = ()
    conclusions: tuple[ArchitectureConclusion, ...] = ()
    recommendation_groups: tuple[ConsolidatedRecommendation, ...] = ()
    summary: ArchitectureSummary | None = None
    telemetry: ArchitectureConclusionTelemetry = Field(
        default_factory=ArchitectureConclusionTelemetry
    )
    diagnostics: tuple[str, ...] = ()

    @field_validator(
        "relationships",
        "clusters",
        "conclusions",
        "recommendation_groups",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)
