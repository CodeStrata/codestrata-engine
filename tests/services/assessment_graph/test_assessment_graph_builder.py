"""Service tests for Assessment Graph construction."""

from __future__ import annotations

import copy

import pytest

from codestrata.domain.assessment_graph import AssessmentNodeType, AssessmentRelationshipType
from codestrata.domain.engineering_knowledge import (
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeGraph,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeNodeType,
    FrameworkProperties,
    LanguageProperties,
    build_engineering_knowledge_metadata,
)
from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphNode,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    Provenance,
    ProvenanceSource,
)
from codestrata.domain.knowledge_binding import (
    KnowledgeBinding,
    KnowledgeBindingResult,
    KnowledgeMatchingStrategy,
)
from codestrata.domain.repository_graph import (
    DependencyProperties,
    FileProperties,
    RepositoryFileKind,
    RepositoryGraph,
    RepositoryGraphNodeFactory,
    RepositoryProperties,
)
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.services.assessment_graph import (
    AssessmentGraphBuilder,
    AssessmentGraphBuildError,
    build_assessment_graph,
)
from codestrata.services.engineering_knowledge import load_builtin_engineering_knowledge_catalog
from codestrata.services.knowledge_pipeline import KnowledgePipeline


def _provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id="test:ag",
        extractor_id="test",
        extractor_version="1.0.0",
    )


def _repository_graph(*nodes: GraphNode, fingerprint: str = "test:demo") -> RepositoryGraph:
    metadata = GraphMetadata(
        graph_id=GraphId("graph:repo:demo:1"),
        graph_type=GraphType.REPOSITORY,
        schema_version=REPOSITORY_GRAPH_SCHEMA_VERSION,
        generator_version="1.0.0",
        source_fingerprint=fingerprint,
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )
    ordered = tuple(sorted(nodes, key=lambda node: node.id.root))
    return RepositoryGraph(GraphSnapshot(metadata=metadata, nodes=ordered, relationships=()))


def _sample_knowledge() -> EngineeringKnowledgeGraph:
    factory = EngineeringKnowledgeNodeFactory()
    nodes = [
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(canonical_key="react", name="React"),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.LANGUAGE,
            properties=LanguageProperties(canonical_key="javascript", name="JavaScript"),
            provenance=(_provenance(),),
        ),
    ]
    metadata = build_engineering_knowledge_metadata(
        EngineeringKnowledgeCatalogMetadata(
            catalog_id="test-knowledge",
            catalog_version="1.0.0",
            name="Test Knowledge",
        )
    )
    return EngineeringKnowledgeGraph(
        GraphSnapshot(
            metadata=metadata,
            nodes=tuple(sorted(nodes, key=lambda node: node.id.root)),
            relationships=(),
        )
    )


def _js_repository(*, shuffle: bool = False) -> RepositoryGraph:
    factory = RepositoryGraphNodeFactory("demo")
    repo = factory.repository(RepositoryProperties(name="demo"))
    react = factory.dependency(DependencyProperties(ecosystem="npm", name="react", namespace=None))
    js_file = factory.file(
        FileProperties(
            path="src/index.js",
            file_kind=RepositoryFileKind.SOURCE,
            language="javascript",
        )
    )
    nodes: list[GraphNode] = [repo, react, js_file]
    if shuffle:
        nodes = [js_file, repo, react]
    return _repository_graph(*nodes)


def _binding_result(
    repository_graph: RepositoryGraph,
    knowledge_graph: EngineeringKnowledgeGraph,
    *,
    bindings: tuple[KnowledgeBinding, ...] | None = None,
) -> KnowledgeBindingResult:
    if bindings is None:
        return KnowledgePipeline().bind(repository_graph, knowledge_graph)
    return KnowledgeBindingResult(
        repository_graph_id=repository_graph.metadata.graph_id,
        repository_source_fingerprint=repository_graph.metadata.source_fingerprint,
        knowledge_graph_id=knowledge_graph.metadata.graph_id,
        knowledge_source_fingerprint=knowledge_graph.metadata.source_fingerprint,
        matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
        bindings=bindings,
    )


def test_empty_binding_result_creates_empty_assessment_graph() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = _binding_result(repo, knowledge, bindings=())
    graph = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    assert graph.metadata.graph_type is GraphType.ASSESSMENT
    assert graph.nodes == ()
    assert graph.relationships == ()
    assert graph.metadata.source_fingerprint.startswith("sha256:")


def test_one_binding_creates_reference_nodes_and_relationship() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    react_bindings = [item for item in result.bindings if item.matched_key == "react"]
    assert len(react_bindings) == 1
    single = _binding_result(repo, knowledge, bindings=(react_bindings[0],))
    graph = AssessmentGraphBuilder().build(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=single,
    )
    assert len(graph.nodes) == 2
    assert len(graph.relationships) == 1
    types = {node.node_type for node in graph.nodes}
    assert types == {
        AssessmentNodeType.REPOSITORY_ENTITY_REFERENCE,
        AssessmentNodeType.KNOWLEDGE_CONCEPT_REFERENCE,
    }
    relationship = graph.relationships[0]
    assert relationship.relationship_type == AssessmentRelationshipType.BINDS_TO_KNOWLEDGE
    assert relationship.properties["binding_id"] == react_bindings[0].binding_id
    assert relationship.properties["matched_key"] == "react"


