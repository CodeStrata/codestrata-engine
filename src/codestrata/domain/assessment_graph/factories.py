"""Factories for Assessment Graph nodes, relationships, and metadata."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.assessment_graph.enums import (
    AssessmentNodeType,
    AssessmentRelationshipType,
)
from codestrata.domain.assessment_graph.ids import (
    AssessmentNodeIdFactory,
    AssessmentRelationshipIdFactory,
    build_assessment_graph_id,
    build_assessment_source_fingerprint,
)
from codestrata.domain.assessment_graph.properties import (
    AssessmentBindingProperties,
    KnowledgeConceptReferenceProperties,
    RepositoryEntityReferenceProperties,
    properties_mapping,
)
from codestrata.domain.graph.enums import GraphGenerationMode, GraphStatus, GraphType
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.models import (
    EvidenceReference,
    GraphMetadata,
    GraphNode,
    GraphRelationship,
    Provenance,
)

ASSESSMENT_GRAPH_SCHEMA_VERSION = "1.0.0"
ASSESSMENT_GRAPH_GENERATOR_VERSION = "1.0.0"


class AssessmentNodeFactory:
    """Create deterministic Assessment Graph reference nodes."""

    def __init__(
        self,
        *,
        schema_version: str = ASSESSMENT_GRAPH_SCHEMA_VERSION,
        id_factory: AssessmentNodeIdFactory | None = None,
    ) -> None:
        self._schema_version = schema_version
        self._ids = id_factory or AssessmentNodeIdFactory()

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def repository_entity_reference(
        self,
        properties: RepositoryEntityReferenceProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return GraphNode(
            id=self._ids.repository_entity_reference(
                source_repository_graph_id=properties.source_repository_graph_id,
                source_repository_node_id=properties.source_repository_node_id,
            ),
            node_type=AssessmentNodeType.REPOSITORY_ENTITY_REFERENCE.value,
            schema_version=self._schema_version,
            properties=properties_mapping(properties),
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )

    def knowledge_concept_reference(
        self,
        properties: KnowledgeConceptReferenceProperties,
        *,
        provenance: Sequence[Provenance] = (),
        evidence: Sequence[EvidenceReference] = (),
    ) -> GraphNode:
        return GraphNode(
            id=self._ids.knowledge_concept_reference(
                source_knowledge_graph_id=properties.source_knowledge_graph_id,
                source_knowledge_node_id=properties.source_knowledge_node_id,
            ),
            node_type=AssessmentNodeType.KNOWLEDGE_CONCEPT_REFERENCE.value,
            schema_version=self._schema_version,
            properties=properties_mapping(properties),
            provenance=tuple(provenance),
            evidence=tuple(evidence),
        )


class AssessmentRelationshipFactory:
    """Create deterministic Assessment Graph binding relationships."""

    def __init__(
        self,
        *,
        id_factory: AssessmentRelationshipIdFactory | None = None,
    ) -> None:
        self._ids = id_factory or AssessmentRelationshipIdFactory()

    def binds_to_knowledge(
        self,
        *,
        source_node_id: NodeId,
        target_node_id: NodeId,
        properties: AssessmentBindingProperties,
        provenance: Sequence[Provenance] | None = None,
        evidence: Sequence[EvidenceReference] | None = None,
    ) -> GraphRelationship:
        relationship_provenance = (
            tuple(provenance) if provenance is not None else tuple(properties.binding_provenance)
        )
        relationship_evidence = (
            tuple(evidence) if evidence is not None else tuple(properties.evidence_references)
        )
        return GraphRelationship(
            id=self._ids.binds_to_knowledge(binding_id=properties.binding_id),
            relationship_type=AssessmentRelationshipType.BINDS_TO_KNOWLEDGE.value,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            properties=properties_mapping(properties),
            provenance=relationship_provenance,
            evidence=relationship_evidence,
        )


def build_assessment_graph_metadata(
    *,
    repository_graph_id: str,
    repository_source_fingerprint: str,
    knowledge_graph_id: str,
    knowledge_source_fingerprint: str,
    binding_ids: Sequence[str],
    schema_version: str = ASSESSMENT_GRAPH_SCHEMA_VERSION,
    generator_version: str = ASSESSMENT_GRAPH_GENERATOR_VERSION,
    generation_mode: GraphGenerationMode = GraphGenerationMode.FULL,
    status: GraphStatus = GraphStatus.VALID,
) -> GraphMetadata:
    """Build deterministic Assessment Graph metadata from logical inputs."""

    fingerprint = build_assessment_source_fingerprint(
        repository_graph_id=repository_graph_id,
        repository_source_fingerprint=repository_source_fingerprint,
        knowledge_graph_id=knowledge_graph_id,
        knowledge_source_fingerprint=knowledge_source_fingerprint,
        binding_ids=binding_ids,
    )
    return GraphMetadata(
        graph_id=build_assessment_graph_id(source_fingerprint=fingerprint),
        graph_type=GraphType.ASSESSMENT,
        schema_version=schema_version,
        generator_version=generator_version,
        source_fingerprint=fingerprint,
        generation_mode=generation_mode,
        status=status,
    )
