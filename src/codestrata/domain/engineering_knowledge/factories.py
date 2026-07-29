"""Factories for Engineering Knowledge Graph nodes and relationships."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.engineering_knowledge.enums import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
)
from codestrata.domain.engineering_knowledge.ids import (
    EngineeringKnowledgeNodeIdFactory,
    EngineeringKnowledgeRelationshipIdFactory,
)
from codestrata.domain.engineering_knowledge.properties import (
    ArchitectureStyleProperties,
    ConstraintProperties,
    EngineeringKnowledgeCatalogMetadata,
    EngineeringKnowledgeProperties,
    EngineeringPracticeProperties,
    FrameworkProperties,
    KnowledgePropertyModel,
    LanguageProperties,
    ModernizationStrategyProperties,
    PatternProperties,
    PlatformCapabilityProperties,
    QualityAttributeProperties,
    RiskTypeProperties,
    RuleProperties,
    TechnologyProperties,
    properties_mapping,
)
from codestrata.domain.graph.enums import GraphGenerationMode, GraphStatus, GraphType
from codestrata.domain.graph.ids import GraphId, NodeId
from codestrata.domain.graph.models import (
    EvidenceReference,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    Provenance,
)

ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION = "1.0.0"


class EngineeringKnowledgeNodeFactory:
    """Create deterministic ``GraphNode`` values for knowledge concepts."""

    def __init__(
        self,
        *,
        schema_version: str = ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
        id_factory: EngineeringKnowledgeNodeIdFactory | None = None,
    ) -> None:
        self._schema_version = schema_version
        self._ids = id_factory or EngineeringKnowledgeNodeIdFactory()

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def create(
        self,
        *,
        node_type: EngineeringKnowledgeNodeType,
        properties: KnowledgePropertyModel,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return GraphNode(
            id=self._ids.create(
                node_type=node_type,
                canonical_key=properties.canonical_key,
            ),
            node_type=node_type.value,
            schema_version=self._schema_version,
            properties=properties_mapping(properties),
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )

    def technology(
        self,
        properties: TechnologyProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.TECHNOLOGY,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def framework(
        self,
        properties: FrameworkProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.FRAMEWORK,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def language(
        self,
        properties: LanguageProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.LANGUAGE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def architecture_style(
        self,
        properties: ArchitectureStyleProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.ARCHITECTURE_STYLE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def design_pattern(
        self,
        properties: PatternProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.DESIGN_PATTERN,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def anti_pattern(
        self,
        properties: PatternProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.ANTI_PATTERN,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def quality_attribute(
        self,
        properties: QualityAttributeProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.QUALITY_ATTRIBUTE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def engineering_practice(
        self,
        properties: EngineeringPracticeProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.ENGINEERING_PRACTICE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def risk_type(
        self,
        properties: RiskTypeProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.RISK_TYPE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def modernization_strategy(
        self,
        properties: ModernizationStrategyProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.MODERNIZATION_STRATEGY,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def rule(
        self,
        properties: RuleProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.RULE,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def constraint(
        self,
        properties: ConstraintProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.CONSTRAINT,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def platform_capability(
        self,
        properties: PlatformCapabilityProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return self.create(
            node_type=EngineeringKnowledgeNodeType.PLATFORM_CAPABILITY,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )

    def concept(
        self,
        *,
        node_type: EngineeringKnowledgeNodeType,
        properties: EngineeringKnowledgeProperties,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        """Create a node for types that use the shared property model."""

        return self.create(
            node_type=node_type,
            properties=properties,
            provenance=provenance,
            evidence=evidence,
        )


class EngineeringKnowledgeRelationshipFactory:
    """Create deterministic knowledge relationships without graph assembly."""

    def __init__(
        self,
        *,
        schema_version: str = ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
        id_factory: EngineeringKnowledgeRelationshipIdFactory | None = None,
    ) -> None:
        self._schema_version = schema_version
        self._ids = id_factory or EngineeringKnowledgeRelationshipIdFactory()

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def create(
        self,
        *,
        relationship_type: EngineeringKnowledgeRelationshipType | str,
        source_node_id: NodeId | str,
        target_node_id: NodeId | str,
        properties: Mapping[str, Any] | None = None,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphRelationship:
        source = (
            source_node_id if isinstance(source_node_id, NodeId) else NodeId(str(source_node_id))
        )
        target = (
            target_node_id if isinstance(target_node_id, NodeId) else NodeId(str(target_node_id))
        )
        rel_type = (
            relationship_type.value
            if isinstance(relationship_type, EngineeringKnowledgeRelationshipType)
            else str(relationship_type)
        )
        relationship_id = self._ids.create(
            relationship_type=rel_type,
            source_node_id=source,
            target_node_id=target,
        )
        payload = dict(properties or {})
        payload.setdefault("schema_version", self._schema_version)
        return GraphRelationship(
            id=relationship_id,
            relationship_type=rel_type,
            source_node_id=source,
            target_node_id=target,
            properties=payload,
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )


def build_engineering_knowledge_metadata(
    catalog: EngineeringKnowledgeCatalogMetadata,
    *,
    schema_version: str = ENGINEERING_KNOWLEDGE_GRAPH_SCHEMA_VERSION,
    generation_mode: GraphGenerationMode = GraphGenerationMode.REUSED,
    status: GraphStatus = GraphStatus.VALID,
) -> GraphMetadata:
    """Build ``GraphMetadata`` for a curated engineering knowledge catalog graph.

    ``REUSED`` denotes curated/imported catalog material rather than repository
    extraction. No timestamps are generated automatically.
    """

    return GraphMetadata(
        graph_id=GraphId(f"graph:ekg:{catalog.catalog_id}:{catalog.catalog_version}"),
        graph_type=GraphType.ENGINEERING_KNOWLEDGE,
        schema_version=schema_version,
        generator_version=catalog.catalog_version,
        source_fingerprint=f"catalog:{catalog.catalog_id}:{catalog.catalog_version}",
        generation_mode=generation_mode,
        status=status,
    )
