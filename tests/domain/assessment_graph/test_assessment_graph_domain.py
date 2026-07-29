"""Domain tests for Assessment Graph identities and schema."""

from __future__ import annotations

import pytest

from codestrata.domain.assessment_graph import (
    AssessmentBindingProperties,
    AssessmentGraph,
    AssessmentGraphSchemaError,
    AssessmentNodeFactory,
    AssessmentNodeType,
    AssessmentRelationshipFactory,
    AssessmentRelationshipType,
    KnowledgeConceptReferenceProperties,
    RepositoryEntityReferenceProperties,
    build_assessment_graph_id,
    build_assessment_graph_metadata,
    build_assessment_source_fingerprint,
)
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphSnapshot,
    GraphStatus,
    GraphType,
)
from codestrata.domain.knowledge_binding import (
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
)


def test_fingerprint_and_graph_id_are_deterministic() -> None:
    first = build_assessment_source_fingerprint(
        repository_graph_id="graph:repo:a",
        repository_source_fingerprint="fp-a",
        knowledge_graph_id="graph:ekg:b",
        knowledge_source_fingerprint="fp-b",
        binding_ids=["kb:2", "kb:1"],
    )
    second = build_assessment_source_fingerprint(
        repository_graph_id="graph:repo:a",
        repository_source_fingerprint="fp-a",
        knowledge_graph_id="graph:ekg:b",
        knowledge_source_fingerprint="fp-b",
        binding_ids=["kb:1", "kb:2"],
    )
    assert first == second
    assert first.startswith("sha256:")
    assert build_assessment_graph_id(source_fingerprint=first) == GraphId(
        f"graph:assessment:{first.removeprefix('sha256:')}"
    )


def test_fingerprint_changes_when_bindings_change() -> None:
    base = build_assessment_source_fingerprint(
        repository_graph_id="graph:repo:a",
        repository_source_fingerprint="fp-a",
        knowledge_graph_id="graph:ekg:b",
        knowledge_source_fingerprint="fp-b",
        binding_ids=["kb:1"],
    )
    changed = build_assessment_source_fingerprint(
        repository_graph_id="graph:repo:a",
        repository_source_fingerprint="fp-a",
        knowledge_graph_id="graph:ekg:b",
        knowledge_source_fingerprint="fp-b",
        binding_ids=["kb:1", "kb:2"],
    )
    assert base != changed


def test_reference_nodes_and_binding_relationship_round_trip() -> None:
    nodes = AssessmentNodeFactory()
    relationships = AssessmentRelationshipFactory()
    repo_ref = nodes.repository_entity_reference(
        RepositoryEntityReferenceProperties(
            source_repository_graph_id="graph:repo:demo:1",
            source_repository_node_id="repo:demo:dependency:npm:_:react",
            repository_node_type="dependency",
        )
    )
    knowledge_ref = nodes.knowledge_concept_reference(
        KnowledgeConceptReferenceProperties(
            source_knowledge_graph_id="graph:ekg:codestrata-core:1.0.0",
            source_knowledge_node_id="ekg:framework:react",
            knowledge_node_type="framework",
            canonical_key="react",
        )
    )
    relationship = relationships.binds_to_knowledge(
        source_node_id=repo_ref.id,
        target_node_id=knowledge_ref.id,
        properties=AssessmentBindingProperties(
            binding_id="kb:exact_canonical_key:x",
            binding_type=KnowledgeBindingType.USES_CONCEPT,
            confidence=1.0,
            matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
            matched_key="react",
            observation_kind=KnowledgeObservationKind.DEPENDENCY_NAME,
        ),
    )
    assert repo_ref.node_type == AssessmentNodeType.REPOSITORY_ENTITY_REFERENCE
    assert knowledge_ref.node_type == AssessmentNodeType.KNOWLEDGE_CONCEPT_REFERENCE
    assert relationship.relationship_type == AssessmentRelationshipType.BINDS_TO_KNOWLEDGE

    metadata = build_assessment_graph_metadata(
        repository_graph_id="graph:repo:demo:1",
        repository_source_fingerprint="fp-repo",
        knowledge_graph_id="graph:ekg:codestrata-core:1.0.0",
        knowledge_source_fingerprint="fp-ekg",
        binding_ids=[relationship.properties["binding_id"]],  # type: ignore[index]
    )
    graph = AssessmentGraph(
        GraphSnapshot(
            metadata=metadata,
            nodes=(repo_ref, knowledge_ref),
            relationships=(relationship,),
        )
    )
    assert graph.metadata.graph_type is GraphType.ASSESSMENT
    assert len(graph.nodes) == 2
    assert len(graph.relationships) == 1


def test_schema_rejects_wrong_graph_type() -> None:
    metadata = GraphMetadata(
        graph_id=GraphId("graph:assessment:bad"),
        graph_type=GraphType.REPOSITORY,
        schema_version="1.0.0",
        generator_version="1.0.0",
        source_fingerprint="x",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    with pytest.raises(AssessmentGraphSchemaError, match="graph_type"):
        AssessmentGraph(GraphSnapshot(metadata=metadata, nodes=(), relationships=()))
