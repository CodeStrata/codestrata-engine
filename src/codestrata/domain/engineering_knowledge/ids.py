"""Deterministic Engineering Knowledge Graph identity construction.

Canonical keys are explicitly supplied. Framework identity stays version-stable
(``ekg:framework:spring-boot``); version-specific guidance belongs in properties
or dedicated rule nodes, not in the framework identity itself.
"""

from __future__ import annotations

import re

from codestrata.domain.engineering_knowledge.enums import (
    EngineeringKnowledgeNodeType,
    EngineeringKnowledgeRelationshipType,
)
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import require_nonblank

_MULTI_HYPHEN = re.compile(r"-{2,}")


def normalize_canonical_key(value: str) -> str:
    """Normalize an explicitly supplied knowledge canonical key."""

    key = require_nonblank(value, label="canonical_key").lower()
    if any(ch in key for ch in ("/", "\\", "?", "#", "@")) or "://" in key:
        raise ValueError(
            "canonical_key must not contain path separators, URL fragments, "
            "query strings, or credential material"
        )
    if ":" in key:
        raise ValueError("canonical_key must not contain ':' characters")
    compact = key.replace(" ", "-").replace("_", "-")
    compact = _MULTI_HYPHEN.sub("-", compact).strip("-")
    if not compact:
        raise ValueError("canonical_key must not be blank after normalization")
    return compact


def node_type_slug(node_type: EngineeringKnowledgeNodeType | str) -> str:
    """Return the hyphenated node-type segment used in knowledge node IDs."""

    if isinstance(node_type, EngineeringKnowledgeNodeType):
        raw = node_type.value
    else:
        raw = require_nonblank(str(node_type), label="node_type")
    return raw.replace("_", "-")


class EngineeringKnowledgeNodeIdFactory:
    """Build ``ekg:<node-type>:<canonical-key>`` node identities."""

    def create(
        self,
        *,
        node_type: EngineeringKnowledgeNodeType | str,
        canonical_key: str,
    ) -> NodeId:
        slug = node_type_slug(node_type)
        key = normalize_canonical_key(canonical_key)
        return NodeId(f"ekg:{slug}:{key}")


class EngineeringKnowledgeRelationshipIdFactory:
    """Build ``ekg-rel:<type>:<source>=><target>`` relationship identities."""

    def create(
        self,
        *,
        relationship_type: EngineeringKnowledgeRelationshipType | str,
        source_node_id: NodeId | str,
        target_node_id: NodeId | str,
    ) -> str:
        if isinstance(relationship_type, EngineeringKnowledgeRelationshipType):
            rel_type = relationship_type.value
        else:
            rel_type = require_nonblank(str(relationship_type), label="relationship_type")
        source = (
            source_node_id.root
            if isinstance(source_node_id, NodeId)
            else NodeId(str(source_node_id)).root
        )
        target = (
            target_node_id.root
            if isinstance(target_node_id, NodeId)
            else NodeId(str(target_node_id)).root
        )
        return f"ekg-rel:{rel_type}:{source}=>{target}"
