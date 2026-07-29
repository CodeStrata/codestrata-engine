"""Unmatched observation coverage for the Knowledge Pipeline."""

from __future__ import annotations

from codestrata.domain.engineering_knowledge import (
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeGraph,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeNodeType,
    FrameworkProperties,
    build_engineering_knowledge_metadata,
)
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    Provenance,
    ProvenanceSource,
)
from codestrata.domain.knowledge_binding import KnowledgeObservationKind
from codestrata.domain.repository_graph import (
    DependencyProperties,
    RepositoryGraph,
    RepositoryGraphNodeFactory,
    RepositoryProperties,
)
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.services.knowledge_pipeline import KnowledgePipeline


def _provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id="test",
        extractor_id="test",
        extractor_version="1.0.0",
    )


def test_unmatched_observations_are_deterministic_and_deduped() -> None:
    factory = RepositoryGraphNodeFactory("demo")
    nodes = [
        factory.repository(RepositoryProperties(name="demo")),
        factory.dependency(DependencyProperties(ecosystem="npm", name="left-pad", namespace=None)),
        factory.dependency(DependencyProperties(ecosystem="npm", name="react", namespace=None)),
    ]
    metadata = GraphMetadata(
        graph_id=GraphId("graph:repo:demo:1"),
        graph_type=GraphType.REPOSITORY,
        schema_version=REPOSITORY_GRAPH_SCHEMA_VERSION,
        generator_version="1.0.0",
        source_fingerprint="fp",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    repository_graph = RepositoryGraph(
        GraphSnapshot(
            metadata=metadata,
            nodes=tuple(sorted(nodes, key=lambda node: node.id.root)),
            relationships=(),
        )
    )
    knowledge_factory = EngineeringKnowledgeNodeFactory()
    knowledge_nodes = [
        knowledge_factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(canonical_key="react", name="React"),
            provenance=(_provenance(),),
        )
    ]
    knowledge = EngineeringKnowledgeGraph(
        GraphSnapshot(
            metadata=build_engineering_knowledge_metadata(
                EngineeringKnowledgeCatalogMetadata(
                    catalog_id="test",
                    catalog_version="1.0.0",
                    name="Test",
                )
            ),
            nodes=tuple(knowledge_nodes),
            relationships=(),
        )
    )
    result = KnowledgePipeline().bind(repository_graph, knowledge)
    assert any(binding.matched_key == "react" for binding in result.bindings)
    unmatched_keys = [item.candidate_key for item in result.unmatched_observations]
    assert "left-pad" in unmatched_keys
    assert unmatched_keys == sorted(unmatched_keys)
    assert all(
        item.observation_kind is KnowledgeObservationKind.DEPENDENCY_NAME
        for item in result.unmatched_observations
        if item.candidate_key == "left-pad"
    )
    assert all(item.evidence for item in result.unmatched_observations)
