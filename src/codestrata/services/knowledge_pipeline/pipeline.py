"""Knowledge Pipeline: bind Repository Graph observations to EKG concepts.

Consumes both graphs and returns an immutable ``KnowledgeBindingResult``.
Never mutates the Repository Graph or Engineering Knowledge Graph.
"""

from __future__ import annotations

from codestrata.domain.engineering_knowledge.models import EngineeringKnowledgeGraph
from codestrata.domain.graph.models import EvidenceReference
from codestrata.domain.knowledge_binding.enums import KnowledgeMatchingStrategy
from codestrata.domain.knowledge_binding.models import (
    KNOWLEDGE_BINDING_RESULT_VERSION,
    KnowledgeBinding,
    KnowledgeBindingResult,
    UnmatchedKnowledgeObservation,
)
from codestrata.domain.repository_graph.models import RepositoryGraph
from codestrata.services.knowledge_pipeline.matching import match_observations
from codestrata.services.knowledge_pipeline.observations import (
    RepositoryKnowledgeObservation,
    extract_repository_observations,
)


class KnowledgePipeline:
    """Deterministic repository-to-knowledge binding service."""

    def bind(
        self,
        repository_graph: RepositoryGraph,
        knowledge_graph: EngineeringKnowledgeGraph,
        *,
        matching_strategy: KnowledgeMatchingStrategy = (
            KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY
        ),
    ) -> KnowledgeBindingResult:
        """Produce deterministic bindings between repository and knowledge graphs.

        ``matching_strategy`` records the primary strategy advertised by this
        run. Exact alias matches may still appear as ``exact_alias`` on
        individual bindings when curated aliases hit.
        """

        if matching_strategy not in {
            KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
            KnowledgeMatchingStrategy.EXACT_ALIAS,
        }:
            raise ValueError(
                f"unsupported knowledge matching strategy '{matching_strategy}'. "
                "This pipeline milestone supports exact canonical/alias matching only."
            )

        observations = extract_repository_observations(repository_graph)
        bindings = match_observations(observations, knowledge_graph)

        considered_ids = tuple(
            sorted(
                {item.repository_node.id for item in observations},
                key=lambda node_id: node_id.root,
            )
        )
        matched_repo_ids = {binding.repository_node_id.root for binding in bindings}
        unmatched = tuple(
            node_id for node_id in considered_ids if node_id.root not in matched_repo_ids
        )
        unmatched_observations = _unmatched_observations(observations, bindings)

        return KnowledgeBindingResult(
            result_version=KNOWLEDGE_BINDING_RESULT_VERSION,
            repository_graph_id=repository_graph.metadata.graph_id,
            repository_source_fingerprint=repository_graph.metadata.source_fingerprint,
            knowledge_graph_id=knowledge_graph.metadata.graph_id,
            knowledge_source_fingerprint=knowledge_graph.metadata.source_fingerprint,
            matching_strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
            bindings=bindings,
            considered_repository_node_ids=considered_ids,
            unmatched_repository_node_ids=unmatched,
            unmatched_observations=unmatched_observations,
        )


def bind_repository_knowledge(
    repository_graph: RepositoryGraph,
    knowledge_graph: EngineeringKnowledgeGraph,
) -> KnowledgeBindingResult:
    """Convenience wrapper around :class:`KnowledgePipeline.bind`."""

    return KnowledgePipeline().bind(repository_graph, knowledge_graph)


def _unmatched_observations(
    observations: tuple[RepositoryKnowledgeObservation, ...],
    bindings: tuple[KnowledgeBinding, ...],
) -> tuple[UnmatchedKnowledgeObservation, ...]:
    matched_keys = {
        (
            binding.repository_node_id.root,
            binding.observation_kind,
            binding.matched_key,
        )
        for binding in bindings
    }
    seen: set[tuple[str, str, str]] = set()
    unmatched: list[UnmatchedKnowledgeObservation] = []
    for observation in observations:
        key = (
            observation.repository_node.id.root,
            observation.observation_kind,
            observation.candidate_key,
        )
        if key in matched_keys:
            continue
        dedupe_key = (
            observation.repository_node.id.root,
            observation.observation_kind.value,
            observation.candidate_key,
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unmatched.append(
            UnmatchedKnowledgeObservation(
                repository_node_id=observation.repository_node.id,
                observation_kind=observation.observation_kind,
                candidate_key=observation.candidate_key,
                repository_node_type=observation.repository_node.node_type,
                evidence=(
                    EvidenceReference(
                        evidence_type="repository_graph_observation",
                        source_id=observation.repository_node.id.root,
                        symbol_id=observation.repository_node.id,
                        excerpt=(
                            f"{observation.observation_kind.value}="
                            f"{observation.candidate_key} "
                            f"on {observation.repository_node.node_type}"
                        ),
                    ),
                ),
            )
        )
    return tuple(
        sorted(
            unmatched,
            key=lambda item: (
                item.repository_node_id.root,
                item.observation_kind.value,
                item.candidate_key,
            ),
        )
    )
