"""Deterministic relationship identity construction for Repository Graph."""

from __future__ import annotations

from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.repository_graph.enums import RepositoryRelationshipType


class RelationshipIdFactory:
    """Build stable relationship IDs from type and endpoint node IDs.

    Format: ``rel:<relationship_type>:<source_id>=><target_id>``

    The ``=>`` separator avoids ambiguity because node IDs already contain ``:``.
    IDs are deterministic across runs and contain no random components.
    """

    def create(
        self,
        *,
        relationship_type: RepositoryRelationshipType | str,
        source_node_id: NodeId | str,
        target_node_id: NodeId | str,
    ) -> str:
        rel_type = self._normalize_type(relationship_type)
        source = self._normalize_node_id(source_node_id)
        target = self._normalize_node_id(target_node_id)
        return f"rel:{rel_type}:{source}=>{target}"

    @staticmethod
    def _normalize_type(value: RepositoryRelationshipType | str) -> str:
        if isinstance(value, RepositoryRelationshipType):
            return value.value
        return require_nonblank(str(value), label="relationship_type")

    @staticmethod
    def _normalize_node_id(value: NodeId | str) -> str:
        if isinstance(value, NodeId):
            return value.root
        return NodeId(str(value)).root
