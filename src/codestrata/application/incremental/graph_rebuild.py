"""Repository / knowledge / assessment graph merge helpers."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.incremental.errors import IncrementalGraphMergeError
from codestrata.domain.graph.models import GraphNode, GraphRelationship, GraphSnapshot


def nodes_sourced_from_paths(
    snapshot: GraphSnapshot,
    paths: set[str],
) -> set[str]:
    """Return node IDs whose path property or provenance references ``paths``."""

    matched: set[str] = set()
    for node in snapshot.nodes:
        props = dict(node.properties)
        path = props.get("path") or props.get("file_path") or props.get("source_path")
        if isinstance(path, str) and path in paths:
            matched.add(str(node.id))
            continue
        for prov in node.provenance:
            if prov.source_id in paths:
                matched.add(str(node.id))
                break
    return matched


def merge_graph_snapshots(
    previous: GraphSnapshot,
    *,
    remove_node_ids: set[str],
    new_nodes: Sequence[GraphNode],
    new_relationships: Sequence[GraphRelationship],
    metadata: object | None = None,
) -> GraphSnapshot:
    """Deterministically merge graph regions without mutating ``previous``."""

    retained_nodes = {
        str(node.id): node for node in previous.nodes if str(node.id) not in remove_node_ids
    }
    for node in new_nodes:
        key = str(node.id)
        if key in retained_nodes and retained_nodes[key] != node:
            raise IncrementalGraphMergeError(
                "Conflicting duplicate node identity during graph merge",
                reason_code="duplicate_node_id",
                failed_step="graph_merge",
            )
        retained_nodes[key] = node

    known = set(retained_nodes)
    retained_rels: dict[str, GraphRelationship] = {}
    for rel in previous.relationships:
        src = str(rel.source_node_id)
        tgt = str(rel.target_node_id)
        if src in remove_node_ids or tgt in remove_node_ids:
            continue
        if src not in known or tgt not in known:
            raise IncrementalGraphMergeError(
                "Dangling relationship retained during graph merge",
                reason_code="dangling_relationship",
                failed_step="graph_merge",
            )
        retained_rels[rel.id] = rel

    for rel in new_relationships:
        src = str(rel.source_node_id)
        tgt = str(rel.target_node_id)
        if src not in known or tgt not in known:
            raise IncrementalGraphMergeError(
                "New relationship references missing nodes",
                reason_code="dangling_new_relationship",
                failed_step="graph_merge",
            )
        existing = retained_rels.get(rel.id)
        if existing is not None and existing != rel:
            raise IncrementalGraphMergeError(
                "Conflicting duplicate relationship identity during graph merge",
                reason_code="duplicate_edge_id",
                failed_step="graph_merge",
            )
        retained_rels[rel.id] = rel

    meta = metadata if metadata is not None else previous.metadata
    return GraphSnapshot(
        metadata=meta,  # type: ignore[arg-type]
        nodes=tuple(retained_nodes[key] for key in sorted(retained_nodes)),
        relationships=tuple(retained_rels[key] for key in sorted(retained_rels)),
    )
