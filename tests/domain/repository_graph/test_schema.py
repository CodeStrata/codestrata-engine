"""Tests for Repository Graph schema validation and aggregate wrapper."""

from __future__ import annotations

import pytest

from codestrata.domain.graph import (
    GraphGenerationMode,
    GraphId,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    GraphSnapshot,
    GraphStatus,
    GraphType,
    NodeId,
)
from codestrata.domain.repository_graph import (
    CallableProperties,
    DependencyProperties,
    FileProperties,
    ModuleProperties,
    NamespaceProperties,
    RepositoryCallableKind,
    RepositoryFileKind,
    RepositoryGraph,
    RepositoryGraphNodeFactory,
    RepositoryGraphSchema,
    RepositoryGraphSchemaError,
    RepositoryNodeType,
    RepositoryProperties,
    RepositoryRelationshipType,
    RepositoryTypeKind,
    TypeProperties,
)


def _metadata(*, graph_type: GraphType = GraphType.REPOSITORY) -> GraphMetadata:
    return GraphMetadata(
        graph_id=GraphId("graph:petclinic"),
        graph_type=graph_type,
        schema_version="1.0.0",
        generator_version="0.1.0",
        source_fingerprint="fp:1",
        generation_mode=GraphGenerationMode.FULL,
        status=GraphStatus.VALID,
    )


def _rel(
    *,
    relationship_id: str,
    relationship_type: str,
    source: GraphNode,
    target: GraphNode,
) -> GraphRelationship:
    return GraphRelationship(
        id=relationship_id,
        relationship_type=relationship_type,
        source_node_id=source.id,
        target_node_id=target.id,
    )


def _sample_nodes() -> dict[str, GraphNode]:
    factory = RepositoryGraphNodeFactory("petclinic")
    return {
        "repo": factory.repository(RepositoryProperties(name="Petclinic")),
        "module": factory.module(
            module_key="app",
            properties=ModuleProperties(name="app"),
        ),
        "file": factory.file(
            FileProperties(path="src/App.java", file_kind=RepositoryFileKind.SOURCE)
        ),
        "namespace": factory.namespace(NamespaceProperties(qualified_name="com.example")),
        "type": factory.type(
            TypeProperties(
                name="App",
                qualified_name="com.example.App",
                type_kind=RepositoryTypeKind.CLASS,
            )
        ),
        "callable_a": factory.callable(
            qualified_owner="com.example.App",
            signature="run()",
            properties=CallableProperties(
                name="run",
                qualified_signature="com.example.App#run()",
                callable_kind=RepositoryCallableKind.METHOD,
            ),
        ),
        "callable_b": factory.callable(
            qualified_owner="com.example.App",
            signature="stop()",
            properties=CallableProperties(
                name="stop",
                qualified_signature="com.example.App#stop()",
                callable_kind=RepositoryCallableKind.METHOD,
            ),
        ),
        "dependency": factory.dependency(
            DependencyProperties(
                ecosystem="maven",
                name="spring-core",
                namespace="org.springframework",
            )
        ),
    }


def test_valid_repository_graph_accepted() -> None:
    nodes = _sample_nodes()
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=tuple(nodes.values()),
        relationships=(
            _rel(
                relationship_id="rel:contains-module",
                relationship_type=RepositoryRelationshipType.CONTAINS,
                source=nodes["repo"],
                target=nodes["module"],
            ),
            _rel(
                relationship_id="rel:contains-file",
                relationship_type=RepositoryRelationshipType.CONTAINS,
                source=nodes["module"],
                target=nodes["file"],
            ),
            _rel(
                relationship_id="rel:declares-type",
                relationship_type=RepositoryRelationshipType.DECLARES,
                source=nodes["file"],
                target=nodes["type"],
            ),
            _rel(
                relationship_id="rel:declares-callable",
                relationship_type=RepositoryRelationshipType.DECLARES,
                source=nodes["type"],
                target=nodes["callable_a"],
            ),
            _rel(
                relationship_id="rel:depends",
                relationship_type=RepositoryRelationshipType.DEPENDS_ON,
                source=nodes["type"],
                target=nodes["dependency"],
            ),
            _rel(
                relationship_id="rel:calls",
                relationship_type=RepositoryRelationshipType.CALLS,
                source=nodes["callable_a"],
                target=nodes["callable_b"],
            ),
        ),
    )
    assert RepositoryGraphSchema.validate(snapshot) is snapshot
    graph = RepositoryGraph(snapshot)
    assert graph.nodes is snapshot.nodes
    assert graph.relationships is snapshot.relationships
    assert graph.metadata.graph_type is GraphType.REPOSITORY


