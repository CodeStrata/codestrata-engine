"""Tests for Engineering Knowledge Catalog models, loader, and builtin seed."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.domain.engineering_knowledge import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
)
from codestrata.domain.graph import GraphGenerationMode, GraphType, ProvenanceSource
from codestrata.services.engineering_knowledge import (
    BUILTIN_CATALOG_ID,
    BUILTIN_CATALOG_VERSION,
    EngineeringKnowledgeCatalogDocument,
    EngineeringKnowledgeCatalogLoader,
    EngineeringKnowledgeCatalogNode,
    EngineeringKnowledgeCatalogParseError,
    EngineeringKnowledgeCatalogReference,
    EngineeringKnowledgeCatalogRelationship,
    EngineeringKnowledgeCatalogValidationError,
    load_builtin_engineering_knowledge_catalog,
)
from codestrata.services.engineering_knowledge.property_dispatch import validate_node_properties


def _minimal_catalog_yaml(
    *,
    extra_nodes: str = "",
    extra_relationships: str = "",
    nodes: str | None = None,
    relationships: str | None = None,
) -> str:
    default_nodes = """
  - node_type: language
    canonical_key: java
    properties:
      name: Java
  - node_type: framework
    canonical_key: spring-boot
    properties:
      name: Spring Boot
      ecosystem: java
  - node_type: quality_attribute
    canonical_key: maintainability
    properties:
      name: Maintainability
      definition: Ability to change safely.
"""
    default_relationships = """
  - relationship_type: depends_on
    source: framework:spring-boot
    target: language:java
"""
    body_nodes = nodes if nodes is not None else default_nodes + extra_nodes
    body_rels = (
        relationships if relationships is not None else default_relationships + extra_relationships
    )
    return f"""
catalog_id: test-catalog
catalog_version: "1.0.0"
name: Test Catalog
description: Fixture catalog
published_at: "2026-01-01T00:00:00Z"
source: test
schema_version: "1.0.0"
nodes:
{body_nodes}
relationships:
{body_rels}
"""


def test_catalog_document_valid_and_immutable() -> None:
    document = EngineeringKnowledgeCatalogDocument.model_validate(
        {
            "metadata": {
                "catalog_id": "demo",
                "catalog_version": "1.0.0",
                "name": "Demo",
            },
            "schema_version": "1.0.0",
            "nodes": [
                {
                    "node_type": "language",
                    "canonical_key": "java",
                    "properties": {"name": "Java"},
                }
            ],
            "relationships": [],
        }
    )
    assert document.metadata.catalog_id == "demo"
    assert isinstance(document.nodes, tuple)
    with pytest.raises(AttributeError):
        document.nodes.append(document.nodes[0])  # type: ignore[attr-defined]


def test_catalog_document_blank_metadata_rejected() -> None:
    with pytest.raises((ValidationError, EngineeringKnowledgeCatalogValidationError, ValueError)):
        EngineeringKnowledgeCatalogDocument.model_validate(
            {
                "metadata": {
                    "catalog_id": " ",
                    "catalog_version": "1.0.0",
                    "name": "Demo",
                },
                "schema_version": "1.0.0",
                "nodes": [],
                "relationships": [],
            }
        )


def test_catalog_document_json_round_trip() -> None:
    document = EngineeringKnowledgeCatalogDocument.model_validate(
        {
            "metadata": {
                "catalog_id": "demo",
                "catalog_version": "1.0.0",
                "name": "Demo",
                "published_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
            "schema_version": "1.0.0",
            "nodes": [
                {
                    "node_type": "language",
                    "canonical_key": "Java",
                    "properties": {"name": "Java", "tags": ["jvm"]},
                }
            ],
            "relationships": [],
        }
    )
    dumped = document.model_dump(mode="json")
    restored = EngineeringKnowledgeCatalogDocument.model_validate(dumped)
    assert restored == document
    assert document.model_dump_json()


def test_catalog_reference_valid_and_normalized() -> None:
    ref = EngineeringKnowledgeCatalogReference.parse("framework:Spring Boot")
    assert ref.node_type is EngineeringKnowledgeNodeType.FRAMEWORK
    assert ref.canonical_key == "spring-boot"
    assert ref.as_token() == "framework:spring-boot"


def test_catalog_reference_blank_and_invalid_separators_rejected() -> None:
    with pytest.raises(ValueError):
        EngineeringKnowledgeCatalogReference.parse("framework:")
    with pytest.raises(ValueError):
        EngineeringKnowledgeCatalogReference.parse("framework")
    with pytest.raises(ValueError):
        EngineeringKnowledgeCatalogReference.parse("framework:spring:boot")
    with pytest.raises(ValueError):
        EngineeringKnowledgeCatalogReference.parse("framework:spring/boot")


def test_loader_valid_catalog_text() -> None:
    graph = EngineeringKnowledgeCatalogLoader().load_text(_minimal_catalog_yaml())
    assert graph.metadata.graph_type is GraphType.ENGINEERING_KNOWLEDGE
    assert len(graph.nodes) == 3
    assert len(graph.relationships) == 1


def test_loader_malformed_yaml_rejected() -> None:
    with pytest.raises(EngineeringKnowledgeCatalogParseError):
        EngineeringKnowledgeCatalogLoader().load_text("catalog_id: [unterminated")


def test_loader_unsafe_yaml_tags_rejected() -> None:
    payload = "!!python/object/apply:os.system ['echo pwned']\n"
    with pytest.raises(EngineeringKnowledgeCatalogParseError):
        EngineeringKnowledgeCatalogLoader().load_text(payload)


def test_loader_wrong_top_level_structure_rejected() -> None:
    with pytest.raises(EngineeringKnowledgeCatalogParseError):
        EngineeringKnowledgeCatalogLoader().load_text("- just a list\n")


def test_property_dispatch_framework_language_rule() -> None:
    framework = validate_node_properties(
        node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
        canonical_key="spring-boot",
        properties={"name": "Spring Boot", "ecosystem": "java"},
    )
    assert framework.name == "Spring Boot"

    language = validate_node_properties(
        node_type=EngineeringKnowledgeNodeType.LANGUAGE,
        canonical_key="java",
        properties={"name": "Java", "compiled": True},
    )
    assert language.canonical_key == "java"

    rule = validate_node_properties(
        node_type=EngineeringKnowledgeNodeType.RULE,
        canonical_key="example-rule",
        properties={
            "name": "Example",
            "rationale": "Because",
            "condition_expression": "never.evaluated",
        },
    )
    assert rule.condition_expression == "never.evaluated"


def test_property_dispatch_malformed_rejected_and_generic_fallback() -> None:
    with pytest.raises(EngineeringKnowledgeCatalogValidationError):
        validate_node_properties(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            canonical_key="spring-boot",
            properties={"ecosystem": "java"},  # missing name
        )
    with pytest.raises(EngineeringKnowledgeCatalogValidationError):
        validate_node_properties(
            node_type=EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE,
            canonical_key="maintainability",
            properties={"name": "Maintainability"},  # missing definition
        )
    runtime = validate_node_properties(
        node_type=EngineeringKnowledgeNodeType.RUNTIME,
        canonical_key="jvm",
        properties={"name": "JVM"},
    )
    assert runtime.name == "JVM"


def test_duplicate_node_reference_rejected() -> None:
    yaml_text = _minimal_catalog_yaml(
        extra_nodes="""
  - node_type: language
    canonical_key: java
    properties:
      name: Java Duplicate
