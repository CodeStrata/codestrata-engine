"""Project the Architecture Map from a canonical repository graph.

The renderer may compute layout coordinates. This module does not invent
nodes, edges, component boundaries, centrality, risk, health, or impact.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from codestrata.domain.graph.models import GraphSnapshot
from codestrata.reporting.engineering_health.models import (
    ArchitectureMapEdgeView,
    ArchitectureMapNodeView,
    ArchitectureMapView,
)

CANONICAL_GRAPH_REF_KEY = "canonical_graph_ref"
REPOSITORY_GRAPH_FILENAME = "repository-graph.json"

DISPLAY_NODE_LIMIT = 80
UNAVAILABLE_REASON = "Canonical repository graph is unavailable."
EMPTY_REASON = "Canonical repository graph contains no nodes."
INVALID_REASON = "Canonical repository graph could not be validated."

_MODULE_TYPES = frozenset({"module", "component"})
_DEFAULT_FILE_TYPES = frozenset({"file", "module", "repository"})


def load_repository_graph(metadata: Mapping[str, Any] | None) -> GraphSnapshot | None:
    """Load the sealed repository graph. Returns None when unavailable."""

    if not isinstance(metadata, Mapping):
        return None
    raw = metadata.get("canonical_graph")
    if raw is None:
        raw = metadata.get("repository_graph")
    if isinstance(raw, GraphSnapshot):
        return raw
    if isinstance(raw, Mapping):
        try:
            return GraphSnapshot.model_validate(raw)
        except Exception:
            return None
    ref = metadata.get(CANONICAL_GRAPH_REF_KEY)
    if not isinstance(ref, Mapping):
        return None
    directory = ref.get("directory")
    if not directory:
        return None
    path = Path(str(directory)) / REPOSITORY_GRAPH_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    try:
        return GraphSnapshot.model_validate(payload)
    except Exception:
        return None


def _node_id(node: Any) -> str:
    ident = getattr(node, "id", node)
    root = getattr(ident, "root", ident)
    return str(root)


def _prop(node: Any, key: str) -> str | None:
    props = getattr(node, "properties", None)
    if not isinstance(props, Mapping):
        return None
    value = props.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _label(node: Any) -> str:
    return _prop(node, "name") or _prop(node, "path") or _node_id(node)


def _contains_parent(snapshot: GraphSnapshot) -> dict[str, str]:
    parents: dict[str, str] = {}
    for rel in snapshot.relationships:
        if str(rel.relationship_type) != "contains":
            continue
        source = str(rel.source_node_id.root)
        target = str(rel.target_node_id.root)
        parents.setdefault(target, source)
    return parents


def _subject_keys(node: Any) -> set[str]:
    keys = {_node_id(node)}
    path = _prop(node, "path")
    name = _prop(node, "name")
    if path:
        keys.add(path)
        keys.add(path.replace("\\", "/"))
    if name:
        keys.add(name)
    return keys


def _overlay_ids(
    node: Any,
    *,
    hotspot_subjects: Mapping[str, tuple[str, ...]],
    ownership_subjects: Mapping[str, tuple[str, ...]],
    finding_subjects: Mapping[str, tuple[str, ...]],
    evidence_subjects: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    keys = _subject_keys(node)
    hotspots: list[str] = []
    ownership: list[str] = []
    findings: list[str] = []
    evidence: list[str] = []
    for key in keys:
        hotspots.extend(hotspot_subjects.get(key, ()))
        ownership.extend(ownership_subjects.get(key, ()))
        findings.extend(finding_subjects.get(key, ()))
        evidence.extend(evidence_subjects.get(key, ()))
    return (
        tuple(dict.fromkeys(hotspots)),
        tuple(dict.fromkeys(ownership)),
        tuple(dict.fromkeys(findings)),
        tuple(dict.fromkeys(evidence)),
    )


def _layout(count: int, *, radius: float = 160.0) -> list[tuple[float, float]]:
    """Deterministic renderer-only coordinates. Not a graph metric."""

    if count <= 0:
        return []
    if count == 1:
        return [(0.0, 0.0)]
    coords: list[tuple[float, float]] = []
    for index in range(count):
        angle = (2.0 * math.pi * index) / count - (math.pi / 2.0)
        coords.append((round(math.cos(angle) * radius, 3), round(math.sin(angle) * radius, 3)))
    return coords


def project_architecture_map(
    snapshot: GraphSnapshot | None,
    *,
    hotspot_subjects: Mapping[str, Sequence[str]] | None = None,
    ownership_subjects: Mapping[str, Sequence[str]] | None = None,
    finding_subjects: Mapping[str, Sequence[str]] | None = None,
    evidence_subjects: Mapping[str, Sequence[str]] | None = None,
    display_node_limit: int = DISPLAY_NODE_LIMIT,
) -> ArchitectureMapView:
    """Copy canonical nodes/edges and attach optional existing overlays."""

    if snapshot is None:
        return ArchitectureMapView(available=False, unavailable_reason=UNAVAILABLE_REASON)
    if not snapshot.nodes:
        return ArchitectureMapView(
            available=False,
            unavailable_reason=EMPTY_REASON,
            graph_id=str(snapshot.metadata.graph_id),
            source_fingerprint=snapshot.metadata.source_fingerprint,
            canonical_node_count=0,
            canonical_edge_count=len(snapshot.relationships),
        )

    hotspot_map = {key: tuple(values) for key, values in (hotspot_subjects or {}).items()}
    ownership_map = {key: tuple(values) for key, values in (ownership_subjects or {}).items()}
    finding_map = {key: tuple(values) for key, values in (finding_subjects or {}).items()}
    evidence_map = {key: tuple(values) for key, values in (evidence_subjects or {}).items()}
    parents = _contains_parent(snapshot)

    module_ids = [_node_id(node) for node in snapshot.nodes if str(node.node_type) in _MODULE_TYPES]
    if module_ids:
        grouping = "module"
        preferred = set(module_ids)
    else:
        grouping = "file"
        preferred = {
            _node_id(node) for node in snapshot.nodes if str(node.node_type) in _DEFAULT_FILE_TYPES
        }
        if not preferred:
            preferred = {_node_id(node) for node in snapshot.nodes}

    ordered_preferred = sorted(preferred)
    limited = ordered_preferred[:display_node_limit]
    displayed_ids = set(limited)
    disclosed = len(ordered_preferred) > display_node_limit
    layout = {node_id: point for node_id, point in zip(limited, _layout(len(limited)), strict=True)}

    nodes: list[ArchitectureMapNodeView] = []
    for node in snapshot.nodes:
        node_id = _node_id(node)
        hotspot_ids, ownership_ids, finding_ids, evidence_ids = _overlay_ids(
            node,
            hotspot_subjects=hotspot_map,
            ownership_subjects=ownership_map,
            finding_subjects=finding_map,
            evidence_subjects=evidence_map,
        )
        x, y = layout.get(node_id, (0.0, 0.0))
        nodes.append(
            ArchitectureMapNodeView(
                node_id=node_id,
                node_type=str(node.node_type),
                label=_label(node),
                path=_prop(node, "path"),
                parent_id=parents.get(node_id),
                x=x,
                y=y,
                displayed=node_id in displayed_ids,
                hotspot_record_ids=hotspot_ids,
                ownership_subject_ids=ownership_ids,
                finding_ids=finding_ids,
                evidence_ids=evidence_ids,
            )
        )

    edges: list[ArchitectureMapEdgeView] = []
    for rel in snapshot.relationships:
        source = str(rel.source_node_id.root)
        target = str(rel.target_node_id.root)
        edges.append(
            ArchitectureMapEdgeView(
                edge_id=str(rel.id),
                relationship_type=str(rel.relationship_type),
                source_node_id=source,
                target_node_id=target,
                displayed=source in displayed_ids and target in displayed_ids,
            )
        )

    metadata = snapshot.metadata
    return ArchitectureMapView(
        available=True,
        graph_id=str(metadata.graph_id),
        source_fingerprint=metadata.source_fingerprint,
        canonical_node_count=len(snapshot.nodes),
        canonical_edge_count=len(snapshot.relationships),
        displayed_node_count=len(displayed_ids),
        displayed_edge_count=sum(1 for item in edges if item.displayed),
        display_node_limit=display_node_limit,
        display_limit_disclosed=disclosed,
        grouping=grouping,
        nodes=tuple(nodes),
        edges=tuple(edges),
    )


def unavailable_architecture_map(*, reason: str = UNAVAILABLE_REASON) -> ArchitectureMapView:
    return ArchitectureMapView(available=False, unavailable_reason=reason)


def invalid_architecture_map() -> ArchitectureMapView:
    return ArchitectureMapView(available=False, unavailable_reason=INVALID_REASON)