def test_wrong_graph_type_and_unknown_vocabulary_rejected() -> None:
    nodes = _sample_nodes()
    with pytest.raises(RepositoryGraphSchemaError, match="graph_type"):
        RepositoryGraphSchema.validate(
            GraphSnapshot(
                metadata=_metadata(graph_type=GraphType.ASSESSMENT),
                nodes=(nodes["repo"],),
            )
        )

    unknown_node = GraphNode(
        id=NodeId("repo:petclinic:weird"),
        node_type="java_class",
        schema_version="1.0.0",
    )
    with pytest.raises(RepositoryGraphSchemaError, match="unknown Repository Graph node_type"):
        RepositoryGraphSchema.validate(GraphSnapshot(metadata=_metadata(), nodes=(unknown_node,)))

    with pytest.raises(
        RepositoryGraphSchemaError, match="unknown Repository Graph relationship_type"
    ):
        RepositoryGraphSchema.validate(
            GraphSnapshot(
                metadata=_metadata(),
                nodes=(nodes["callable_a"], nodes["callable_b"]),
                relationships=(
                    _rel(
                        relationship_id="rel:bad",
                        relationship_type="invokes",
                        source=nodes["callable_a"],
                        target=nodes["callable_b"],
                    ),
                ),
            )
        )


@pytest.mark.parametrize(
    ("relationship_type", "source_key", "target_key", "ok"),
    [
        (RepositoryRelationshipType.CONTAINS, "repo", "module", True),
        (RepositoryRelationshipType.CONTAINS, "repo", "file", True),
        (RepositoryRelationshipType.CONTAINS, "module", "module", True),
        (RepositoryRelationshipType.CONTAINS, "module", "file", True),
        (RepositoryRelationshipType.CONTAINS, "file", "type", False),
        (RepositoryRelationshipType.DECLARES, "file", "namespace", True),
        (RepositoryRelationshipType.DECLARES, "file", "type", True),
        (RepositoryRelationshipType.DECLARES, "file", "callable_a", True),
        (RepositoryRelationshipType.DECLARES, "namespace", "type", True),
        (RepositoryRelationshipType.DECLARES, "namespace", "callable_a", True),
        (RepositoryRelationshipType.DECLARES, "type", "callable_a", True),
        (RepositoryRelationshipType.DECLARES, "repo", "type", False),
        (RepositoryRelationshipType.DEPENDS_ON, "repo", "dependency", True),
        (RepositoryRelationshipType.DEPENDS_ON, "module", "dependency", True),
        (RepositoryRelationshipType.DEPENDS_ON, "type", "dependency", True),
        (RepositoryRelationshipType.DEPENDS_ON, "callable_a", "dependency", True),
        (RepositoryRelationshipType.DEPENDS_ON, "dependency", "dependency", True),
        (RepositoryRelationshipType.DEPENDS_ON, "file", "dependency", False),
        (RepositoryRelationshipType.CALLS, "callable_a", "callable_b", True),
        (RepositoryRelationshipType.CALLS, "type", "callable_a", False),
    ],
)
def test_relationship_endpoint_matrix(
    relationship_type: RepositoryRelationshipType,
    source_key: str,
    target_key: str,
    ok: bool,
) -> None:
    nodes = _sample_nodes()
    factory = RepositoryGraphNodeFactory("petclinic")

    if source_key == "module" and target_key == "module":
        child = factory.module(
            module_key="child",
            properties=ModuleProperties(name="child"),
        )
        snapshot_nodes = (nodes["module"], child)
        source = nodes["module"]
        target = child
    elif source_key == "dependency" and target_key == "dependency":
        other = factory.dependency(
            DependencyProperties(
                ecosystem="maven",
                name="commons-lang",
                namespace="org.apache",
            )
        )
        snapshot_nodes = (nodes["dependency"], other)
        source = nodes["dependency"]
        target = other
    else:
        snapshot_nodes = (nodes[source_key], nodes[target_key])
        source = nodes[source_key]
        target = nodes[target_key]

    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=snapshot_nodes,
        relationships=(
            _rel(
                relationship_id="rel:case",
                relationship_type=relationship_type,
                source=source,
                target=target,
            ),
        ),
    )
    if ok:
        RepositoryGraphSchema.validate(snapshot)
    else:
        with pytest.raises(RepositoryGraphSchemaError, match="invalid"):
            RepositoryGraphSchema.validate(snapshot)


def test_repository_node_type_values_are_strings() -> None:
    assert RepositoryNodeType.FILE.value == "file"
    assert RepositoryRelationshipType.DEPENDS_ON.value == "depends_on"