"""
    )
    with pytest.raises(EngineeringKnowledgeCatalogValidationError, match="duplicate"):
        EngineeringKnowledgeCatalogLoader().load_text(yaml_text)


def test_duplicate_relationship_rejected() -> None:
    yaml_text = _minimal_catalog_yaml(
        extra_relationships="""
  - relationship_type: depends_on
    source: framework:spring-boot
    target: language:java
"""
    )
    with pytest.raises(EngineeringKnowledgeCatalogValidationError, match="duplicate"):
        EngineeringKnowledgeCatalogLoader().load_text(yaml_text)


def test_missing_relationship_endpoints_rejected() -> None:
    with pytest.raises(EngineeringKnowledgeCatalogValidationError, match="source"):
        EngineeringKnowledgeCatalogLoader().load_text(
            _minimal_catalog_yaml(
                relationships="""
  - relationship_type: depends_on
    source: framework:missing
    target: language:java
"""
            )
        )
    with pytest.raises(EngineeringKnowledgeCatalogValidationError, match="target"):
        EngineeringKnowledgeCatalogLoader().load_text(
            _minimal_catalog_yaml(
                relationships="""
  - relationship_type: depends_on
    source: framework:spring-boot
    target: language:missing
"""
            )
        )


def test_explicit_provenance_preserved() -> None:
    yaml_text = _minimal_catalog_yaml(
        nodes="""
  - node_type: language
    canonical_key: java
    properties:
      name: Java
    provenance:
      - source_type: human
        source_id: curator:alice
        extractor_id: manual
        extractor_version: "1.0.0"
  - node_type: framework
    canonical_key: spring-boot
    properties:
      name: Spring Boot
  - node_type: quality_attribute
    canonical_key: maintainability
    properties:
      name: Maintainability
      definition: Ability to change safely.
"""
    )
    graph = EngineeringKnowledgeCatalogLoader().load_text(yaml_text)
    java = next(node for node in graph.nodes if node.id.root.endswith(":java"))
    assert java.provenance[0].source_type is ProvenanceSource.HUMAN
    assert java.provenance[0].source_id == "curator:alice"
    spring = next(node for node in graph.nodes if "spring-boot" in node.id.root)
    assert spring.provenance[0].source_type is ProvenanceSource.ENGINEERING_KNOWLEDGE_PACK
    assert spring.provenance[0].source_id == "catalog:test-catalog:1.0.0"


def test_graph_creation_metadata_ordering_and_schema() -> None:
    graph = EngineeringKnowledgeCatalogLoader().load_text(_minimal_catalog_yaml())
    assert graph.metadata.graph_type is GraphType.ENGINEERING_KNOWLEDGE
    assert graph.metadata.generation_mode is GraphGenerationMode.REUSED
    assert "test-catalog" in graph.metadata.graph_id.root
    assert "1.0.0" in graph.metadata.source_fingerprint
    node_ids = [node.id.root for node in graph.nodes]
    assert node_ids == sorted(node_ids)
    rel_ids = [item.id for item in graph.relationships]
    assert rel_ids == sorted(rel_ids)
    assert graph.snapshot.model_dump_json()

    bad = _minimal_catalog_yaml(
        extra_relationships="""
  - relationship_type: depends_on
    source: language:java
    target: framework:spring-boot