def test_multiple_bindings_reuse_reference_nodes() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    assert len(result.bindings) >= 2
    graph = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    assert len(graph.relationships) == len(result.bindings)
    # Two distinct repository observations + two knowledge concepts (or fewer if shared).
    assert len(graph.nodes) <= len(result.bindings) * 2
    assert len(graph.nodes) >= 3


def test_duplicate_bindings_do_not_duplicate_graph_elements() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    binding = result.bindings[0]
    duplicated = _binding_result(repo, knowledge, bindings=(binding, binding))
    graph = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=duplicated,
    )
    assert len(graph.relationships) == 1
    assert len(graph.nodes) == 2


def test_unknown_repository_node_fails() -> None:
    from codestrata.domain.graph import NodeId

    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    binding = result.bindings[0].model_copy(
        update={"repository_node_id": NodeId("repo:missing:dependency:npm:_:x")}
    )
    bad = _binding_result(repo, knowledge, bindings=(binding,))
    with pytest.raises(AssessmentGraphBuildError, match="Unknown repository node"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_unknown_knowledge_node_fails() -> None:
    from codestrata.domain.graph import NodeId

    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    binding = result.bindings[0].model_copy(
        update={"knowledge_node_id": NodeId("ekg:framework:missing")}
    )
    bad = _binding_result(repo, knowledge, bindings=(binding,))
    with pytest.raises(AssessmentGraphBuildError, match="Unknown knowledge node"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_repository_graph_id_mismatch_fails() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    bad = result.model_copy(update={"repository_graph_id": GraphId("graph:repo:other")})
    with pytest.raises(AssessmentGraphBuildError, match="repository_graph_id"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_repository_fingerprint_mismatch_fails() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    bad = result.model_copy(update={"repository_source_fingerprint": "other-fp"})
    with pytest.raises(AssessmentGraphBuildError, match="repository_source_fingerprint"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_ekg_id_mismatch_fails() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    bad = result.model_copy(update={"knowledge_graph_id": GraphId("graph:ekg:other:1")})
    with pytest.raises(AssessmentGraphBuildError, match="knowledge_graph_id"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_ekg_fingerprint_mismatch_fails() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    bad = result.model_copy(update={"knowledge_source_fingerprint": "other-ekg-fp"})
    with pytest.raises(AssessmentGraphBuildError, match="knowledge_source_fingerprint"):
        build_assessment_graph(
            repository_graph=repo,
            knowledge_graph=knowledge,
            binding_result=bad,
        )


def test_input_ordering_does_not_affect_output() -> None:
    knowledge = _sample_knowledge()
    left = build_assessment_graph(
        repository_graph=_js_repository(shuffle=False),
        knowledge_graph=knowledge,
        binding_result=KnowledgePipeline().bind(_js_repository(shuffle=False), knowledge),
    )
    right = build_assessment_graph(
        repository_graph=_js_repository(shuffle=True),
        knowledge_graph=knowledge,
        binding_result=KnowledgePipeline().bind(_js_repository(shuffle=True), knowledge),
    )
    assert left.snapshot.model_dump(mode="json") == right.snapshot.model_dump(mode="json")


def test_repeated_construction_is_identical() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    first = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    second = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    assert first.snapshot.model_dump(mode="json") == second.snapshot.model_dump(mode="json")


def test_source_graphs_and_binding_result_remain_unchanged() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    before_repo = copy.deepcopy(repo.snapshot.model_dump(mode="json"))
    before_knowledge = copy.deepcopy(knowledge.snapshot.model_dump(mode="json"))
    before_result = copy.deepcopy(result.model_dump(mode="json"))
    build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    assert repo.snapshot.model_dump(mode="json") == before_repo
    assert knowledge.snapshot.model_dump(mode="json") == before_knowledge
    assert result.model_dump(mode="json") == before_result


def test_changing_binding_changes_assessment_fingerprint() -> None:
    repo = _js_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    full = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    subset = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=_binding_result(repo, knowledge, bindings=(result.bindings[0],)),
    )
    assert full.metadata.source_fingerprint != subset.metadata.source_fingerprint
    assert full.metadata.graph_id != subset.metadata.graph_id


def test_builtin_catalog_and_javascript_repository_produce_assessment_graph() -> None:
    factory = RepositoryGraphNodeFactory("sample-js")
    repo = _repository_graph(
        factory.repository(RepositoryProperties(name="sample-js")),
        factory.dependency(DependencyProperties(ecosystem="npm", name="react", namespace=None)),
        factory.file(
            FileProperties(
                path="src/index.js",
                file_kind=RepositoryFileKind.SOURCE,
                language="javascript",
            )
        ),
        fingerprint="js-fixture",
    )
    knowledge = load_builtin_engineering_knowledge_catalog()
    result = KnowledgePipeline().bind(repo, knowledge)
    assert result.bindings
    graph = build_assessment_graph(
        repository_graph=repo,
        knowledge_graph=knowledge,
        binding_result=result,
    )
    assert graph.relationships
    assert all(
        rel.relationship_type == AssessmentRelationshipType.BINDS_TO_KNOWLEDGE
        for rel in graph.relationships
    )
    keys = {rel.properties.get("matched_key") for rel in graph.relationships}
    assert "react" in keys or "javascript" in keys
