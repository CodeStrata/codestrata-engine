"""Bounded graph operators. Cutoff never proves absence; views stay independent."""

from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError
from codestrata.domain.rules.operators.models import (
    CostMeter,
    OperatorCall,
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorResult,
    Truth,
    boolean_result,
    metric_result,
)


def select_graph(call: OperatorCall, context: OperatorContext) -> OperatorGraph:
    view = call.dependency_view
    if view == "declared":
        if context.declared_graph is None:
            raise OperatorEvaluationError(
                "declared dependency view is missing",
                reason_code="missing_view",
                operator=call.operator,
            )
        return context.declared_graph
    if view == "resolved":
        if context.resolved_graph is None:
            raise OperatorEvaluationError(
                "resolved dependency view is missing",
                reason_code="missing_view",
                operator=call.operator,
            )
        return context.resolved_graph
    if context.declared_graph is not None and context.resolved_graph is not None:
        raise OperatorEvaluationError(
            "dependency_view is required when declared and resolved graphs are both present",
            reason_code="ambiguous_view",
            operator=call.operator,
        )
    if context.declared_graph is not None:
        return context.declared_graph
    if context.resolved_graph is not None:
        return context.resolved_graph
    raise OperatorEvaluationError(
        "graph operators require a declared or resolved view",
        reason_code="missing_view",
        operator=call.operator,
    )


def resolve_depth(call: OperatorCall, meter: CostMeter) -> int:
    if call.traversal == "transitive":
        if call.max_depth is None or call.max_depth < 1:
            raise OperatorEvaluationError(
                "transitive traversal requires a positive bounded max_depth",
                reason_code="unbounded_traversal",
                operator=call.operator,
            )
        depth = call.max_depth
    else:
        if call.max_depth not in (None, 1):
            raise OperatorEvaluationError(
                "direct traversal has max_depth 1",
                reason_code="invalid_depth",
                operator=call.operator,
            )
        depth = 1
    if depth > meter.limits.graph_max_depth:
        raise OperatorBudgetError(
            f"max_depth {depth} exceeds graph_max_depth {meter.limits.graph_max_depth}",
            operator=call.operator,
            details={"max_depth": depth, "limit": meter.limits.graph_max_depth},
        )
    return depth


def filtered_edges(graph: OperatorGraph, edge_types: tuple[str, ...]) -> tuple[OperatorEdge, ...]:
    if not edge_types:
        return graph.edges
    allowed = set(edge_types)
    return tuple(edge for edge in graph.edges if edge.edge_type in allowed)


def adjacency(
    edges: tuple[OperatorEdge, ...],
) -> dict[str, list[OperatorEdge]]:
    adj: dict[str, list[OperatorEdge]] = defaultdict(list)
    seen: set[tuple[str, str, str, bool]] = set()
    for edge in edges:
        key = (edge.source, edge.target, edge.edge_type, edge.unknown)
        if key in seen:
            continue
        seen.add(key)
        adj[edge.source].append(edge)
    for source in adj:
        adj[source].sort(key=lambda item: (item.target, item.edge_type, item.unknown))
    return adj


class WalkOutcome:
    def __init__(self) -> None:
        self.reached: dict[str, int] = {}
        self.cutoff = False
        self.unknown_relevant = False
        self.found_target = False


def bounded_walk(
    *,
    seed: str,
    adj: dict[str, list[OperatorEdge]],
    max_depth: int,
    meter: CostMeter,
    operator: str,
    target: str | None = None,
) -> WalkOutcome:
    outcome = WalkOutcome()
    visited: set[str] = {seed}
    meter.visited_nodes = 1
    queue: deque[tuple[str, int]] = deque([(seed, 0)])
    while queue:
        node, depth = queue.popleft()
        outgoing = adj.get(node, [])
        if depth >= max_depth:
            if outgoing:
                outcome.cutoff = True
            continue
        for edge in outgoing:
            meter.visited_edges += 1
            if meter.visited_edges > meter.limits.graph_max_visited_edges:
                raise OperatorBudgetError(
                    "graph edge visit budget exceeded",
                    operator=operator,
                    details={
                        "visited_edges": meter.visited_edges,
                        "limit": meter.limits.graph_max_visited_edges,
                    },
                )
            meter.charge(1, operator=operator)
            if edge.unknown:
                outcome.unknown_relevant = True
                continue
            neighbor = edge.target
            if neighbor == seed and neighbor == edge.source:
                continue
            if target is not None and neighbor == target:
                outcome.found_target = True
                outcome.reached[neighbor] = depth + 1
                return outcome
            if neighbor in visited:
                continue
            visited.add(neighbor)
            meter.visited_nodes += 1
            if meter.visited_nodes > meter.limits.graph_max_visited_nodes:
                raise OperatorBudgetError(
                    "graph node visit budget exceeded",
                    operator=operator,
                    details={
                        "visited_nodes": meter.visited_nodes,
                        "limit": meter.limits.graph_max_visited_nodes,
                    },
                )
            outcome.reached[neighbor] = depth + 1
            queue.append((neighbor, depth + 1))
    return outcome


