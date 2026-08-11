"""GraphReference — Community-resolvable symbolic graph pointer.

Does not embed full graph snapshots. Does not require Platform Knowledge Graph.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.traceability.enums import GraphKind, GraphReferenceKind
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.validators import (
    TraceabilityValidationError,
    normalize_limitations,
    sorted_unique_ids,
)


class GraphReference(BaseModel):
    """Lightweight reference into a repository or assessment graph view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_id: str
    graph_kind: GraphKind = GraphKind.SYMBOLIC
    reference_kind: GraphReferenceKind
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()
    path_node_ids: tuple[str, ...] = ()
    path_edge_ids: tuple[str, ...] = ()
    cycle_id: str | None = None
    relationship_type: str | None = None
    source_evidence_ids: tuple[str, ...] = ()
    primary_subject_id: str | None = None
    source_locations: tuple[EvidenceLocation, ...] = ()
    graph_version: str | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("graph_id", mode="before")
    @classmethod
    def normalize_graph_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph_id")

    @field_validator(
        "cycle_id",
        "relationship_type",
        "primary_subject_id",
        "graph_version",
        mode="before",
    )
    @classmethod
    def normalize_optional_str(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional graph field")

    @field_validator(
        "node_ids",
        "edge_ids",
        "path_node_ids",
        "path_edge_ids",
        "source_evidence_ids",
        mode="before",
    )
    @classmethod
    def normalize_id_lists(cls, value: object) -> tuple[str, ...]:
        return sorted_unique_ids(value, label="graph id")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("source_locations", mode="before")
    @classmethod
    def normalize_locations(cls, value: object) -> tuple[EvidenceLocation, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise TraceabilityValidationError("source_locations must be a sequence")
        items: list[EvidenceLocation] = []
        for item in value:
            if isinstance(item, EvidenceLocation):
                items.append(item)
            else:
                items.append(EvidenceLocation.model_validate(item))
        # Deterministic order by path then symbolic reference.
        return tuple(
            sorted(
                items,
                key=lambda loc: (
                    loc.path or "",
                    loc.symbolic_reference or "",
                    loc.location_kind.value,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_reference_shape(self) -> GraphReference:
        kind = self.reference_kind
        if kind is GraphReferenceKind.NODE and not self.node_ids:
            raise TraceabilityValidationError("node references require node_ids")
        if kind is GraphReferenceKind.EDGE and not self.edge_ids:
            raise TraceabilityValidationError("edge references require edge_ids")
        if kind is GraphReferenceKind.PATH and not self.path_node_ids:
            raise TraceabilityValidationError("path references require path_node_ids")
        if kind is GraphReferenceKind.CYCLE and self.cycle_id is None and not self.node_ids:
            raise TraceabilityValidationError(
                "cycle references require cycle_id and/or node_ids"
            )
        if kind is GraphReferenceKind.RELATIONSHIP and self.relationship_type is None:
            raise TraceabilityValidationError(
                "relationship references require relationship_type"
            )
        # Forbid accidental full-graph payload smuggling via unbounded collections.
        if (
            len(self.node_ids)
            + len(self.edge_ids)
            + len(self.path_node_ids)
            + len(self.path_edge_ids)
            > 256
        ):
            raise TraceabilityValidationError(
                "GraphReference collections exceed envelope bounds"
            )
        return self