"""
    )
    with pytest.raises(EngineeringKnowledgeCatalogValidationError):
        EngineeringKnowledgeCatalogLoader().load_text(bad)


def test_load_path_and_bytes(tmp_path: Path) -> None:
    text = _minimal_catalog_yaml()
    graph_bytes = EngineeringKnowledgeCatalogLoader().load_bytes(text.encode("utf-8"))
    assert len(graph_bytes.nodes) == 3

    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(text, encoding="utf-8")
    graph_path = EngineeringKnowledgeCatalogLoader().load_path(catalog_path)
    assert graph_path.snapshot.model_dump(mode="json") == graph_bytes.snapshot.model_dump(
        mode="json"
    )


def test_builtin_catalog_loads() -> None:
    graph = load_builtin_engineering_knowledge_catalog()
    again = load_builtin_engineering_knowledge_catalog()
    assert graph.snapshot.model_dump(mode="json") == again.snapshot.model_dump(mode="json")

    assert BUILTIN_CATALOG_ID == "codestrata-core"
    assert BUILTIN_CATALOG_VERSION == "1.0.0"
    assert "codestrata-core" in graph.metadata.graph_id.root
    assert "1.0.0" in graph.metadata.source_fingerprint
    assert len(graph.nodes) >= 30
    assert len(graph.relationships) >= 20

    node_keys = {
        (node.node_type, str(node.properties.get("canonical_key"))) for node in graph.nodes
    }
    assert ("language", "java") in node_keys
    assert ("framework", "spring-boot") in node_keys
    assert ("quality_attribute", "maintainability") in node_keys
    assert ("anti_pattern", "tight-coupling") in node_keys
    assert ("modernization_strategy", "refactor") in node_keys

    rel_types = {
        (
            item.relationship_type,
            item.source_node_id.root,
            item.target_node_id.root,
        )
        for item in graph.relationships
    }
    assert (
        EngineeringKnowledgeRelationshipType.DEPENDS_ON.value,
        "ekg:framework:spring-boot",
        "ekg:language:java",
    ) in rel_types
    assert (
        EngineeringKnowledgeRelationshipType.IMPACTS.value,
        "ekg:anti-pattern:tight-coupling",
        "ekg:quality-attribute:maintainability",
    ) in rel_types

    assert len({node.id.root for node in graph.nodes}) == len(graph.nodes)
    assert len({item.id for item in graph.relationships}) == len(graph.relationships)

    forbidden_types = {
        "repository",
        "module",
        "file",
        "package",
        "assessment",
        "finding",
    }
    assert not {node.node_type for node in graph.nodes} & forbidden_types

    for node in graph.nodes:
        assert node.provenance
        assert "codestrata-core" in node.provenance[0].source_id
        assert "1.0.0" in node.provenance[0].source_id


def test_catalog_rejects_repository_specific_properties() -> None:
    with pytest.raises((ValidationError, ValueError)):
        EngineeringKnowledgeCatalogNode.model_validate(
            {
                "node_type": "language",
                "canonical_key": "java",
                "properties": {
                    "name": "Java",
                    "repository_id": "repo-1",
                },
            }
        )


def test_load_document_api() -> None:
    document = EngineeringKnowledgeCatalogLoader().parse_document(_minimal_catalog_yaml())
    graph = EngineeringKnowledgeCatalogLoader().load_document(document)
    assert len(graph.nodes) == 3
    assert isinstance(
        EngineeringKnowledgeCatalogRelationship.model_validate(
            {
                "relationship_type": "related_to",
                "source": {"node_type": "language", "canonical_key": "java"},
                "target": "framework:spring-boot",
            }
        ).source,
        EngineeringKnowledgeCatalogReference,
    )


def test_document_deterministic_ordering() -> None:
    document = EngineeringKnowledgeCatalogDocument.model_validate(
        {
            "metadata": {
                "catalog_id": "demo",
                "catalog_version": "1.0.0",
                "name": "Demo",
            },
            "schema_version": "1.0.0",
            "nodes": [
                {
                    "node_type": "language",
                    "canonical_key": "python",
                    "properties": {"name": "Python"},
                },
                {
                    "node_type": "language",
                    "canonical_key": "java",
                    "properties": {"name": "Java"},
                },
            ],
            "relationships": [],
        }
    )
    assert [node.canonical_key for node in document.nodes] == ["java", "python"]
