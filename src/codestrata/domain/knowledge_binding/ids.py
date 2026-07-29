"""Deterministic identities for knowledge bindings."""

from __future__ import annotations

from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.knowledge_binding.enums import KnowledgeMatchingStrategy


def build_knowledge_binding_id(
    *,
    repository_node_id: NodeId | str,
    knowledge_node_id: NodeId | str,
    matching_strategy: KnowledgeMatchingStrategy | str,
    matched_key: str,
) -> str:
    """Build a stable binding identity from endpoints and strategy."""

    repo = (
        repository_node_id.root
        if isinstance(repository_node_id, NodeId)
        else NodeId(str(repository_node_id)).root
    )
    knowledge = (
        knowledge_node_id.root
        if isinstance(knowledge_node_id, NodeId)
        else NodeId(str(knowledge_node_id)).root
    )
    strategy = (
        matching_strategy.value
        if isinstance(matching_strategy, KnowledgeMatchingStrategy)
        else require_nonblank(str(matching_strategy), label="matching_strategy")
    )
    key = normalize_canonical_key(matched_key)
    return f"kb:{strategy}:{repo}=>{knowledge}:{key}"
