"""Deterministic Assessment Graph identity construction."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.ids import GraphId, NodeId
from codestrata.domain.graph.validation import require_nonblank


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_assessment_source_fingerprint(
    *,
    repository_graph_id: str,
    repository_source_fingerprint: str,
    knowledge_graph_id: str,
    knowledge_source_fingerprint: str,
    binding_ids: Sequence[str],
) -> str:
    """Build a deterministic AG fingerprint from logical inputs."""

    lines = [
        f"rg_id:{require_nonblank(repository_graph_id, label='repository_graph_id')}",
        "rg_fp:"
        + require_nonblank(
            repository_source_fingerprint,
            label="repository_source_fingerprint",
        ),
        f"ekg_id:{require_nonblank(knowledge_graph_id, label='knowledge_graph_id')}",
        "ekg_fp:"
        + require_nonblank(
            knowledge_source_fingerprint,
            label="knowledge_source_fingerprint",
        ),
        "bindings:",
        *[f"  {require_nonblank(item, label='binding_id')}" for item in sorted(binding_ids)],
    ]
    return f"sha256:{_digest(chr(10).join(lines))}"


def build_assessment_graph_id(*, source_fingerprint: str) -> GraphId:
    """Derive Assessment Graph identity from its source fingerprint."""

    fingerprint = require_nonblank(source_fingerprint, label="source_fingerprint")
    digest = fingerprint.removeprefix("sha256:")
    return GraphId(f"graph:assessment:{digest}")


class AssessmentNodeIdFactory:
    """Build deterministic Assessment Graph node identities."""

    def repository_entity_reference(
        self,
        *,
        source_repository_graph_id: str,
        source_repository_node_id: str,
    ) -> NodeId:
        payload = (
            "repository_entity_reference\n"
            f"{require_nonblank(source_repository_graph_id, label='source_repository_graph_id')}\n"
            f"{require_nonblank(source_repository_node_id, label='source_repository_node_id')}"
        )
        return NodeId(f"ag:repository-entity-ref:{_digest(payload)}")

    def knowledge_concept_reference(
        self,
        *,
        source_knowledge_graph_id: str,
        source_knowledge_node_id: str,
    ) -> NodeId:
        payload = (
            "knowledge_concept_reference\n"
            f"{require_nonblank(source_knowledge_graph_id, label='source_knowledge_graph_id')}\n"
            f"{require_nonblank(source_knowledge_node_id, label='source_knowledge_node_id')}"
        )
        return NodeId(f"ag:knowledge-concept-ref:{_digest(payload)}")


class AssessmentRelationshipIdFactory:
    """Build deterministic Assessment Graph relationship identities."""

    def binds_to_knowledge(self, *, binding_id: str) -> str:
        compact = require_nonblank(binding_id, label="binding_id")
        return f"ag-rel:binds_to_knowledge:{compact}"
