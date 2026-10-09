"""Presentation-only view models for the R2 baseline report.

These copy canonical records. They do not compute health, rank, deltas,
lifecycle, movement, or graph topology.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class ArchitectureMapNodeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    node_type: str
    label: str
    path: str | None = None
    parent_id: str | None = None
    x: float = 0.0
    y: float = 0.0
    displayed: bool = False
    hotspot_record_ids: tuple[str, ...] = ()
    ownership_subject_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @field_validator("node_id", "node_type", "label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="architecture map node field")

    @field_validator(
        "hotspot_record_ids",
        "ownership_subject_ids",
        "finding_ids",
        "evidence_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class ArchitectureMapEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str
    relationship_type: str
    source_node_id: str
    target_node_id: str
    displayed: bool = False

    @field_validator(
        "edge_id", "relationship_type", "source_node_id", "target_node_id", mode="before"
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="architecture map edge field")


class ArchitectureMapView(BaseModel):
    """Canonical-graph projection for the Architecture Map."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    unavailable_reason: str | None = None
    graph_id: str | None = None
    source_fingerprint: str | None = None
    canonical_node_count: int = Field(default=0, ge=0)
    canonical_edge_count: int = Field(default=0, ge=0)
    displayed_node_count: int = Field(default=0, ge=0)
    displayed_edge_count: int = Field(default=0, ge=0)
    display_node_limit: int = Field(default=80, ge=1)
    display_limit_disclosed: bool = False
    grouping: str = "unavailable"
    downloadable_artifact: str = "graphs/repository-graph.json"
    nodes: tuple[ArchitectureMapNodeView, ...] = ()
    edges: tuple[ArchitectureMapEdgeView, ...] = ()

    @field_validator("nodes", "edges", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class HotspotContributorView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    role: str
    value: str | None = None
    measurement_id: str | None = None
    coverage_reason: str | None = None
    evidence_ids: tuple[str, ...] = ()

    @field_validator("name", "role", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot contributor field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class EngineeringHotspotView(BaseModel):
    """Copy of a sealed M22 record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    subject_id: str
    list_kind: str
    ranking_value: str | None = None
    history_profile_id: str | None = None
    history_window: str | None = None
    priority_explanation: str | None = None
    contributors: tuple[HotspotContributorView, ...] = ()
    active_finding_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @field_validator("record_id", "subject_id", "list_kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="hotspot view field")

    @field_validator("contributors", "active_finding_ids", "evidence_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class HotspotSectionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    unavailable_reason: str | None = None
    items: tuple[EngineeringHotspotView, ...] = ()

    @field_validator("items", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class OwnershipConcentrationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: str
    subject_id: str
    numerator: int | None = None
    denominator: int | None = None
    serialized_ratio: str | None = None
    history_profile_id: str | None = None
    history_window: str | None = None
    status: str | None = None
    notes: str | None = None
    evidence_ids: tuple[str, ...] = ()

    @field_validator("scope", "subject_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="ownership view field")

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class OwnershipSectionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    unavailable_reason: str | None = None
    items: tuple[OwnershipConcentrationView, ...] = ()

    @field_validator("items", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class CochangePairView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: str
    left: str
    right: str
    support: int | None = None
    union: int | None = None
    jaccard: str | None = None
    supported_relation: bool | None = None
    qualified_incomplete_window: bool = False
    unavailable_reason: str | None = None

    @field_validator("scope", "left", "right", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="co-change view field")


class CochangeSectionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    unavailable_reason: str | None = None
    items: tuple[CochangePairView, ...] = ()

    @field_validator("items", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class CoverageTrustRowView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    evidence_id: str | None = None
    status: str | None = None

    @field_validator("label", "value", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="coverage trust row")


class CoverageTrustView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[CoverageTrustRowView, ...] = ()
    capability_rows: tuple[dict[str, Any], ...] = ()
    material_limitations: tuple[str, ...] = ()
    comparison_state: str = "No comparison or trend was requested for this baseline assessment."
    identity_note: str = ""

    @field_validator("rows", "capability_rows", "material_limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class AttentionOutcomeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    head: str
    title: str
    display_label: str
    findings_count: int = Field(default=0, ge=0)
    anchor: str

    @field_validator("head", "title", "display_label", "anchor", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="attention outcome field")


class AttentionSummaryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str
    outcomes_needing_attention: tuple[AttentionOutcomeView, ...] = ()
    unavailable_evidence: tuple[AttentionOutcomeView, ...] = ()
    top_priority_action_ids: tuple[str, ...] = ()
    comparison_state: str = "No comparison or trend was requested for this baseline assessment."

    @field_validator("headline", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="attention headline")

    @field_validator(
        "outcomes_needing_attention",
        "unavailable_evidence",
        "top_priority_action_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
