"""Normalize observed structural edges into Repository Graph IDs and operator views."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.metrics import (
    BoundaryEdge,
    BoundaryPattern,
    BoundaryViolationMetric,
    ConcentrationMetric,
    DirectionConstraint,
    DirectionViolationMetric,
    FrameworkLeakageHit,
    FrameworkLeakageMetric,
    FrameworkSubject,
    ModuleCouplingMetric,
    ModuleCycleMetric,
    ModuleEdge,
    ModuleLayer,
    NodeCentrality,
    ReachMetric,
    ReachQuery,
    SourceLineFile,
    boundary_config_fields,
    direction_config_fields,
    framework_leakage_metric,
    m05_module_cycles,
    m06_module_coupling,
    m07_boundary_violations,
    m07_direction_violations,
    m08_component_concentration,
    m09_reach,
    m09_structural_centrality,
)
from codestrata.domain.repository_graph.relationship_ids import RelationshipIdFactory
from codestrata.domain.repository_graph.structural import (
    FAN_OUT_THRESHOLD_DEFAULT,
    MODULE_COUPLING_EDGE_TYPES,
    AdmittedStructuralEdge,
    DroppedStructuralEdge,
    StructuralEdgeObservation,
    StructuralView,
    admit_structural_edge,
)
from codestrata.domain.rules.operators.models import (
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorLimits,
)

STRUCTURE_NORMALIZER_VERSION = "e07.3.v1"


class FileImportObservation(BaseModel):
    """Resolved file-import endpoints used by the M06 external-edge ratio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_file_id: str
    target_file_id: str
    source_component_id: str = ""
    target_component_id: str = ""


class StructuralNormalizationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observations: tuple[StructuralEdgeObservation, ...] = ()
    module_ids: tuple[str, ...] = ()
    file_imports: tuple[FileImportObservation, ...] = ()
    missing_source_roots: tuple[str, ...] = ()
    declared_source_roots: tuple[str, ...] = ()
    fan_out_threshold: int = FAN_OUT_THRESHOLD_DEFAULT
    boundary_pattern: BoundaryPattern | None = None
    module_layers: tuple[ModuleLayer, ...] = ()
    direction_constraint: DirectionConstraint | None = None
    framework_subjects: tuple[FrameworkSubject, ...] = ()
    framework_hits: tuple[FrameworkLeakageHit, ...] = ()
    notes: tuple[str, ...] = ()
    source_files: tuple[SourceLineFile, ...] = ()
    reach_query: ReachQuery | None = None
    centrality_universe: tuple[str, ...] = ()
    centrality_partial: bool = False
    centrality_view: str = "resolved"


