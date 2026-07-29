"""Deterministic Assessment Graph builder.

Consumes Repository Graph, Engineering Knowledge Graph, and
``KnowledgeBindingResult`` without mutating any of them.
"""

from __future__ import annotations

from codestrata.domain.assessment_graph import (
    AssessmentBindingProperties,
    AssessmentGraph,
    AssessmentNodeFactory,
    AssessmentRelationshipFactory,
    KnowledgeConceptReferenceProperties,
    RepositoryEntityReferenceProperties,
    build_assessment_graph_metadata,
)
from codestrata.domain.engineering_knowledge import EngineeringKnowledgeGraph
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot
from codestrata.domain.knowledge_binding import KnowledgeBinding, KnowledgeBindingResult
from codestrata.domain.repository_graph import RepositoryGraph
from codestrata.services.assessment_graph.exceptions import AssessmentGraphBuildError


class AssessmentGraphBuilder:
    """Assemble an Assessment Graph from validated knowledge bindings."""

    def __init__(
        self,
        *,
        node_factory: AssessmentNodeFactory | None = None,
        relationship_factory: AssessmentRelationshipFactory | None = None,
    ) -> None:
        self._nodes = node_factory or AssessmentNodeFactory()
        self._relationships = relationship_factory or AssessmentRelationshipFactory()

    def build(
        self,
        *,
        repository_graph: RepositoryGraph,
        knowledge_graph: EngineeringKnowledgeGraph,
        binding_result: KnowledgeBindingResult,
    ) -> AssessmentGraph:
        """Build an Assessment Graph or fail closed on mismatched inputs."""

        self._validate_inputs(
            repository_graph=repository_graph,
            knowledge_graph=knowledge_graph,
            binding_result=binding_result,
        )

        repo_nodes = {node.id.root: node for node in repository_graph.nodes}
        knowledge_nodes = {node.id.root: node for node in knowledge_graph.nodes}

        # Sort bindings for deterministic projection regardless of input order.
        bindings = tuple(sorted(binding_result.bindings, key=lambda item: item.binding_id))

        repo_refs: dict[str, GraphNode] = {}
        knowledge_refs: dict[str, GraphNode] = {}
        relationships_by_id: dict[str, GraphRelationship] = {}

        rg_id = repository_graph.metadata.graph_id.root
        ekg_id = knowledge_graph.metadata.graph_id.root

        for binding in bindings:
            repo_node = repo_nodes.get(binding.repository_node_id.root)
            if repo_node is None:
                raise AssessmentGraphBuildError(
                    "Unknown repository node referenced by binding "
                    f"'{binding.binding_id}': {binding.repository_node_id}"
                )
            knowledge_node = knowledge_nodes.get(binding.knowledge_node_id.root)
            if knowledge_node is None:
                raise AssessmentGraphBuildError(
                    "Unknown knowledge node referenced by binding "
                    f"'{binding.binding_id}': {binding.knowledge_node_id}"
                )

            repo_ref = self._repository_reference(
                repository_graph_id=rg_id,
                repository_node=repo_node,
                binding=binding,
            )
            knowledge_ref = self._knowledge_reference(
                knowledge_graph_id=ekg_id,
                knowledge_node=knowledge_node,
            )
            repo_refs[repo_ref.id.root] = repo_ref
            knowledge_refs[knowledge_ref.id.root] = knowledge_ref

            relationship = self._relationships.binds_to_knowledge(
                source_node_id=repo_ref.id,
                target_node_id=knowledge_ref.id,
                properties=AssessmentBindingProperties(
                    binding_id=binding.binding_id,
                    binding_type=binding.binding_type,
                    confidence=binding.confidence,
                    matching_strategy=binding.matching_strategy,
                    matched_key=binding.matched_key,
                    observation_kind=binding.observation_kind,
                    evidence_references=binding.evidence,
                    binding_provenance=binding.provenance,
                ),
            )
            existing = relationships_by_id.get(relationship.id)
            if existing is None:
                relationships_by_id[relationship.id] = relationship
            elif existing != relationship:
                raise AssessmentGraphBuildError(
                    f"Conflicting Assessment Graph relationship for id '{relationship.id}'"
                )

        nodes = tuple(
            sorted(
                (*repo_refs.values(), *knowledge_refs.values()),
                key=lambda node: node.id.root,
            )
        )
        relationships = tuple(relationships_by_id[key] for key in sorted(relationships_by_id))
        metadata = build_assessment_graph_metadata(
            repository_graph_id=rg_id,
            repository_source_fingerprint=repository_graph.metadata.source_fingerprint,
            knowledge_graph_id=ekg_id,
            knowledge_source_fingerprint=knowledge_graph.metadata.source_fingerprint,
            binding_ids=[binding.binding_id for binding in bindings],
        )
        return AssessmentGraph(
            GraphSnapshot(
                metadata=metadata,
                nodes=nodes,
                relationships=relationships,
            )
        )

    def _validate_inputs(
        self,
        *,
        repository_graph: RepositoryGraph,
        knowledge_graph: EngineeringKnowledgeGraph,
        binding_result: KnowledgeBindingResult,
    ) -> None:
        if binding_result.repository_graph_id != repository_graph.metadata.graph_id:
            raise AssessmentGraphBuildError(
                "KnowledgeBindingResult repository_graph_id "
                f"'{binding_result.repository_graph_id}' does not match supplied "
                f"Repository Graph '{repository_graph.metadata.graph_id}'"
            )
        if (
            binding_result.repository_source_fingerprint
            != repository_graph.metadata.source_fingerprint
        ):
            raise AssessmentGraphBuildError(
                "KnowledgeBindingResult repository_source_fingerprint "
                f"'{binding_result.repository_source_fingerprint}' does not match "
                "supplied Repository Graph fingerprint "
                f"'{repository_graph.metadata.source_fingerprint}'"
            )
        if binding_result.knowledge_graph_id != knowledge_graph.metadata.graph_id:
            raise AssessmentGraphBuildError(
                "KnowledgeBindingResult knowledge_graph_id "
                f"'{binding_result.knowledge_graph_id}' does not match supplied "
                f"Engineering Knowledge Graph '{knowledge_graph.metadata.graph_id}'"
            )
        if (
            binding_result.knowledge_source_fingerprint
            != knowledge_graph.metadata.source_fingerprint
        ):
            raise AssessmentGraphBuildError(
                "KnowledgeBindingResult knowledge_source_fingerprint "
                f"'{binding_result.knowledge_source_fingerprint}' does not match "
                "supplied Engineering Knowledge Graph fingerprint "
                f"'{knowledge_graph.metadata.source_fingerprint}'"
            )

    def _repository_reference(
        self,
        *,
        repository_graph_id: str,
        repository_node: GraphNode,
        binding: KnowledgeBinding,
    ) -> GraphNode:
        return self._nodes.repository_entity_reference(
            RepositoryEntityReferenceProperties(
                source_repository_graph_id=repository_graph_id,
                source_repository_node_id=repository_node.id.root,
                repository_node_type=binding.repository_node_type or repository_node.node_type,
            )
        )

    def _knowledge_reference(
        self,
        *,
        knowledge_graph_id: str,
        knowledge_node: GraphNode,
    ) -> GraphNode:
        canonical = knowledge_node.properties.get("canonical_key")
        canonical_key = canonical if isinstance(canonical, str) else None
        return self._nodes.knowledge_concept_reference(
            KnowledgeConceptReferenceProperties(
                source_knowledge_graph_id=knowledge_graph_id,
                source_knowledge_node_id=knowledge_node.id.root,
                knowledge_node_type=knowledge_node.node_type,
                canonical_key=canonical_key,
            )
        )


def build_assessment_graph(
    *,
    repository_graph: RepositoryGraph,
    knowledge_graph: EngineeringKnowledgeGraph,
    binding_result: KnowledgeBindingResult,
) -> AssessmentGraph:
    """Convenience entry point for Assessment Graph construction."""

    return AssessmentGraphBuilder().build(
        repository_graph=repository_graph,
        knowledge_graph=knowledge_graph,
        binding_result=binding_result,
    )
