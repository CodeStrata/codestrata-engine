"""Tests for GraphReference."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.traceability import (
    EvidenceLocation,
    GraphKind,
    GraphReference,
    GraphReferenceKind,
    to_stable_dict,
)


def test_node_reference() -> None:
    ref = GraphReference(
        graph_id="architecture-view",
        graph_kind=GraphKind.ARCHITECTURE_VIEW,
        reference_kind=GraphReferenceKind.NODE,
        node_ids=("unit:b", "unit:a"),
    )
    assert ref.node_ids == ("unit:a", "unit:b")


def test_edge_reference() -> None:
    ref = GraphReference(
        graph_id="architecture-view",
        reference_kind=GraphReferenceKind.EDGE,
        edge_ids=("a->b",),
    )
    assert ref.edge_ids == ("a->b",)


def test_path_reference() -> None:
    ref = GraphReference(
        graph_id="architecture-view",
        reference_kind=GraphReferenceKind.PATH,
        path_node_ids=("c", "a", "b"),
        path_edge_ids=("a->b", "b->c"),
    )
    assert ref.path_node_ids == ("a", "b", "c")


def test_cycle_reference() -> None:
    ref = GraphReference(
        graph_id="architecture-view",
        reference_kind=GraphReferenceKind.CYCLE,
        cycle_id="cycle:payments",
        node_ids=("unit:a",),
    )
    assert ref.cycle_id == "cycle:payments"


def test_symbolic_community_reference() -> None:
    ref = GraphReference(
        graph_id="symbolic:architecture",
        graph_kind=GraphKind.SYMBOLIC,
        reference_kind=GraphReferenceKind.RELATIONSHIP,
        relationship_type="depends_on",
        primary_subject_id="unit:payments",
        source_locations=(
            EvidenceLocation(path="b.py"),
            EvidenceLocation(path="a.py"),
        ),
    )
    assert [loc.path for loc in ref.source_locations] == ["a.py", "b.py"]


def test_requires_shape_fields() -> None:
    with pytest.raises(ValidationError, match="node_ids"):
        GraphReference(
            graph_id="g",
            reference_kind=GraphReferenceKind.NODE,
        )


def test_deterministic_serialization_no_payload_dump() -> None:
    ref = GraphReference(
        graph_id="g",
        reference_kind=GraphReferenceKind.NODE,
        node_ids=("n1",),
        limitations=("thin",),
    )
    payload = to_stable_dict(ref)
    assert "nodes" not in payload
    assert "edges" not in payload
    assert "graph" not in payload
    assert payload["node_ids"] == ["n1"]
