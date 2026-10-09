"""Neutral fact, evidence and graph records for the E01.2 envelope body."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.contracts.enums import ExtractionStatus, SubjectKind
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class EvidenceRecord(BaseModel):
    """Durable evidence identity. Paths alone are not identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.evidence.v1"
    schema_version: str = "1.0.0"
    evidence_id: str
    source_kind: str
    working_state_digest: str
    source_revision: str
    extractor_version: str
    relative_path: str | None = None
    span: str | None = None
    graph_record_id: str | None = None
    feed_record_id: str | None = None
    commit_id: str | None = None
    limitation: str | None = None

    @field_validator(
        "evidence_id",
        "source_kind",
        "working_state_digest",
        "source_revision",
        "extractor_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence field")


class FactRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.fact.v1"
    schema_version: str = "1.0.0"
    fact_id: str
    measurement_id: str | None = None
    subject_kind: SubjectKind
    subject_id: str
    source_kind: str
    value: str | int | float | bool | None = None
    unit: str
    evidence_ids: tuple[str, ...]
    extraction_status: ExtractionStatus
    direction: str = "neutral"

    @field_validator("fact_id", "subject_id", "source_kind", "unit", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="fact field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(require_nonblank(str(item), label="evidence_id") for item in as_tuple(value))


class GraphNodeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    kind: str
    subject_id: str

    @field_validator("node_id", "kind", "subject_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph node field")


class GraphEdgeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    source_id: str
    target_id: str
    kind: str

    @field_validator("edge_id", "source_id", "target_id", "kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph edge field")


class GraphRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.graph.v1"
    schema_version: str = "1.0.0"
    graph_id: str
    nodes: tuple[GraphNodeRecord, ...] = ()
    edges: tuple[GraphEdgeRecord, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("graph_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph_id")

    @field_validator("nodes", "edges", "limitations", mode="before")
    @classmethod
    def normalize_seq(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class FindingRecord(BaseModel):
    """Canonical finding projection. Tenant/job identity is forbidden."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    subject_id: str
    result: str
    default_severity: str
    effective_severity: str
    confidence: str
    evidence_ids: tuple[str, ...]
    occurrence_key: str | None = None
    override_provenance: str | None = None

    @field_validator(
        "finding_id",
        "rule_id",
        "subject_id",
        "result",
        "default_severity",
        "effective_severity",
        "confidence",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        items = [require_nonblank(str(item), label="evidence_id") for item in as_tuple(value)]
        if not items:
            raise ValueError("findings require evidence references")
        return tuple(sorted(set(items)))
