"""Unit tests for the shared storage-independent graph domain kernel."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.graph import (
    EvidenceReference,
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    NodeId,
    Provenance,
    ProvenanceSource,
)


def _provenance(**overrides: object) -> Provenance:
    payload: dict[str, object] = {
        "source_type": ProvenanceSource.DETERMINISTIC_ANALYZER,
        "source_id": "analyzer:architecture",
        "extractor_id": "architecture-v1",
        "extractor_version": "1.0.0",
        "confidence": 0.9,
    }
    payload.update(overrides)
    return Provenance.model_validate(payload)


def _evidence(**overrides: object) -> EvidenceReference:
    payload: dict[str, object] = {
        "evidence_type": "file_location",
        "source_id": "file:src/App.java",
        "path": "src/App.java",
        "start_line": 10,
        "end_line": 12,
        "content_hash": "abc123",
        "excerpt": "class App {}",
    }
    payload.update(overrides)
    return EvidenceReference.model_validate(payload)


def _node(node_id: str = "node:app", **overrides: object) -> GraphNode:
    payload: dict[str, object] = {
        "id": node_id,
        "node_type": "file",
        "schema_version": "1.0.0",
        "properties": {"path": "src/App.java"},
        "provenance": [_provenance()],
        "evidence": [_evidence()],
    }
    payload.update(overrides)
    return GraphNode.model_validate(payload)


def _relationship(
    *,
    relationship_id: str = "rel:1",
    source: str = "node:app",
    target: str = "node:util",
    **overrides: object,
) -> GraphRelationship:
    payload: dict[str, object] = {
        "id": relationship_id,
        "relationship_type": "depends_on",
        "source_node_id": source,
        "target_node_id": target,
        "properties": {"weight": 1},
        "provenance": [_provenance()],
        "evidence": [],
    }
    payload.update(overrides)
    return GraphRelationship.model_validate(payload)


def _metadata(**overrides: object) -> GraphMetadata:
    payload: dict[str, object] = {
        "graph_id": "graph:repo:sample",
        "graph_type": GraphType.REPOSITORY,
        "schema_version": "1.0.0",
        "generator_version": "0.1.0",
        "source_fingerprint": "fingerprint:abc",
        "generation_mode": GraphGenerationMode.FULL,
        "status": GraphStatus.VALID,
    }
    payload.update(overrides)
    return GraphMetadata.model_validate(payload)


def test_enum_values() -> None:
    assert GraphType.REPOSITORY == "repository"
    assert GraphType.ENGINEERING_KNOWLEDGE == "engineering_knowledge"
    assert GraphType.ASSESSMENT == "assessment"
    assert GraphStatus.BUILDING == "building"
    assert GraphStatus.VALID == "valid"
    assert GraphStatus.INVALID == "invalid"
    assert GraphStatus.SUPERSEDED == "superseded"
    assert GraphGenerationMode.FULL == "full"
    assert GraphGenerationMode.INCREMENTAL == "incremental"
    assert GraphGenerationMode.REUSED == "reused"
    assert GraphGenerationMode.MIGRATED == "migrated"
    assert ProvenanceSource.REPOSITORY_FILE == "repository_file"
    assert ProvenanceSource.AI_AGENT == "ai_agent"
    assert ProvenanceSource.MIGRATION == "migration"


def test_graph_id_and_node_id_normalize_and_reject_blank() -> None:
    assert GraphId("  graph:1  ").root == "graph:1"
    assert str(GraphId("graph:1")) == "graph:1"
    assert NodeId("  node:1  ").root == "node:1"
    assert str(NodeId("node:1")) == "node:1"

    with pytest.raises(ValidationError, match="must not be blank"):
        GraphId("   ")
    with pytest.raises(ValidationError, match="must not be blank"):
        NodeId("")
    with pytest.raises(ValidationError, match="must be a string"):
        GraphId.model_validate(123)


def test_provenance_validation() -> None:
    item = _provenance(confidence=0.0)
    assert item.confidence == 0.0
    assert _provenance(confidence=1.0).confidence == 1.0
    assert _provenance(extractor_id=None, extractor_version=None).extractor_id is None

    with pytest.raises(ValidationError, match="must not be blank"):
        _provenance(source_id="  ")
    with pytest.raises(ValidationError, match="must not be blank"):
        _provenance(extractor_id="  ")
    with pytest.raises(ValidationError):
        _provenance(confidence=1.1)
    with pytest.raises(ValidationError):
        _provenance(confidence=-0.1)


def test_evidence_reference_line_ranges_and_blanks() -> None:
    assert _evidence(start_line=1, end_line=1).end_line == 1
    assert _evidence(symbol_id="node:symbol").symbol_id == NodeId("node:symbol")

    with pytest.raises(ValidationError, match="must not be blank"):
        _evidence(evidence_type=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        _evidence(path=" ")
    with pytest.raises(ValidationError, match="end_line cannot be earlier"):
        _evidence(start_line=5, end_line=4)
    with pytest.raises(ValidationError):
        _evidence(start_line=0)


def test_graph_node_and_relationship_property_keys() -> None:
    node = _node()
    assert node.id == NodeId("node:app")
    assert isinstance(node.provenance, tuple)
    assert isinstance(node.evidence, tuple)

    with pytest.raises(ValidationError, match="must not be blank"):
        _node(node_type=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        _node(properties={" ": 1})
    with pytest.raises(ValidationError, match="must not be blank"):
        _relationship(id=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        _relationship(properties={"": True})


def test_self_referential_relationship_allowed() -> None:
    rel = _relationship(source="node:app", target="node:app")
    assert rel.source_node_id == rel.target_node_id


def test_graph_snapshot_rejects_duplicate_and_missing_ids() -> None:
    metadata = _metadata()
    with pytest.raises(ValidationError, match="node IDs must be unique"):
        GraphSnapshot(
            metadata=metadata,
            nodes=(_node("node:a"), _node("node:a")),
            relationships=(),
        )
    with pytest.raises(ValidationError, match="relationship IDs must be unique"):
        GraphSnapshot(
            metadata=metadata,
            nodes=(_node("node:a"), _node("node:b")),
            relationships=(
                _relationship(relationship_id="rel:1", source="node:a", target="node:b"),
                _relationship(relationship_id="rel:1", source="node:b", target="node:a"),
            ),
        )
    with pytest.raises(ValidationError, match="source_node_id"):
        GraphSnapshot(
            metadata=metadata,
            nodes=(_node("node:a"),),
            relationships=(_relationship(source="node:missing", target="node:a"),),
        )
    with pytest.raises(ValidationError, match="target_node_id"):
        GraphSnapshot(
            metadata=metadata,
            nodes=(_node("node:a"),),
            relationships=(_relationship(source="node:a", target="node:missing"),),
        )


def test_valid_connected_graph_snapshot_and_immutability() -> None:
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(_node("node:a"), _node("node:b")),
        relationships=(_relationship(source="node:a", target="node:b"),),
    )
    assert snapshot.metadata.graph_type is GraphType.REPOSITORY
    assert len(snapshot.nodes) == 2
    assert snapshot.relationships[0].relationship_type == "depends_on"

    with pytest.raises(ValidationError):
        snapshot.metadata.status = GraphStatus.INVALID  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.nodes[0].properties["x"] = 1  # type: ignore[index]
    with pytest.raises(ValidationError):
        snapshot.nodes += ()  # type: ignore[misc]


def test_serialization_and_reconstruction() -> None:
    original = GraphSnapshot(
        metadata=_metadata(graph_type=GraphType.ASSESSMENT, status=GraphStatus.BUILDING),
        nodes=(
            _node("node:a", node_type="finding"),
            _node("node:b", node_type="recommendation"),
        ),
        relationships=(
            _relationship(
                relationship_id="rel:grounds",
                source="node:b",
                target="node:a",
                relationship_type="grounded_in",
            ),
        ),
    )
    payload = original.model_dump(mode="json")
    assert payload["metadata"]["graph_id"] == "graph:repo:sample"
    assert payload["nodes"][0]["id"] == "node:a"
    assert payload["relationships"][0]["source_node_id"] == "node:b"

    restored = GraphSnapshot.model_validate(payload)
    assert restored == original
    assert restored.metadata.graph_id == GraphId("graph:repo:sample")
    assert restored.nodes[0].id == NodeId("node:a")


def test_metadata_rejects_blank_required_strings() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        _metadata(schema_version=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        _metadata(source_fingerprint="")
