"""Admission of observed/declared structural edges at supported confidence/depth."""

from __future__ import annotations

from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.relationship_ids import RelationshipIdFactory
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralDepth,
    StructuralDropReason,
    StructuralEdgeObservation,
    StructuralView,
    admit_structural_edge,
)


def _obs(**overrides: object) -> StructuralEdgeObservation:
    payload: dict[str, object] = {
        "edge_type": "imports",
        "source_id": "repo:demo:module:a",
        "target_id": "repo:demo:module:b",
        "source_type": RepositoryNodeType.MODULE,
        "target_type": RepositoryNodeType.MODULE,
        "confidence": StructuralConfidence.HIGH,
        "depth": StructuralDepth.DIRECT,
        "view": StructuralView.RESOLVED,
        "unknown": False,
        "resolved": True,
        "cross_repository": False,
        "runtime_topology": False,
        "evidence_path": "src/a.py",
    }
    payload.update(overrides)
    return StructuralEdgeObservation.model_validate(payload)


def test_supported_structural_types_are_admitted() -> None:
    cases = (
        _obs(),
        _obs(edge_type="depends_on"),
        _obs(
            edge_type="implements",
            source_id="repo:demo:type:A",
            target_id="repo:demo:type:B",
            source_type=RepositoryNodeType.TYPE,
            target_type=RepositoryNodeType.TYPE,
        ),
        _obs(
            edge_type="exposes_API",
            source_id="repo:demo:module:a",
            target_id="repo:demo:type:Api",
            target_type=RepositoryNodeType.TYPE,
        ),
        _obs(
            edge_type="uses_dependency",
            source_id="repo:demo:file:src/a.py",
            target_id="repo:demo:dependency:pypi:_:requests",
            source_type=RepositoryNodeType.FILE,
            target_type=RepositoryNodeType.DEPENDENCY,
            confidence=StructuralConfidence.MEDIUM,
        ),
        _obs(
            edge_type="calls",
            source_id="repo:demo:callable:A#run()",
            target_id="repo:demo:callable:B#go()",
            source_type=RepositoryNodeType.CALLABLE,
            target_type=RepositoryNodeType.CALLABLE,
        ),
    )
    for observation in cases:
        assert admit_structural_edge(observation) is None


def test_cross_repo_runtime_low_confidence_and_unreliable_calls_dropped() -> None:
    assert (
        admit_structural_edge(_obs(cross_repository=True)) is StructuralDropReason.CROSS_REPOSITORY
    )
    assert (
        admit_structural_edge(_obs(runtime_topology=True)) is StructuralDropReason.RUNTIME_TOPOLOGY
    )
    assert (
        admit_structural_edge(_obs(confidence=StructuralConfidence.LOW))
        is StructuralDropReason.UNSUPPORTED_CONFIDENCE
    )
    assert (
        admit_structural_edge(_obs(depth=StructuralDepth.TRANSITIVE))
        is StructuralDropReason.UNSUPPORTED_DEPTH
    )
    assert (
        admit_structural_edge(
            _obs(
                edge_type="calls",
                source_id="repo:demo:callable:A#run()",
                target_id="repo:demo:callable:B#go()",
                source_type=RepositoryNodeType.CALLABLE,
                target_type=RepositoryNodeType.CALLABLE,
                unknown=True,
                resolved=False,
            )
        )
        is StructuralDropReason.UNRELIABLE_CALL
    )
    assert (
        admit_structural_edge(
            _obs(
                edge_type="calls",
                source_type=RepositoryNodeType.TYPE,
                target_type=RepositoryNodeType.CALLABLE,
            )
        )
        is StructuralDropReason.INVALID_ENDPOINTS
    )
    assert (
        admit_structural_edge(_obs(evidence_path="C:/abs/src/a.py"))
        is StructuralDropReason.ABSOLUTE_EVIDENCE_PATH
    )


def test_relationship_ids_are_stable_and_include_edge_type() -> None:
    factory = RelationshipIdFactory()
    first = factory.create(
        relationship_type="imports",
        source_node_id="repo:demo:module:a",
        target_node_id="repo:demo:module:b",
    )
    second = factory.create(
        relationship_type="imports",
        source_node_id="repo:demo:module:a",
        target_node_id="repo:demo:module:b",
    )
    depends = factory.create(
        relationship_type="depends_on",
        source_node_id="repo:demo:module:a",
        target_node_id="repo:demo:module:b",
    )
    assert first == second
    assert first == "rel:imports:repo:demo:module:a=>repo:demo:module:b"
    assert depends == "rel:depends_on:repo:demo:module:a=>repo:demo:module:b"
    assert "exposes_API" in factory.create(
        relationship_type="exposes_API",
        source_node_id="repo:demo:module:a",
        target_node_id="repo:demo:type:Api",
    )


def test_unknown_type_contains_and_unix_absolute_paths_are_dropped() -> None:
    unknown = StructuralDropReason.UNKNOWN_EDGE_TYPE
    assert admit_structural_edge(_obs(edge_type="invokes")) is unknown
    assert admit_structural_edge(_obs(edge_type="contains")) is unknown
    assert (
        admit_structural_edge(_obs(evidence_path="/abs/src/a.py"))
        is StructuralDropReason.ABSOLUTE_EVIDENCE_PATH
    )
    assert (
        admit_structural_edge(_obs(source_root="\\\\unc\\share"))
        is StructuralDropReason.ABSOLUTE_EVIDENCE_PATH
    )
    optional = StructuralEdgeObservation.model_validate(
        {**_obs().model_dump(), "evidence_path": None, "source_root": None}
    )
    assert optional.evidence_path is None
    assert admit_structural_edge(optional) is None