class StructuralGraphEvidence(BaseModel):
    """Admitted structural graph plus architecture metrics for YAML launch rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    normalizer_version: str = STRUCTURE_NORMALIZER_VERSION
    admitted: tuple[AdmittedStructuralEdge, ...]
    dropped: tuple[DroppedStructuralEdge, ...]
    declared_graph: OperatorGraph
    resolved_graph: OperatorGraph
    cycles: ModuleCycleMetric
    coupling: ModuleCouplingMetric
    boundary: BoundaryViolationMetric
    direction: DirectionViolationMetric
    leakage: FrameworkLeakageMetric
    concentration: ConcentrationMetric
    centrality: tuple[NodeCentrality, ...] = ()
    reach: ReachMetric | None = None
    boundary_pattern: BoundaryPattern | None = None
    direction_constraint: DirectionConstraint | None = None
    dependency_paths: dict[str, str] = Field(default_factory=dict)
    facts_digest: str
    limitations: tuple[str, ...] = ()
    complete: bool

    def operator_context(self, limits: OperatorLimits | None = None) -> OperatorContext:
        return OperatorContext(
            declared_graph=self.declared_graph,
            resolved_graph=self.resolved_graph,
            metrics={
                "metric.value": self.coupling.max_fan_out,
                "metric.component_concentration": self.concentration.max_share,
                "metric.direction_violations": self.direction.computation,
                "metric.framework_leakage": self.leakage.computation,
            },
            baseline=boundary_config_fields(self.boundary_pattern),
            limits=limits or OperatorLimits(),
        )


def normalize_structural_edges(
    request: StructuralNormalizationRequest,
    *,
    id_factory: RelationshipIdFactory | None = None,
) -> StructuralGraphEvidence:
    """Admit supported edges, assign stable IDs, and compute cycle/coupling metrics."""

    factory = id_factory or RelationshipIdFactory()
    admitted: list[AdmittedStructuralEdge] = []
    dropped: list[DroppedStructuralEdge] = []
    for observation in request.observations:
        reason = admit_structural_edge(observation)
        if reason is not None:
            dropped.append(DroppedStructuralEdge(observation=observation, reason=reason))
            continue
        unknown = observation.unknown or not observation.resolved
        if observation.edge_type == "calls":
            unknown = False
        relationship_id = factory.create(
            relationship_type=observation.edge_type,
            source_node_id=observation.source_id,
            target_node_id=observation.target_id,
        )
        admitted.append(
            AdmittedStructuralEdge(
                relationship_id=relationship_id,
                edge_type=observation.edge_type,
                source_id=observation.source_id,
                target_id=observation.target_id,
                source_type=observation.source_type,
                target_type=observation.target_type,
                view=observation.view,
                unknown=unknown,
                evidence_path=observation.evidence_path,
                source_root=observation.source_root,
            )
        )
    admitted.sort(key=lambda item: (item.edge_type, item.source_id, item.target_id, item.unknown))
    dropped.sort(
        key=lambda item: (
            item.reason.value,
            item.observation.edge_type,
            item.observation.source_id,
            item.observation.target_id,
        )
    )
    missing_roots = tuple(sorted(dict.fromkeys(request.missing_source_roots)))
    complete = not missing_roots
    declared_graph = _operator_graph(admitted, StructuralView.DECLARED, complete=complete)
    resolved_graph = _operator_graph(admitted, StructuralView.RESOLVED, complete=complete)
    module_edges = _module_edges(admitted)
    module_ids = tuple(sorted(dict.fromkeys(request.module_ids)))
    if not module_ids:
        module_ids = tuple(sorted(_inferred_modules(admitted)))
    cycles = m05_module_cycles(module_ids, module_edges, complete=complete)
    file_edges, unmapped = _file_import_pairs(request.file_imports)
    coupling = m06_module_coupling(
        module_ids,
        module_edges,
        file_import_edges=file_edges,
        unmapped_excluded=unmapped,
        complete=complete,
        threshold=request.fan_out_threshold,
    )
    boundary_edges = _boundary_edges(admitted, StructuralView.RESOLVED)
    graph_complete = complete and not any(item.unknown for item in boundary_edges)
    boundary = m07_boundary_violations(
        boundary_edges,
        pattern=request.boundary_pattern,
        complete=graph_complete,
    )
    direction = m07_direction_violations(
        boundary_edges,
        request.module_layers,
        constraint=request.direction_constraint,
        complete=graph_complete,
    )
    leakage = framework_leakage_metric(request.framework_subjects, request.framework_hits)
    concentration = m08_component_concentration(request.source_files)
    centrality = _centrality(request, admitted)
    reach = _reach(request, admitted)
    limitations = _limitations(
        dropped,
        missing_roots,
        cycles,
        coupling,
        boundary,
        concentration,
        direction,
        leakage,
        request.notes,
    )
    paths = _dependency_paths(admitted)
    payload = {
        "admitted": [item.relationship_id for item in admitted],
        "dropped": [item.reason.value for item in dropped],
        "missing_source_roots": list(missing_roots),
        "cycle_count": cycles.count,
        "max_fan_out": coupling.max_fan_out.serialized,
        "boundary": boundary_config_fields(request.boundary_pattern),
        "boundary_status": boundary.computation.status.value,
        "boundary_count": boundary.count,
        "direction": direction_config_fields(request.direction_constraint),
        "direction_status": direction.computation.status.value,
        "direction_count": direction.count,
        "leakage_status": leakage.computation.status.value,
        "leakage_count": leakage.count,
        "concentration_status": concentration.max_share.status.value,
        "concentration_serialized": concentration.max_share.serialized,
        "reach": None
        if reach is None
        else {
            "seed": reach.seed,
            "dependency_view": reach.dependency_view,
            "traversal": reach.traversal,
            "max_depth": reach.max_depth,
            "cutoff": reach.cutoff,
            "reached": list(reach.reached),
        },
    }
    metrics_known = _metrics_known(boundary, concentration, centrality, reach, direction, leakage)
    return StructuralGraphEvidence(
        admitted=tuple(admitted),
        dropped=tuple(dropped),
        declared_graph=declared_graph,
        resolved_graph=resolved_graph,
        cycles=cycles,
        coupling=coupling,
        boundary=boundary,
        direction=direction,
        leakage=leakage,
        concentration=concentration,
        centrality=centrality,
        reach=reach,
        boundary_pattern=request.boundary_pattern,
        direction_constraint=request.direction_constraint,
        dependency_paths=paths,
        facts_digest=digest_canonical(payload),
        limitations=limitations,
        complete=complete and cycles.complete and coupling.complete and metrics_known,
    )


def _in_view(edge: AdmittedStructuralEdge, view: StructuralView) -> bool:
    if edge.view is StructuralView.BOTH:
        return True
    return edge.view is view


def _operator_graph(
    admitted: Sequence[AdmittedStructuralEdge],
    view: StructuralView,
    *,
    complete: bool,
) -> OperatorGraph:
    selected = [item for item in admitted if _in_view(item, view)]
    nodes = tuple(
        sorted({item.source_id for item in selected} | {item.target_id for item in selected})
    )
    edges = tuple(
        OperatorEdge(
            source=item.source_id,
            target=item.target_id,
            edge_type=item.edge_type,
            unknown=item.unknown,
        )
        for item in selected
    )
    graph_complete = complete and not any(item.unknown for item in selected)
    return OperatorGraph(nodes=nodes, edges=edges, complete=graph_complete)


def _module_edges(admitted: Sequence[AdmittedStructuralEdge]) -> tuple[ModuleEdge, ...]:
    edges: list[ModuleEdge] = []
    for item in admitted:
        if item.edge_type not in MODULE_COUPLING_EDGE_TYPES:
            continue
        if (
            item.source_type is not RepositoryNodeType.MODULE
            or item.target_type is not RepositoryNodeType.MODULE
        ):
            continue
        edges.append(
            ModuleEdge(
                source=item.source_id,
                target=item.target_id,
                edge_type=item.edge_type,
                unknown=item.unknown,
                relationship_id=item.relationship_id,
            )
        )
    return tuple(edges)


def _inferred_modules(admitted: Sequence[AdmittedStructuralEdge]) -> set[str]:
    found: set[str] = set()
    for item in admitted:
        if item.source_type is RepositoryNodeType.MODULE:
            found.add(item.source_id)
        if item.target_type is RepositoryNodeType.MODULE:
            found.add(item.target_id)
    return found


def _file_import_pairs(
    observations: Sequence[FileImportObservation],
) -> tuple[tuple[tuple[str, str, str, str], ...], int]:
    eligible: list[tuple[str, str, str, str]] = []
    unmapped = 0
    seen: set[tuple[str, str]] = set()
    for item in observations:
        key = (item.source_file_id, item.target_file_id)
        if key in seen:
            continue
        seen.add(key)
        if not item.source_component_id or not item.target_component_id:
            unmapped += 1
            continue
        eligible.append(
            (
                item.source_file_id,
                item.target_file_id,
                item.source_component_id,
                item.target_component_id,
            )
        )
    return tuple(eligible), unmapped


def _boundary_edges(
    admitted: Sequence[AdmittedStructuralEdge],
    view: StructuralView,
) -> tuple[BoundaryEdge, ...]:
    edges: list[BoundaryEdge] = []
    for item in admitted:
        if item.edge_type not in MODULE_COUPLING_EDGE_TYPES:
            continue
        if not _in_view(item, view):
            continue
        edges.append(
            BoundaryEdge(
                source=item.source_id,
                target=item.target_id,
                edge_type=item.edge_type,
                unknown=item.unknown,
                evidence_path=item.evidence_path,
            )
        )
    return tuple(edges)


def _dependency_paths(admitted: Sequence[AdmittedStructuralEdge]) -> dict[str, str]:
    buckets: dict[str, list[str]] = {}
    for item in admitted:
        if not item.evidence_path:
            continue
        key = f"{item.source_id}->{item.target_id}"
        buckets.setdefault(key, []).append(item.evidence_path)
    return {key: sorted(values)[0] for key, values in buckets.items()}


def _centrality(
    request: StructuralNormalizationRequest,
    admitted: Sequence[AdmittedStructuralEdge],
) -> tuple[NodeCentrality, ...]:
    if not request.centrality_universe:
        return ()
    view = StructuralView(request.centrality_view)
    edges = tuple(
        ModuleEdge(
            source=item.source,
            target=item.target,
            edge_type=item.edge_type,
            unknown=item.unknown,
        )
        for item in _boundary_edges(admitted, view)
    )
    unresolved = any(item.unknown for item in edges)
    return tuple(
        m09_structural_centrality(
            node,
            request.centrality_universe,
            edges,
            dependency_view=request.centrality_view,
            partial_universe=request.centrality_partial,
            unresolved=unresolved,
        )
        for node in sorted(dict.fromkeys(request.centrality_universe))
    )


def _reach(
    request: StructuralNormalizationRequest,
    admitted: Sequence[AdmittedStructuralEdge],
) -> ReachMetric | None:
    query = request.reach_query
    if query is None:
        return None
    view = StructuralView(query.dependency_view)
    edges = tuple(
        ModuleEdge(
            source=item.source,
            target=item.target,
            edge_type=item.edge_type,
            unknown=item.unknown,
        )
        for item in _boundary_edges(admitted, view)
        if not query.edge_types or item.edge_type in query.edge_types
    )
    return m09_reach(edges, query)


def _metrics_known(
    boundary: BoundaryViolationMetric,
    concentration: ConcentrationMetric,
    centrality: Sequence[NodeCentrality],
    reach: ReachMetric | None,
    direction: DirectionViolationMetric,
    leakage: FrameworkLeakageMetric,
) -> bool:
    if boundary.computation.status is MetricStatus.UNKNOWN:
        return False
    if direction.computation.status is MetricStatus.UNKNOWN:
        return False
    if leakage.computation.status is MetricStatus.UNKNOWN:
        return False
    if concentration.max_share.status is MetricStatus.UNKNOWN:
        return False
    if any(item.computation.status is MetricStatus.UNKNOWN for item in centrality):
        return False
    if reach is not None and reach.computation.status is MetricStatus.UNKNOWN:
        return False
    return True


def _limitations(
    dropped: Sequence[DroppedStructuralEdge],
    missing_roots: Sequence[str],
    cycles: ModuleCycleMetric,
    coupling: ModuleCouplingMetric,
    boundary: BoundaryViolationMetric,
    concentration: ConcentrationMetric,
    direction: DirectionViolationMetric,
    leakage: FrameworkLeakageMetric,
    extra_notes: Sequence[str],
) -> tuple[str, ...]:
    reasons = sorted({item.reason.value for item in dropped})
    notes = [f"dropped:{reason}" for reason in reasons]
    if missing_roots:
        notes.append("partial_source_roots")
    if cycles.unresolved_edges:
        notes.append("unresolved_module_edges")
    if coupling.unresolved_excluded:
        notes.append("unresolved_coupling_edges")
    if coupling.unmapped_excluded:
        notes.append("unmapped_file_imports")
    if coupling.max_fan_out.reason:
        notes.append(coupling.max_fan_out.reason)
    if boundary.computation.reason:
        notes.append(boundary.computation.reason)
    if direction.computation.reason:
        notes.append(direction.computation.reason)
    if leakage.computation.reason:
        notes.append(leakage.computation.reason)
    if concentration.max_share.reason:
        notes.append(concentration.max_share.reason)
    notes.extend(item for item in extra_notes if item)
    return tuple(dict.fromkeys(notes))
