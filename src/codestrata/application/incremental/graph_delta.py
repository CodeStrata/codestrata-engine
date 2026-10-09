"""M29 Graph Delta and Bounded Static Blast Radius.

Computes graph delta between base and candidate graphs, bounded reverse-dependency
static blast radius, test associations (E08.2), and boundary metrics (M07/M27).

Standing rules:
- Impact is possible static reach, never executed-test coverage or runtime probability.
- Traversal follows reverse dependency edges (dependents that depend on changed seeds).
- Traversal is bounded (default depth 4, max 32, node/edge budgets).
- Exceeding budget marks cutoff / lower bound with status UNKNOWN.
- Diamonds and cycles are de-duplicated by stable IDs.
- Missing boundary or test evidence is UNKNOWN, not zero.
  Exact zero requires complete applicable evidence.
- Distinct ordered pairs of crossed boundaries are tracked separately from spread and violations.
- Base and candidate are reported separately; deleted subjects use base evidence.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from codestrata.application.evidence.testing.models import (
    AssociationMetric,
    AssociationRecord,
)
from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.contracts.hotspot import ChangeSummary
from codestrata.domain.graph.models import GraphRelationship, GraphSnapshot
from codestrata.domain.repository_graph.metrics import ModuleEdge
from codestrata.models.scan_comparison import GraphDelta, StaticBlastRadius

DEFAULT_IMPACT_DEPTH = 4
MAX_IMPACT_DEPTH = 32
DEFAULT_MAX_VISITED_NODES = 100000
DEFAULT_MAX_VISITED_EDGES = 500000


def calculate_graph_delta(
    base_graph: Any | None,
    candidate_graph: Any | None,
    *,
    changed_files: Sequence[str] = (),
    file_to_component: Mapping[str, str] | None = None,
) -> GraphDelta:
    """Calculate the delta (added/removed nodes and edges) between base and candidate."""
    base_nodes: dict[str, Any] = {}
    base_edges: dict[str, tuple[str, str, str]] = {}
    cand_nodes: dict[str, Any] = {}
    cand_edges: dict[str, tuple[str, str, str]] = {}
    graph_ids: dict[str, str] = {}

    if base_graph is not None:
        base_nodes, base_edges = _extract_nodes_and_edges(base_graph)
        b_id = getattr(getattr(base_graph, "metadata", None), "graph_id", None)
        if b_id:
            graph_ids["base"] = str(getattr(b_id, "root", b_id))

    if candidate_graph is not None:
        cand_nodes, cand_edges = _extract_nodes_and_edges(candidate_graph)
        c_id = getattr(getattr(candidate_graph, "metadata", None), "graph_id", None)
        if c_id:
            graph_ids["candidate"] = str(getattr(c_id, "root", c_id))

    added_nodes = sorted(set(cand_nodes) - set(base_nodes))
    removed_nodes = sorted(set(base_nodes) - set(cand_nodes))
    added_edges = sorted(set(cand_edges) - set(base_edges))
    removed_edges = sorted(set(base_edges) - set(cand_edges))

    # Detect modified nodes (present in both but properties differ)
    modified_nodes: list[str] = []
    for nid in set(base_nodes) & set(cand_nodes):
        bn = base_nodes[nid]
        cn = cand_nodes[nid]
        if _node_properties_differ(bn, cn):
            modified_nodes.append(nid)

    # Compile changed seeds
    seeds_set = set(added_nodes) | set(removed_nodes) | set(modified_nodes)
    if file_to_component and changed_files:
        for f in changed_files:
            c = file_to_component.get(f)
            if c:
                seeds_set.add(c)

    changed_seeds = sorted(seeds_set)

    return GraphDelta(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        added_edges=added_edges,
        removed_edges=removed_edges,
        changed_seeds=changed_seeds,
        base_node_count=len(base_nodes),
        candidate_node_count=len(cand_nodes),
        base_edge_count=len(base_edges),
        candidate_edge_count=len(cand_edges),
        status="complete",
        graph_ids=graph_ids,
    )


def calculate_static_blast_radius(
    seeds: Sequence[str],
    graph: Any | None,
    *,
    test_associations: (
        AssociationMetric | Sequence[AssociationRecord] | Mapping[str, Sequence[str]] | None
    ) = None,
    test_evidence_complete: bool = True,
    boundaries: Mapping[str, str] | None = None,
    boundary_dimension: str | None = None,
    max_depth: int = DEFAULT_IMPACT_DEPTH,
    max_visited_nodes: int = DEFAULT_MAX_VISITED_NODES,
    max_visited_edges: int = DEFAULT_MAX_VISITED_EDGES,
    graph_side: str = "candidate",
    changed_files: Sequence[str] = (),
    unmapped_files: int = 0,
) -> tuple[StaticBlastRadius, ChangeSummary]:
    """Calculate the bounded reverse-dependency blast radius and canonical ChangeSummary.

    Follows reverse dependency edges: if A -> B (A depends on B) and B changes,
    then A is impacted.
    """
    clean_seeds = tuple(sorted(dict.fromkeys(s for s in seeds if s)))
    effective_max_depth = min(max(1, max_depth), MAX_IMPACT_DEPTH)

    nodes, edges = _extract_nodes_and_edges(graph) if graph is not None else ({}, {})

    # Build reverse dependency adjacency list: target -> list of sources (dependents)
    # Edge A -> B means A depends on B. Reverse edge: B -> A.
    reverse_adj: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    edge_witnesses_map: dict[str, list[str]] = defaultdict(list)

    for edge_id, (source, target, edge_type) in edges.items():
        # Source depends on Target
        reverse_adj[target].append((source, edge_id, edge_type))

    # Sort reverse adjacencies for deterministic BFS
    for k in reverse_adj:
        reverse_adj[k].sort(key=lambda item: (item[0], item[1]))

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    for seed in clean_seeds:
        visited.add(seed)
        queue.append((seed, 0))

    visited_nodes_count = len(visited)
    visited_edges_count = 0
    cutoff = False
    cutoff_reason: str | None = None

    while queue:
        curr_node, curr_depth = queue.popleft()
        outgoing = reverse_adj.get(curr_node, [])

        if curr_depth >= effective_max_depth:
            unvisited_neighbors = [
                neighbor for neighbor, _, _ in outgoing if neighbor not in visited
            ]
            if unvisited_neighbors:
                cutoff = True
                cutoff_reason = "depth_bound_truncated"
            continue

        for neighbor, _edge_id, _edge_type in outgoing:
            visited_edges_count += 1
            if visited_edges_count > max_visited_edges:
                cutoff = True
                cutoff_reason = "edge_budget_exceeded"
                break

            if neighbor not in visited:
                if len(visited) >= max_visited_nodes:
                    cutoff = True
                    cutoff_reason = "node_budget_exceeded"
                    break
                visited.add(neighbor)
                visited_nodes_count = len(visited)
                queue.append((neighbor, curr_depth + 1))

        if cutoff and cutoff_reason in {"node_budget_exceeded", "edge_budget_exceeded"}:
            break

    affected_components = tuple(sorted(visited))
    lower_bound = cutoff

    # Test associations mapping
    affected_test_ids: tuple[str, ...] = ()
    affected_test_count: int | None = None
    test_coverage_status = ResultStatus.PASS

    if test_associations is None:
        test_coverage_status = ResultStatus.UNKNOWN
        affected_test_count = None
        affected_test_ids = ()
    else:
        matched_tests: set[str] = set()
        matched_tests.update(
            _lookup_associated_tests(test_associations, affected_components, changed_files)
        )
        affected_test_ids = tuple(sorted(matched_tests))

        if not test_evidence_complete or lower_bound:
            test_coverage_status = ResultStatus.UNKNOWN
            affected_test_count = len(affected_test_ids) if affected_test_ids else None
        else:
            test_coverage_status = ResultStatus.PASS
            affected_test_count = len(affected_test_ids)

    # Boundary metrics
    boundary_spread_member_ids: tuple[str, ...] = ()
    boundary_spread_count: int | None = None
    boundary_spread_status = ResultStatus.PASS
    crossed_boundary_pairs: tuple[str, ...] = ()
    crossed_boundary_count: int | None = None
    crossed_boundary_status = ResultStatus.PASS

    if boundaries is None or len(boundaries) == 0:
        boundary_spread_status = ResultStatus.UNKNOWN
        boundary_spread_count = None
        crossed_boundary_status = ResultStatus.UNKNOWN
        crossed_boundary_count = None
        resolved_boundary_dim = boundary_dimension
    else:
        resolved_boundary_dim = boundary_dimension or "layers"
        # Boundary spread: distinct declared boundary members containing changed subjects
        spread_members = {boundaries[s] for s in clean_seeds if s in boundaries}
        boundary_spread_member_ids = tuple(sorted(spread_members))
        boundary_spread_count = len(boundary_spread_member_ids)

        has_unmapped = unmapped_files > 0 or any(s not in boundaries for s in clean_seeds)
        boundary_spread_status = ResultStatus.UNKNOWN if has_unmapped else ResultStatus.PASS

        # Distinct ordered pairs of crossed boundaries joined by observed dependency edges
        # within the bounded affected subgraph where source and target membership differ.
        distinct_pairs: set[str] = set()
        affected_set = set(affected_components)

        for _edge_id, (source, target, _edge_type) in edges.items():
            if source in affected_set and target in affected_set:
                b_src = boundaries.get(source)
                b_tgt = boundaries.get(target)
                if b_src and b_tgt and b_src != b_tgt:
                    pair_key = f"{b_src} -> {b_tgt}"
                    distinct_pairs.add(pair_key)
                    witness = f"{source} -> {target}"
                    edge_witnesses_map[pair_key].append(witness)
        crossed_boundary_pairs = tuple(sorted(distinct_pairs))
        crossed_boundary_count = len(crossed_boundary_pairs)

        if has_unmapped:
            boundary_spread_status = ResultStatus.UNKNOWN
            boundary_spread_count = None
            crossed_boundary_status = ResultStatus.UNKNOWN
            crossed_boundary_count = None
            crossed_boundary_pairs = ()
        else:
            boundary_spread_status = ResultStatus.PASS
            crossed_boundary_status = ResultStatus.PASS

    static_blast_radius = StaticBlastRadius(
        seeds=list(clean_seeds),
        traversal_direction="reverse",
        max_depth=effective_max_depth,
        visited_nodes=visited_nodes_count,
        visited_edges=visited_edges_count,
        cutoff=cutoff,
        cutoff_reason=cutoff_reason,
        lower_bound=lower_bound,
        affected_component_ids=list(affected_components),
        affected_component_count=len(affected_components),
        affected_test_ids=list(affected_test_ids),
        affected_test_count=affected_test_count,
        test_coverage_status=test_coverage_status.value,
        boundary_dimension=resolved_boundary_dim,
        boundary_spread_member_ids=list(boundary_spread_member_ids),
        boundary_spread_count=boundary_spread_count,
        boundary_spread_status=boundary_spread_status.value,
        crossed_boundary_pairs=list(crossed_boundary_pairs),
        crossed_boundary_count=crossed_boundary_count,
        crossed_boundary_status=crossed_boundary_status.value,
        edge_witnesses={k: sorted(v) for k, v in edge_witnesses_map.items()},
        graph_side=graph_side,
        unresolved_mappings=[],
    )

    # Change summary mapping coverage
    clean_changed_files = tuple(sorted(dict.fromkeys(f for f in changed_files if f)))
    mapped_count = max(0, len(clean_changed_files) - unmapped_files)
    if clean_changed_files:
        mapping_ratio = mapped_count / len(clean_changed_files)
        mapping_coverage = f"{mapping_ratio:.6f}"
        mapping_coverage_status = ResultStatus.PASS if unmapped_files == 0 else ResultStatus.UNKNOWN
    else:
        mapping_coverage = "1.000000"
        mapping_coverage_status = ResultStatus.PASS

    change_summary = ChangeSummary(
        changed_file_ids=clean_changed_files,
        changed_component_ids=clean_seeds,
        changed_file_count=len(clean_changed_files),
        changed_component_count=len(clean_seeds),
        unmapped_changed_file_count=unmapped_files,
        mapping_coverage=mapping_coverage,
        mapping_coverage_status=mapping_coverage_status,
        boundary_dimension=resolved_boundary_dim,
        boundary_spread_member_ids=boundary_spread_member_ids,
        boundary_spread_count=boundary_spread_count,
        boundary_spread_status=boundary_spread_status,
        crossed_boundary_count=crossed_boundary_count,
        crossed_boundary_pairs=crossed_boundary_pairs,
        crossed_boundary_status=crossed_boundary_status,
        affected_component_ids=affected_components,
        affected_component_count=len(affected_components),
        affected_test_ids=affected_test_ids,
        affected_test_count=affected_test_count,
        visited_nodes=visited_nodes_count,
        visited_edges=visited_edges_count,
        cutoff_reason=cutoff_reason,
        graph_side=graph_side,
        lower_bound=lower_bound,
        narrative_only_context=False,
    )

    return static_blast_radius, change_summary


def _extract_nodes_and_edges(
    graph: Any,
) -> tuple[dict[str, Any], dict[str, tuple[str, str, str]]]:
    """Extract node map and edge map (id -> (source, target, type))."""
    nodes: dict[str, Any] = {}
    edges: dict[str, tuple[str, str, str]] = {}

    if graph is None:
        return nodes, edges

    if isinstance(graph, GraphSnapshot):
        for n in graph.nodes:
            nid = str(getattr(n.id, "root", n.id))
            nodes[nid] = n
        for r in graph.relationships:
            rid = str(r.id)
            src = str(getattr(r.source_node_id, "root", r.source_node_id))
            tgt = str(getattr(r.target_node_id, "root", r.target_node_id))
            edges[rid] = (src, tgt, r.relationship_type)
        return nodes, edges

    # RepositoryGraph wrapper
    if hasattr(graph, "snapshot") and isinstance(graph.snapshot, GraphSnapshot):
        return _extract_nodes_and_edges(graph.snapshot)

    # General object or mapping with nodes and relationships / edges
    if isinstance(graph, Mapping):
        raw_nodes = graph.get("nodes")
        raw_edges = graph.get("relationships") or graph.get("edges")
    else:
        raw_nodes = getattr(graph, "nodes", None)
        raw_edges = getattr(graph, "relationships", None) or getattr(graph, "edges", None)

    if raw_nodes is not None:
        if isinstance(raw_nodes, Mapping):
            for k, v in raw_nodes.items():
                nodes[str(k)] = v
        elif isinstance(raw_nodes, Iterable):
            for item in raw_nodes:
                raw_nid: Any = getattr(item, "id", None) or (
                    item.get("id") if isinstance(item, Mapping) else item
                )
                nodes[str(getattr(raw_nid, "root", raw_nid))] = item

    if raw_edges is not None:
        if isinstance(raw_edges, Mapping):
            for k, v in raw_edges.items():
                if isinstance(v, (list, tuple)) and len(v) >= 2:
                    etype = str(v[2]) if len(v) > 2 else "dependency"
                    edges[str(k)] = (str(v[0]), str(v[1]), etype)
        elif isinstance(raw_edges, Iterable):
            for idx, item in enumerate(raw_edges):
                if isinstance(item, GraphRelationship):
                    rid = str(item.id)
                    src = str(getattr(item.source_node_id, "root", item.source_node_id))
                    tgt = str(getattr(item.target_node_id, "root", item.target_node_id))
                    edges[rid] = (src, tgt, item.relationship_type)
                elif isinstance(item, ModuleEdge):
                    rid = item.relationship_id or f"edge-{idx}"
                    edges[rid] = (item.source, item.target, item.edge_type)
                elif hasattr(item, "source") and hasattr(item, "target"):
                    rid = str(getattr(item, "id", f"edge-{idx}"))
                    src = str(getattr(item.source, "root", item.source))
                    tgt = str(getattr(item.target, "root", item.target))
                    etype = str(getattr(item, "type", "dependency"))
                    edges[rid] = (src, tgt, etype)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    rid = f"edge-{idx}"
                    etype = str(item[2]) if len(item) > 2 else "dependency"
                    edges[rid] = (str(item[0]), str(item[1]), etype)

    return nodes, edges


def _node_properties_differ(node_a: Any, node_b: Any) -> bool:
    props_a = getattr(node_a, "properties", None)
    props_b = getattr(node_b, "properties", None)
    if props_a is not None and props_b is not None:
        return dict(props_a) != dict(props_b)
    return False


def _lookup_associated_tests(
    associations: AssociationMetric | Sequence[AssociationRecord] | Mapping[str, Sequence[str]],
    components: Sequence[str],
    changed_files: Sequence[str],
) -> set[str]:
    """Map components and files to associated test IDs/paths."""
    matched: set[str] = set()
    targets = set(components) | set(changed_files)

    if isinstance(associations, AssociationMetric):
        records = associations.associations
    elif isinstance(associations, Mapping):
        for target in targets:
            if target in associations:
                matched.update(associations[target])
        return matched
    elif isinstance(associations, Sequence):
        records = associations  # type: ignore[assignment]
    else:
        return matched

    for rec in records:
        if isinstance(rec, AssociationRecord):
            is_match = rec.production_path in targets or any(
                target in rec.production_path for target in targets
            )
            if is_match:
                tid = rec.test_id or rec.test_path
                if tid:
                    matched.add(tid)

    return matched