def op_neighbors(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    seed = _seed(call)
    depth = resolve_depth(call, meter)
    graph = select_graph(call, context)
    walk = bounded_walk(
        seed=seed,
        adj=adjacency(filtered_edges(graph, call.edge_types)),
        max_depth=depth,
        meter=meter,
        operator=call.operator,
    )
    members = tuple(sorted(walk.reached))
    complete = graph.complete and not walk.cutoff and not walk.unknown_relevant
    truth = Truth.TRUE if members else (Truth.UNKNOWN if not complete else Truth.FALSE)
    return boolean_result(
        truth,
        meter=meter,
        cutoff=walk.cutoff,
        complete=complete,
        members=members,
        reason=None if complete else "cutoff_or_unknown_edges",
    )


def op_degree(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    seed = _seed(call)
    graph = select_graph(call, context)
    meter.charge(1, operator=call.operator)
    edges = filtered_edges(graph, call.edge_types)
    neighbors: set[str] = set()
    unknown = False
    for edge in edges:
        if edge.source != seed:
            continue
        if edge.unknown:
            unknown = True
            continue
        if edge.target == seed:
            continue
        neighbors.add(edge.target)
    complete = graph.complete and not unknown
    size = len(neighbors)
    metric = MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(size),
        serialized=str(size),
        numerator=size,
        extra={"members": sorted(neighbors)},
    )
    # Degree is a lower bound when coverage is incomplete; it never becomes a clean zero.
    if not complete and size == 0:
        metric = MetricComputation(status=MetricStatus.UNKNOWN, reason="unknown_edges")
        return metric_result(metric, meter=meter, complete=False, members=())
    return metric_result(metric, meter=meter, complete=complete, members=tuple(sorted(neighbors)))


def op_exists_path(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    seed = _seed(call)
    target = _target(call)
    depth = resolve_depth(call, meter)
    graph = select_graph(call, context)
    walk = bounded_walk(
        seed=seed,
        adj=adjacency(filtered_edges(graph, call.edge_types)),
        max_depth=depth,
        meter=meter,
        operator=call.operator,
        target=target,
    )
    if walk.found_target:
        return boolean_result(
            Truth.TRUE,
            meter=meter,
            cutoff=walk.cutoff,
            complete=True,
            members=(target,),
        )
    if walk.cutoff or walk.unknown_relevant or not graph.complete:
        return boolean_result(
            Truth.UNKNOWN,
            meter=meter,
            cutoff=walk.cutoff,
            complete=False,
            reason="cutoff_never_proves_absence",
        )
    return boolean_result(Truth.FALSE, meter=meter, complete=True)


def op_reachable(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    seed = _seed(call)
    depth = resolve_depth(call, meter)
    graph = select_graph(call, context)
    walk = bounded_walk(
        seed=seed,
        adj=adjacency(filtered_edges(graph, call.edge_types)),
        max_depth=depth,
        meter=meter,
        operator=call.operator,
    )
    members = tuple(sorted(walk.reached))
    complete = graph.complete and not walk.cutoff and not walk.unknown_relevant
    metric = MetricComputation(
        status=MetricStatus.VALUE if complete else MetricStatus.UNKNOWN,
        value=None if not complete else Decimal(len(members)),
        serialized=None if not complete else str(len(members)),
        numerator=len(members),
        reason=None if complete else "lower_bound_with_unknown_completeness",
        extra={"members": list(members), "lower_bound": len(members)},
    )
    truth = Truth.TRUE if members else (Truth.UNKNOWN if not complete else Truth.FALSE)
    return OperatorResult(
        truth=truth,
        metric=metric,
        members=members,
        cutoff=walk.cutoff,
        complete=complete,
        reason=metric.reason,
        cost_units=meter.units,
    )


def op_cycle(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    graph = select_graph(call, context)
    edges = filtered_edges(graph, call.edge_types)
    meter.charge(max(len(edges), 1), operator=call.operator)
    if len(graph.nodes) > meter.limits.graph_max_visited_nodes:
        raise OperatorBudgetError(
            "graph node visit budget exceeded",
            operator=call.operator,
            details={"nodes": len(graph.nodes), "limit": meter.limits.graph_max_visited_nodes},
        )
    adj: dict[str, list[str]] = defaultdict(list)
    self_loops: set[str] = set()
    unknown = False
    node_set = set(graph.nodes)
    for edge in edges:
        node_set.add(edge.source)
        node_set.add(edge.target)
        if edge.unknown:
            unknown = True
            continue
        if edge.source == edge.target:
            self_loops.add(edge.source)
        adj[edge.source].append(edge.target)
    components = _tarjan(tuple(sorted(node_set)), adj)
    cyclic: list[str] = []
    for component in components:
        if len(component) > 1:
            cyclic.extend(component)
    cyclic.extend(sorted(self_loops))
    members = tuple(sorted(dict.fromkeys(cyclic)))
    if members:
        return boolean_result(Truth.TRUE, meter=meter, complete=graph.complete, members=members)
    if unknown or not graph.complete:
        return boolean_result(
            Truth.UNKNOWN,
            meter=meter,
            complete=False,
            reason="incomplete_negative_graph",
        )
    return boolean_result(Truth.FALSE, meter=meter, complete=True)


def op_crosses_boundary(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
) -> OperatorResult:
    source_pattern = call.fact
    target_pattern = call.value
    if not isinstance(source_pattern, str) or not isinstance(target_pattern, str):
        raise OperatorEvaluationError(
            "crosses_boundary requires string source and target patterns",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    graph = select_graph(call, context)
    edges = filtered_edges(graph, call.edge_types)
    meter.charge(max(len(edges), 1), operator=call.operator)
    hits: list[str] = []
    unknown_relevant = False
    for edge in edges:
        source_hit = _glob_match(source_pattern, edge.source)
        target_hit = _glob_match(target_pattern, edge.target)
        if edge.unknown and (source_hit or target_hit):
            unknown_relevant = True
            continue
        if source_hit and target_hit and edge.source != edge.target:
            hits.append(f"{edge.source}->{edge.target}")
    if hits:
        return boolean_result(
            Truth.TRUE,
            meter=meter,
            members=tuple(sorted(dict.fromkeys(hits))),
        )
    if unknown_relevant or not graph.complete:
        return boolean_result(
            Truth.UNKNOWN,
            meter=meter,
            complete=False,
            reason="unresolved_relevant_edge",
        )
    return boolean_result(Truth.FALSE, meter=meter, complete=True)


def _seed(call: OperatorCall) -> str:
    if call.fact:
        return call.fact
    raise OperatorEvaluationError(
        "graph operator requires a seed node in fact",
        reason_code="invalid_operands",
        operator=call.operator,
    )


def _target(call: OperatorCall) -> str:
    if isinstance(call.value, str) and call.value:
        return call.value
    raise OperatorEvaluationError(
        "exists_path requires a target node in value",
        reason_code="invalid_operands",
        operator=call.operator,
    )


def _glob_match(pattern: str, value: str) -> bool:
    if pattern == value:
        return True
    if pattern.endswith("/**") and value.startswith(pattern[:-3]):
        return True
    if pattern.endswith("/*"):
        prefix = pattern[:-1]
        rest = value[len(prefix) :] if value.startswith(prefix) else None
        return rest is not None and "/" not in rest
    return False


def _tarjan(nodes: tuple[str, ...], adj: dict[str, list[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(vertex: str) -> None:
        nonlocal index
        indices[vertex] = index
        low[vertex] = index
        index += 1
        stack.append(vertex)
        on_stack.add(vertex)
        for successor in sorted(set(adj.get(vertex, []))):
            if successor not in indices:
                strongconnect(successor)
                low[vertex] = min(low[vertex], low[successor])
            elif successor in on_stack:
                low[vertex] = min(low[vertex], indices[successor])
        if low[vertex] == indices[vertex]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == vertex:
                    break
            components.append(sorted(component))

    for node in nodes:
        if node not in indices:
            strongconnect(node)
    return components
