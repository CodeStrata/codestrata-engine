"""Exact canonical-key matching between repository observations and EKG nodes.

Matching is intentionally narrow: exact canonical keys and curated aliases only.
Fuzzy, embedding, and AI strategies belong in future matcher implementations.

Alias ownership is fail-closed: a normalized alias that maps to more than one
distinct knowledge concept raises ``AmbiguousKnowledgeConceptError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.domain.engineering_knowledge.enums import EngineeringKnowledgeNodeType
from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.engineering_knowledge.models import EngineeringKnowledgeGraph
from codestrata.domain.graph.enums import ProvenanceSource
from codestrata.domain.graph.models import EvidenceReference, GraphNode, Provenance
from codestrata.domain.knowledge_binding.enums import (
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
)
from codestrata.domain.knowledge_binding.models import KnowledgeBinding
from codestrata.services.knowledge_pipeline.exceptions import AmbiguousKnowledgeConceptError
from codestrata.services.knowledge_pipeline.observations import RepositoryKnowledgeObservation

# Technology-concept node types eligible for repository observation binding.
_MATCHABLE_KNOWLEDGE_TYPES = frozenset(
    {
        EngineeringKnowledgeNodeType.TECHNOLOGY.value,
        EngineeringKnowledgeNodeType.FRAMEWORK.value,
        EngineeringKnowledgeNodeType.LIBRARY.value,
        EngineeringKnowledgeNodeType.LANGUAGE.value,
        EngineeringKnowledgeNodeType.RUNTIME.value,
        EngineeringKnowledgeNodeType.BUILD_TOOL.value,
        EngineeringKnowledgeNodeType.PLATFORM.value,
    }
)

_PIPELINE_PROVENANCE = Provenance(
    source_type=ProvenanceSource.DETERMINISTIC_ANALYZER,
    source_id="knowledge-pipeline:exact-canonical:1.1.0",
    extractor_id="knowledge-pipeline",
    extractor_version="1.1.0",
    confidence=1.0,
)


class KnowledgeConceptIndex:
    """Immutable lookup of matchable EKG nodes by canonical key and alias."""

    def __init__(
        self,
        *,
        by_canonical_key: Mapping[str, tuple[GraphNode, ...]],
        by_alias: Mapping[str, tuple[GraphNode, ...]],
        catalog_hint: str | None,
    ) -> None:
        self._by_canonical_key = dict(by_canonical_key)
        self._by_alias = dict(by_alias)
        self._catalog_hint = catalog_hint

    @classmethod
    def from_knowledge_graph(
        cls,
        knowledge_graph: EngineeringKnowledgeGraph,
    ) -> KnowledgeConceptIndex:
        catalog_hint = (
            f"{knowledge_graph.metadata.graph_id.root}"
            f"/{knowledge_graph.metadata.source_fingerprint}"
        )
        by_key: dict[str, list[GraphNode]] = {}
        by_alias: dict[str, list[GraphNode]] = {}
        for node in knowledge_graph.nodes:
            if node.node_type not in _MATCHABLE_KNOWLEDGE_TYPES:
                continue
            canonical = node.properties.get("canonical_key")
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            key = normalize_canonical_key(canonical)
            by_key.setdefault(key, []).append(node)

            aliases = node.properties.get("aliases")
            if isinstance(aliases, list | tuple):
                for alias in aliases:
                    if not isinstance(alias, str) or not alias.strip():
                        continue
                    alias_key = normalize_canonical_key(alias)
                    if alias_key == key:
                        continue
                    by_alias.setdefault(alias_key, []).append(node)

        normalized_aliases: dict[str, tuple[GraphNode, ...]] = {}
        for alias_key, nodes in by_alias.items():
            unique_ids = tuple(sorted({node.id.root for node in nodes}))
            if len(unique_ids) > 1:
                raise AmbiguousKnowledgeConceptError(
                    alias=alias_key,
                    knowledge_node_ids=unique_ids,
                    catalog_hint=catalog_hint,
                )
            # Deduplicate identical node contributions for the same alias.
            deduped = {node.id.root: node for node in nodes}
            normalized_aliases[alias_key] = tuple(
                sorted(deduped.values(), key=lambda item: item.id.root)
            )

        return cls(
            by_canonical_key={
                key: tuple(sorted(nodes, key=lambda item: item.id.root))
                for key, nodes in by_key.items()
            },
            by_alias=normalized_aliases,
            catalog_hint=catalog_hint,
        )

    def match(
        self,
        observation: RepositoryKnowledgeObservation,
    ) -> tuple[KnowledgeBinding, ...]:
        """Return bindings for one observation (may be empty)."""

        bindings: list[KnowledgeBinding] = []
        key = observation.candidate_key
        for knowledge_node in self._by_canonical_key.get(key, ()):
            bindings.append(
                _build_binding(
                    observation=observation,
                    knowledge_node=knowledge_node,
                    matched_key=key,
                    strategy=KnowledgeMatchingStrategy.EXACT_CANONICAL_KEY,
                )
            )
        for knowledge_node in self._by_alias.get(key, ()):
            # Prefer canonical over alias when the same node already matched.
            if any(
                item.knowledge_node_id == knowledge_node.id
                and item.repository_node_id == observation.repository_node.id
                for item in bindings
            ):
                continue
            bindings.append(
                _build_binding(
                    observation=observation,
                    knowledge_node=knowledge_node,
                    matched_key=key,
                    strategy=KnowledgeMatchingStrategy.EXACT_ALIAS,
                )
            )
        return tuple(bindings)


def match_observations(
    observations: Sequence[RepositoryKnowledgeObservation],
    knowledge_graph: EngineeringKnowledgeGraph,
) -> tuple[KnowledgeBinding, ...]:
    """Match all observations and return deduplicated, sorted bindings."""

    index = KnowledgeConceptIndex.from_knowledge_graph(knowledge_graph)
    bindings_by_id: dict[str, KnowledgeBinding] = {}
    for observation in observations:
        for binding in index.match(observation):
            existing = bindings_by_id.get(binding.binding_id)
            if existing is None:
                bindings_by_id[binding.binding_id] = binding
                continue
            if existing != binding:
                raise ValueError(f"conflicting knowledge binding for id '{binding.binding_id}'")
    return tuple(bindings_by_id[key] for key in sorted(bindings_by_id))


def _build_binding(
    *,
    observation: RepositoryKnowledgeObservation,
    knowledge_node: GraphNode,
    matched_key: str,
    strategy: KnowledgeMatchingStrategy,
) -> KnowledgeBinding:
    repo_node = observation.repository_node
    evidence = (
        EvidenceReference(
            evidence_type="repository_graph_observation",
            source_id=repo_node.id.root,
            symbol_id=repo_node.id,
            excerpt=(
                f"{observation.observation_kind.value}={matched_key} on {repo_node.node_type}"
            ),
        ),
    )
    return KnowledgeBinding.create(
        repository_node_id=repo_node.id,
        knowledge_node_id=knowledge_node.id,
        binding_type=KnowledgeBindingType.USES_CONCEPT,
        confidence=1.0,
        matching_strategy=strategy,
        matched_key=matched_key,
        observation_kind=observation.observation_kind,
        repository_node_type=repo_node.node_type,
        knowledge_node_type=knowledge_node.node_type,
        evidence=evidence,
        provenance=(_PIPELINE_PROVENANCE,),
    )
