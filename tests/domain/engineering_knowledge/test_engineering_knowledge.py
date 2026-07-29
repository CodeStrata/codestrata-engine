"""Tests for Engineering Knowledge Graph domain schema."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from codestrata.domain.engineering_knowledge import (
    ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeGraph,
    EngineeringKnowledgeGraphSchema,
    EngineeringKnowledgeGraphSchemaError,
    EngineeringKnowledgeNodeFactory,
    EngineeringKnowledgeNodeIdFactory,
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeProperties,
    EngineeringKnowledgeRelationshipFactory,
    EngineeringKnowledgeRelationshipIdFactory,
    EngineeringKnowledgeRelationshipType,
    FrameworkProperties,
    KnowledgeMaturityLevel,
    KnowledgeRuleKind,
    KnowledgeSeverity,
    ModernizationStrategyKind,
    QualityAttributeProperties,
    RuleProperties,
    TechnologyLifecycleStatus,
    TechnologyProperties,
    build_engineering_knowledge_metadata,
)
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
    Provenance,
    ProvenanceSource,
)


def _provenance() -> Provenance:
    return Provenance(
        source_type=ProvenanceSource.ENGINEERING_KNOWLEDGE_PACK,
        source_id="catalog:codestrata-core",
        extractor_id="curated",
        extractor_version="1.0.0",
    )


def _metadata() -> GraphMetadata:
    return build_engineering_knowledge_metadata(
        EngineeringKnowledgeCatalogMetadata(
            catalog_id="codestrata-core",
            catalog_version="1.0.0",
            name="CodeStrata Core Knowledge",
        )
    )


def test_enum_vocabularies() -> None:
    assert EngineeringKnowledgeNodeType.FRAMEWORK == "framework"
    assert EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE == "architecture_style"
    assert EngineeringKnowledgeRelationshipType.GOVERNED_BY == "governed_by"
    assert TechnologyLifecycleStatus.END_OF_SUPPORT == "end_of_support"
    assert KnowledgeMaturityLevel.ESTABLISHED == "established"
    assert KnowledgeSeverity.CRITICAL == "critical"
    assert ModernizationStrategyKind.REPLATFORM == "replatform"
    assert KnowledgeRuleKind.LIFECYCLE == "lifecycle"
    assert len(set(EngineeringKnowledgeNodeType)) == 17
    assert len(set(EngineeringKnowledgeRelationshipType)) == 15


def test_node_and_relationship_id_factories() -> None:
    nodes = EngineeringKnowledgeNodeIdFactory()
    spring = nodes.create(
        node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
        canonical_key="Spring Boot",
    )
    assert str(spring) == "ekg:framework:spring-boot"
    assert (
        str(
            nodes.create(
                node_type=EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE,
                canonical_key="Micro_Services",
            )
        )
        == "ekg:architecture-style:micro-services"
    )
    assert (
        str(
            nodes.create(
                node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
                canonical_key="spring---boot",
            )
        )
        == "ekg:framework:spring-boot"
    )
    assert nodes.create(
        node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
        canonical_key="spring-boot",
    ) == nodes.create(
        node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
        canonical_key="Spring Boot",
    )
    assert nodes.create(
        node_type=EngineeringKnowledgeNodeType.TECHNOLOGY,
        canonical_key="spring-boot",
    ) != nodes.create(
        node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
        canonical_key="spring-boot",
    )

    with pytest.raises(ValueError, match="blank"):
        nodes.create(node_type=EngineeringKnowledgeNodeType.RULE, canonical_key=" ")
    with pytest.raises(ValueError, match="path separators|credential"):
        nodes.create(node_type=EngineeringKnowledgeNodeType.RULE, canonical_key="a/b")

    rels = EngineeringKnowledgeRelationshipIdFactory()
    source = "ekg:framework:spring-boot"
    target = "ekg:language:java"
    first = rels.create(
        relationship_type=EngineeringKnowledgeRelationshipType.DEPENDS_ON,
        source_node_id=source,
        target_node_id=target,
    )
    second = rels.create(
        relationship_type=EngineeringKnowledgeRelationshipType.DEPENDS_ON,
        source_node_id=source,
        target_node_id=target,
    )
    assert first == second
    assert first.startswith("ekg-rel:depends_on:")
    assert first != rels.create(
        relationship_type=EngineeringKnowledgeRelationshipType.REQUIRES,
        source_node_id=source,
        target_node_id=target,
    )
    assert first != rels.create(
        relationship_type=EngineeringKnowledgeRelationshipType.DEPENDS_ON,
        source_node_id=source,
        target_node_id="ekg:runtime:jvm",
    )


def test_property_models_validation_and_round_trip() -> None:
    props = EngineeringKnowledgeProperties(
        canonical_key=" Spring_Boot ",
        name="Spring Boot",
        description="Application framework",
        aliases=["SpringBoot", "spring boot", "SpringBoot"],
        tags=["java", "backend", "java"],
        external_references=["https://spring.io/projects/spring-boot"],
        knowledge_version="3.x",
    )
    assert props.canonical_key == "spring-boot"
    assert props.aliases == ("spring-boot", "springboot")
    assert props.tags == ("backend", "java")
    restored = EngineeringKnowledgeProperties.model_validate_json(props.model_dump_json())
    assert restored == props

    with pytest.raises(ValidationError, match="blank"):
        EngineeringKnowledgeProperties(canonical_key="x", name=" ")
    with pytest.raises(ValidationError, match="blank"):
        EngineeringKnowledgeProperties(canonical_key="x", name="ok", description=" ")
    with pytest.raises(ValidationError):
        RuleProperties(
            canonical_key="java-eol",
            name="Java EOL",
            rationale="Runtime is unsupported",
            confidence=1.5,
        )

    tech = TechnologyProperties(
        canonical_key="java",
        name="Java",
        lifecycle_status=TechnologyLifecycleStatus.MAINTENANCE,
        end_of_support_date=date(2030, 1, 1),
    )
    assert tech.end_of_support_date == date(2030, 1, 1)

    catalog = EngineeringKnowledgeCatalogMetadata(
        catalog_id="codestrata-core",
        catalog_version="1.0.0",
        name="Core",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        source="https://example.com/catalog",
    )
    assert (
        EngineeringKnowledgeCatalogMetadata.model_validate_json(catalog.model_dump_json())
        == catalog
    )
    with pytest.raises(ValidationError, match="timezone-aware"):
        EngineeringKnowledgeCatalogMetadata(
            catalog_id="codestrata-core",
            catalog_version="1.0.0",
            name="Core",
            published_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValidationError, match="credential"):
        EngineeringKnowledgeCatalogMetadata(
            catalog_id="codestrata-core",
            catalog_version="1.0.0",
            name="Core",
            source="https://user:token@example.com/catalog",
        )


def test_node_and_relationship_factories() -> None:
    nodes = EngineeringKnowledgeNodeFactory()
    provenance = (_provenance(),)
    framework = nodes.framework(
        FrameworkProperties(
            canonical_key="spring-boot",
            name="Spring Boot",
            ecosystem="java",
            lifecycle_status=TechnologyLifecycleStatus.CURRENT,
        ),
        provenance=provenance,
    )
    assert framework.node_type == EngineeringKnowledgeNodeType.FRAMEWORK
    assert str(framework.id) == "ekg:framework:spring-boot"
    assert framework.schema_version == ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION
    assert framework.properties["canonical_key"] == "spring-boot"
    assert framework.provenance == provenance

    quality = nodes.quality_attribute(
        QualityAttributeProperties(
            canonical_key="maintainability",
            name="Maintainability",
            definition="Ease of change",
            common_metrics=["cyclomatic-complexity"],
        )
    )
    relationships = EngineeringKnowledgeRelationshipFactory()
    supports = relationships.create(
        relationship_type=EngineeringKnowledgeRelationshipType.SUPPORTS,
        source_node_id=framework.id,
        target_node_id=quality.id,
        provenance=provenance,
    )
    assert supports.id.startswith("ekg-rel:supports:")
    assert supports.source_node_id == framework.id
    assert supports.properties["schema_version"] == relationships.schema_version


@pytest.mark.parametrize(
    ("relationship_type", "source_type", "target_type", "ok"),
    [
        (
            EngineeringKnowledgeRelationshipType.IS_A,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            EngineeringKnowledgeNodeType.TECHNOLOGY,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.IS_A,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            EngineeringKnowledgeNodeType.LANGUAGE,
            False,
        ),
        (
            EngineeringKnowledgeRelationshipType.SUPPORTS,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.SUPPORTS,
            EngineeringKnowledgeNodeType.RULE,
            EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE,
            False,
        ),
        (
            EngineeringKnowledgeRelationshipType.IMPACTS,
            EngineeringKnowledgeNodeType.ANTI_PATTERN,
            EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.IMPACTS,
            EngineeringKnowledgeNodeType.RULE,
            EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE,
            False,
        ),
        (
            EngineeringKnowledgeRelationshipType.MITIGATES,
            EngineeringKnowledgeNodeType.RULE,
            EngineeringKnowledgeNodeType.RISK_TYPE,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.MITIGATES,
            EngineeringKnowledgeNodeType.TECHNOLOGY,
            EngineeringKnowledgeNodeType.RISK_TYPE,
            False,
        ),
        (
            EngineeringKnowledgeRelationshipType.RECOMMENDS,
            EngineeringKnowledgeNodeType.RULE,
            EngineeringKnowledgeNodeType.MODERNIZATION_STRATEGY,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.RECOMMENDS,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            EngineeringKnowledgeNodeType.MODERNIZATION_STRATEGY,
            False,
        ),
        (
            EngineeringKnowledgeRelationshipType.GOVERNED_BY,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            EngineeringKnowledgeNodeType.RULE,
            True,
        ),
        (
            EngineeringKnowledgeRelationshipType.GOVERNED_BY,
            EngineeringKnowledgeNodeType.RULE,
            EngineeringKnowledgeNodeType.FRAMEWORK,
            False,
        ),
    ],
)
def test_schema_relationship_matrix(
    relationship_type: EngineeringKnowledgeRelationshipType,
    source_type: EngineeringKnowledgeNodeType,
    target_type: EngineeringKnowledgeNodeType,
    ok: bool,
) -> None:
    factory = EngineeringKnowledgeNodeFactory()
    source = factory.concept(
        node_type=source_type,
        properties=EngineeringKnowledgeProperties(
            canonical_key=f"source-{source_type}",
            name=f"Source {source_type}",
        ),
    )
    # Quality attribute needs definition when using typed model; use concept for matrix.
    if target_type is EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE:
        target = factory.quality_attribute(
            QualityAttributeProperties(
                canonical_key="qa",
                name="QA",
                definition="definition",
            )
        )
    elif target_type is EngineeringKnowledgeNodeType.RULE:
        target = factory.rule(
            RuleProperties(
                canonical_key="rule",
                name="Rule",
                rationale="because",
            )
        )
    else:
        target = factory.concept(
            node_type=target_type,
            properties=EngineeringKnowledgeProperties(
                canonical_key=f"target-{target_type}",
                name=f"Target {target_type}",
            ),
        )
    relationship = EngineeringKnowledgeRelationshipFactory().create(
        relationship_type=relationship_type,
        source_node_id=source.id,
        target_node_id=target.id,
    )
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(source, target),
        relationships=(relationship,),
    )
    if ok:
        EngineeringKnowledgeGraphSchema.validate(snapshot)
    else:
        with pytest.raises(EngineeringKnowledgeGraphSchemaError, match="invalid"):
            EngineeringKnowledgeGraphSchema.validate(snapshot)


def test_schema_rejects_wrong_type_and_unknown_vocabulary() -> None:
    factory = EngineeringKnowledgeNodeFactory()
    node = factory.technology(
        TechnologyProperties(canonical_key="java", name="Java"),
    )
    with pytest.raises(EngineeringKnowledgeGraphSchemaError, match="graph_type"):
        EngineeringKnowledgeGraphSchema.validate(
            GraphSnapshot(
                metadata=GraphMetadata(
                    graph_id=GraphId("graph:x"),
                    graph_type=GraphType.REPOSITORY,
                    schema_version="1.0.0",
                    generator_version="1",
                    source_fingerprint="fp",
                    generation_mode=GraphGenerationMode.FULL,
                    status=GraphStatus.VALID,
                ),
                nodes=(node,),
            )
        )
    with pytest.raises(EngineeringKnowledgeGraphSchemaError, match="unknown"):
        EngineeringKnowledgeGraphSchema.validate(
            GraphSnapshot(
                metadata=_metadata(),
                nodes=(
                    GraphNode(
                        id=NodeId("ekg:weird:x"),
                        node_type="repository",
                        schema_version="1.0.0",
                    ),
                ),
            )
        )
    with pytest.raises(EngineeringKnowledgeGraphSchemaError, match="unknown"):
        EngineeringKnowledgeGraphSchema.validate(
            GraphSnapshot(
                metadata=_metadata(),
                nodes=(
                    node,
                    factory.concept(
                        node_type=EngineeringKnowledgeNodeType.LANGUAGE,
                        properties=EngineeringKnowledgeProperties(
                            canonical_key="java-lang",
                            name="Java Lang",
                        ),
                    ),
                ),
                relationships=(
                    GraphRelationship(
                        id="bad",
                        relationship_type="contains",
                        source_node_id=node.id,
                        target_node_id=NodeId("ekg:language:java-lang"),
                    ),
                ),
            )
        )


def test_related_to_accepts_valid_pairs_and_aggregate() -> None:
    factory = EngineeringKnowledgeNodeFactory()
    left = factory.concept(
        node_type=EngineeringKnowledgeNodeType.PLATFORM,
        properties=EngineeringKnowledgeProperties(canonical_key="aws", name="AWS"),
    )
    right = factory.concept(
        node_type=EngineeringKnowledgeNodeType.LIBRARY,
        properties=EngineeringKnowledgeProperties(canonical_key="jackson", name="Jackson"),
    )
    relationship = EngineeringKnowledgeRelationshipFactory().create(
        relationship_type=EngineeringKnowledgeRelationshipType.RELATED_TO,
        source_node_id=left.id,
        target_node_id=right.id,
    )
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(left, right),
        relationships=(relationship,),
    )
    graph = EngineeringKnowledgeGraph(snapshot)
    assert graph.nodes is snapshot.nodes
    assert graph.relationships is snapshot.relationships
    with pytest.raises(ValidationError):
        graph.metadata.status = GraphStatus.INVALID  # type: ignore[misc]


def test_valid_knowledge_graph_end_to_end() -> None:
    nodes = EngineeringKnowledgeNodeFactory()
    rels = EngineeringKnowledgeRelationshipFactory()
    java = nodes.technology(TechnologyProperties(canonical_key="java", name="Java"))
    spring = nodes.framework(
        FrameworkProperties(canonical_key="spring-boot", name="Spring Boot", ecosystem="java")
    )
    maintainability = nodes.quality_attribute(
        QualityAttributeProperties(
            canonical_key="maintainability",
            name="Maintainability",
            definition="Ease of change",
        )
    )
    snapshot = GraphSnapshot(
        metadata=_metadata(),
        nodes=(java, spring, maintainability),
        relationships=(
            rels.create(
                relationship_type=EngineeringKnowledgeRelationshipType.IS_A,
                source_node_id=spring.id,
                target_node_id=java.id,
            ),
            rels.create(
                relationship_type=EngineeringKnowledgeRelationshipType.IMPACTS,
                source_node_id=spring.id,
                target_node_id=maintainability.id,
            ),
        ),
    )
    graph = EngineeringKnowledgeGraph(snapshot)
    assert graph.metadata.graph_type is GraphType.ENGINEERING_KNOWLEDGE
    assert len(graph.nodes) == 3
