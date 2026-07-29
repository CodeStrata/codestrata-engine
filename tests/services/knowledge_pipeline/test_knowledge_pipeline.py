"""Tests for the Knowledge Pipeline exact-match service."""

from __future__ import annotations

import pytest

from codestrata.domain.engineering_knowledge import (
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeGraph,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeProperties,
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
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
)
from codestrata.domain.repository_graph import (
    DependencyProperties,
    FileProperties,
    ModuleProperties,
    RepositoryFileKind,
    RepositoryGraph,
    RepositoryGraphNodeFactory,
    RepositoryProperties,
)
from codestrata.domain.repository_graph.factories import REPOSITORY_GRAPH_SCHEMA_VERSION
from codestrata.services.engineering_knowledge import load_builtin_engineering_knowledge_catalog
from codestrata.services.knowledge_pipeline import KnowledgePipeline, bind_repository_knowledge


def _provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id="test:rg",
        extractor_id="test",
        extractor_version="1.0.0",
    )


def _repository_graph(*nodes: GraphNode) -> RepositoryGraph:
    metadata = GraphMetadata(
        graph_id=GraphId("graph:repo:demo:1"),
        graph_type=GraphType.REPOSITORY,
        schema_version=REPOSITORY_GRAPH_SCHEMA_VERSION,
        generator_version="1.0.0",
        source_fingerprint="test:demo",
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
            properties=FrameworkProperties(
                canonical_key="spring-boot",
                name="Spring Boot",
                aliases=("springboot",),
            ),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(canonical_key="react", name="React"),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.LANGUAGE,
            properties=LanguageProperties(canonical_key="java", name="Java"),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.LANGUAGE,
            properties=LanguageProperties(canonical_key="php", name="PHP"),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.BUILD_TOOL,
            properties=EngineeringKnowledgeProperties(canonical_key="maven", name="Maven"),
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


def _sample_repository(*, shuffle: bool = False) -> RepositoryGraph:
    factory = RepositoryGraphNodeFactory("demo")
    repo = factory.repository(RepositoryProperties(name="demo"))
    spring = factory.dependency(
        DependencyProperties(ecosystem="maven", name="spring-boot", namespace=None)
    )
    react = factory.dependency(DependencyProperties(ecosystem="npm", name="React", namespace=None))
    unknown = factory.dependency(
        DependencyProperties(ecosystem="npm", name="left-pad", namespace=None)
    )
    java_file = factory.file(
        FileProperties(
            path="src/Main.java",
            file_kind=RepositoryFileKind.SOURCE,
            language="Java",
        )
    )
    maven_module = factory.module(
        module_key="app",
        properties=ModuleProperties(name="app", path="app", build_system="Maven"),
    )
    nodes: list[GraphNode] = [repo, spring, react, unknown, java_file, maven_module]
    if shuffle:
        nodes = [unknown, maven_module, react, repo, java_file, spring]
    return _repository_graph(*nodes)


def test_known_technologies_match() -> None:
    result = KnowledgePipeline().bind(_sample_repository(), _sample_knowledge())
    pairs = {
        (binding.matched_key, binding.knowledge_node_type, binding.observation_kind)
        for binding in result.bindings
    }
    assert (
        "spring-boot",
        "framework",
        KnowledgeObservationKind.DEPENDENCY_NAME,
    ) in pairs
    assert ("react", "framework", KnowledgeObservationKind.DEPENDENCY_NAME) in pairs
    assert ("java", "language", KnowledgeObservationKind.FILE_LANGUAGE) in pairs
    assert ("maven", "build_tool", KnowledgeObservationKind.MODULE_BUILD_SYSTEM) in pairs
    assert all(binding.confidence == 1.0 for binding in result.bindings)
    assert all(
        binding.binding_type is KnowledgeBindingType.USES_CONCEPT for binding in result.bindings
    )


def test_unknown_technologies_do_not_match() -> None:
    result = bind_repository_knowledge(_sample_repository(), _sample_knowledge())
    matched_keys = {binding.matched_key for binding in result.bindings}
    assert "left-pad" not in matched_keys
    unmatched_roots = {node_id.root for node_id in result.unmatched_repository_node_ids}
    assert any("left-pad" in root for root in unmatched_roots)


def test_duplicate_bindings_are_not_produced() -> None:
    knowledge = _sample_knowledge()
    first = KnowledgePipeline().bind(_sample_repository(), knowledge)
    second = KnowledgePipeline().bind(_sample_repository(), knowledge)
    ids = [binding.binding_id for binding in first.bindings]
    assert len(ids) == len(set(ids))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_matching_is_deterministic_and_order_independent() -> None:
    knowledge = _sample_knowledge()
    left = KnowledgePipeline().bind(_sample_repository(shuffle=False), knowledge)
    right = KnowledgePipeline().bind(_sample_repository(shuffle=True), knowledge)
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    binding_ids = [item.binding_id for item in left.bindings]
    assert binding_ids == sorted(binding_ids)


def test_alias_exact_match() -> None:
    factory = RepositoryGraphNodeFactory("demo")
    graph = _repository_graph(
        factory.repository(RepositoryProperties(name="demo")),
        factory.dependency(DependencyProperties(ecosystem="maven", name="springboot")),
    )
    result = KnowledgePipeline().bind(graph, _sample_knowledge())
    assert len(result.bindings) == 1
    binding = result.bindings[0]
    assert binding.matched_key == "springboot"
    assert binding.matching_strategy is KnowledgeMatchingStrategy.EXACT_ALIAS
    assert binding.knowledge_node_id.root == "ekg:framework:spring-boot"


def test_builtin_catalog_matches_core_concepts() -> None:
    factory = RepositoryGraphNodeFactory("app")
    graph = _repository_graph(
        factory.repository(RepositoryProperties(name="app")),
        factory.dependency(DependencyProperties(ecosystem="maven", name="spring-boot")),
        factory.dependency(DependencyProperties(ecosystem="npm", name="react")),
        factory.file(
            FileProperties(
                path="src/index.js",
                file_kind=RepositoryFileKind.SOURCE,
                language="javascript",
            )
        ),
        factory.module(
            module_key="build",
            properties=ModuleProperties(name="build", path="build", build_system="gradle"),
        ),
    )
    knowledge = load_builtin_engineering_knowledge_catalog()
    result = KnowledgePipeline().bind(graph, knowledge)
    keys = {binding.matched_key for binding in result.bindings}
    assert {"spring-boot", "react", "javascript", "gradle"} <= keys
    assert result.repository_graph_id == graph.metadata.graph_id
    assert result.repository_source_fingerprint == graph.metadata.source_fingerprint
    assert result.knowledge_graph_id == knowledge.metadata.graph_id
    assert result.knowledge_source_fingerprint == knowledge.metadata.source_fingerprint


def test_does_not_mutate_source_graphs() -> None:
    repo = _sample_repository()
    knowledge = _sample_knowledge()
    before_repo = repo.snapshot.model_dump(mode="json")
    before_knowledge = knowledge.snapshot.model_dump(mode="json")
    KnowledgePipeline().bind(repo, knowledge)
    assert repo.snapshot.model_dump(mode="json") == before_repo
    assert knowledge.snapshot.model_dump(mode="json") == before_knowledge


def test_php_language_observation_matches() -> None:
    factory = RepositoryGraphNodeFactory("phpapp")
    graph = _repository_graph(
        factory.repository(RepositoryProperties(name="phpapp")),
        factory.file(
            FileProperties(
                path="index.php",
                file_kind=RepositoryFileKind.SOURCE,
                language="PHP",
            )
        ),
    )
    result = KnowledgePipeline().bind(graph, _sample_knowledge())
    assert len(result.bindings) == 1
    assert result.bindings[0].matched_key == "php"
    assert result.bindings[0].knowledge_node_type == "language"


def test_result_json_round_trip() -> None:
    result = KnowledgePipeline().bind(_sample_repository(), _sample_knowledge())
    from codestrata.domain.knowledge_binding import KnowledgeBindingResult

    restored = KnowledgeBindingResult.model_validate(result.model_dump(mode="json"))
    assert restored == result


def test_result_records_source_fingerprints() -> None:
    repo = _sample_repository()
    knowledge = _sample_knowledge()
    result = KnowledgePipeline().bind(repo, knowledge)
    assert result.repository_source_fingerprint == "test:demo"
    assert result.knowledge_source_fingerprint == knowledge.metadata.source_fingerprint
    assert "T" not in result.repository_source_fingerprint  # no ISO timestamps
    dumped = result.model_dump(mode="json")
    assert "repository_source_fingerprint" in dumped
    assert "knowledge_source_fingerprint" in dumped


def test_alias_collision_fails_closed() -> None:
    from codestrata.services.knowledge_pipeline import AmbiguousKnowledgeConceptError

    factory = EngineeringKnowledgeNodeFactory()
    nodes = [
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(
                canonical_key="spring-boot",
                name="Spring Boot",
                aliases=("boot",),
            ),
            provenance=(_provenance(),),
        ),
        factory.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=FrameworkProperties(
                canonical_key="micronaut",
                name="Micronaut",
                aliases=("Boot",),  # normalizes to same alias as spring-boot
            ),
            provenance=(_provenance(),),
        ),
    ]
    metadata = build_engineering_knowledge_metadata(
        EngineeringKnowledgeCatalogMetadata(
            catalog_id="ambiguous-catalog",
            catalog_version="1.0.0",
            name="Ambiguous Catalog",
        )
    )
    knowledge = EngineeringKnowledgeGraph(
        GraphSnapshot(
            metadata=metadata,
            nodes=tuple(sorted(nodes, key=lambda node: node.id.root)),
            relationships=(),
        )
    )
    with pytest.raises(AmbiguousKnowledgeConceptError, match="boot") as exc_info:
        KnowledgePipeline().bind(_sample_repository(), knowledge)
    error = exc_info.value
    assert error.alias == "boot"
    assert "ekg:framework:spring-boot" in error.knowledge_node_ids
    assert "ekg:framework:micronaut" in error.knowledge_node_ids
    assert error.catalog_hint is not None
    assert "ambiguous-catalog" in error.catalog_hint
