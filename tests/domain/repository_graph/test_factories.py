"""Tests for Repository Graph node construction."""

from __future__ import annotations

from codestrata.domain.graph import EvidenceReference, Provenance, ProvenanceSource
from codestrata.domain.repository_graph import (
    REPOSITORY_GRAPH_SCHEMA_VERSION,
    CallableProperties,
    DependencyProperties,
    DependencyScope,
    FileProperties,
    ModuleProperties,
    NamespaceProperties,
    RepositoryCallableKind,
    RepositoryFileKind,
    RepositoryGraphNodeFactory,
    RepositoryNodeType,
    RepositoryProperties,
    RepositoryTypeKind,
    TypeProperties,
)


def _provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
        source_id="extractor:repository-graph",
        extractor_id="rg-test",
        extractor_version="0.1.0",
        confidence=1.0,
    )


def _evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_type="file_location",
        source_id="file:src/App.java",
        path="src/App.java",
        start_line=1,
        end_line=2,
    )


def test_node_factory_builds_typed_deterministic_nodes() -> None:
    factory = RepositoryGraphNodeFactory("petclinic")
    provenance = (_provenance(),)
    evidence = (_evidence(),)

    repo = factory.repository(
        RepositoryProperties(name="Petclinic"),
        provenance=provenance,
        evidence=evidence,
    )
    assert repo.node_type == RepositoryNodeType.REPOSITORY
    assert str(repo.id) == "repo:petclinic"
    assert repo.schema_version == REPOSITORY_GRAPH_SCHEMA_VERSION
    assert repo.properties["name"] == "Petclinic"
    assert repo.provenance == provenance
    assert repo.evidence == evidence

    module = factory.module(
        module_key="app",
        properties=ModuleProperties(name="app", path="modules/app"),
    )
    assert module.node_type == RepositoryNodeType.MODULE
    assert str(module.id) == "repo:petclinic:module:app"

    file_node = factory.file(
        FileProperties(path="src/App.java", file_kind=RepositoryFileKind.SOURCE),
        provenance=provenance,
    )
    assert file_node.node_type == RepositoryNodeType.FILE
    assert str(file_node.id) == "repo:petclinic:file:src/App.java"
    assert file_node.properties["file_kind"] == "source"
    assert file_node.provenance == provenance

    ns = factory.namespace(NamespaceProperties(qualified_name="com.example"))
    assert ns.node_type == RepositoryNodeType.NAMESPACE

    type_node = factory.type(
        TypeProperties(
            name="App",
            qualified_name="com.example.App",
            type_kind=RepositoryTypeKind.CLASS,
        )
    )
    assert type_node.node_type == RepositoryNodeType.TYPE
    assert str(type_node.id) == "repo:petclinic:type:com.example.App"

    callable_node = factory.callable(
        qualified_owner="com.example.App",
        signature="run()",
        properties=CallableProperties(
            name="run",
            qualified_signature="com.example.App#run()",
            callable_kind=RepositoryCallableKind.METHOD,
        ),
    )
    assert callable_node.node_type == RepositoryNodeType.CALLABLE
    assert str(callable_node.id).endswith("#run()")

    dep = factory.dependency(
        DependencyProperties(
            ecosystem="maven",
            name="spring-core",
            namespace="org.springframework",
            version="6.1.0",
            scope=DependencyScope.COMPILE,
        )
    )
    assert dep.node_type == RepositoryNodeType.DEPENDENCY
    assert "6.1.0" not in str(dep.id)
    assert dep.properties["version"] == "6.1.0"
