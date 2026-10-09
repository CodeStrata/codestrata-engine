"""M05–M09 structural metrics over admitted module and file edges."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.formulas import (
    m06_external_edge_ratio,
    m09_centrality,
    serialize_ratio,
)
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.repository_graph.structural import (
    FAN_OUT_THRESHOLD_DEFAULT,
    looks_absolute_path,
)

M05_FORMULA_VERSION = "codestrata.m05.module-cycles.v1"
M06_FORMULA_VERSION = "codestrata.m06.module-coupling.v1"
M07_FORMULA_VERSION = "codestrata.m07.boundary-violations.v1"
M08_FORMULA_VERSION = "codestrata.m08.component-concentration.v1"
M09_FORMULA_VERSION = "codestrata.m09.centrality-reach.v1"
LINE_COUNT_DERIVATION = "nonblank_noncomment_full_line.v1"
CONCENTRATION_SHARE_THRESHOLD = Decimal("0.60")
BUNDLED_BOUNDARY_CONSTRAINT = "forbid:api->internal"


class ModuleEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    edge_type: str
    unknown: bool = False
    relationship_id: str | None = None


class CycleComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    member_ids: tuple[str, ...]
    witness_edge_ids: tuple[str, ...]
    self_loop: bool = False


class ModuleCycleMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = M05_FORMULA_VERSION
    count: int
    components: tuple[CycleComponent, ...]
    member_ids: tuple[str, ...]
    complete: bool
    unresolved_edges: int = 0
    computation: MetricComputation


class ModuleCoupling(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    module_id: str
    fan_in: int
    fan_out: int
    fan_in_ids: tuple[str, ...] = ()
    fan_out_ids: tuple[str, ...] = ()


class ModuleCouplingMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = M06_FORMULA_VERSION
    modules: tuple[ModuleCoupling, ...]
    max_fan_out: MetricComputation
    external_edge_ratio: MetricComputation
    unresolved_excluded: int = 0
    unmapped_excluded: int = 0
    complete: bool
    threshold: int = FAN_OUT_THRESHOLD_DEFAULT
    extra: dict[str, object] = Field(default_factory=dict)


def m05_module_cycles(
    nodes: Sequence[str],
    edges: Sequence[ModuleEdge],
    *,
    complete: bool,
) -> ModuleCycleMetric:
    """Count SCCs of size >1 plus single-node self-loops, each once."""

    adj: dict[str, list[str]] = defaultdict(list)
    known: list[ModuleEdge] = []
    unresolved = 0
    self_loop_nodes: set[str] = set()
    node_set = {item for item in nodes if item}
    id_by_pair: dict[tuple[str, str, str], str] = {}
    for edge in edges:
        node_set.add(edge.source)
        node_set.add(edge.target)
        if edge.unknown:
            unresolved += 1
            continue
        known.append(edge)
        if edge.source == edge.target:
            self_loop_nodes.add(edge.source)
        adj[edge.source].append(edge.target)
        if edge.relationship_id:
            id_by_pair[(edge.source, edge.target, edge.edge_type)] = edge.relationship_id
    components = _tarjan(tuple(sorted(node_set)), adj)
    reported: list[CycleComponent] = []
    members: list[str] = []
    for component in components:
        if len(component) > 1:
            witness = _witness_ids(component, known, id_by_pair, self_loop=False)
            reported.append(
                CycleComponent(
                    member_ids=tuple(component),
                    witness_edge_ids=witness,
                )
            )
            members.extend(component)
            continue
        node = component[0]
        if node in self_loop_nodes:
            witness = _witness_ids((node,), known, id_by_pair, self_loop=True)
            reported.append(
                CycleComponent(
                    member_ids=(node,),
                    witness_edge_ids=witness,
                    self_loop=True,
                )
            )
            members.append(node)
    reported.sort(key=lambda item: item.member_ids)
    unique_members = tuple(sorted(dict.fromkeys(members)))
    count = len(reported)
    status = MetricStatus.VALUE
    reason = None
    if count == 0 and (unresolved or not complete):
        status = MetricStatus.UNKNOWN
        reason = "incomplete_negative_graph"
    computation = MetricComputation(
        status=status,
        value=None if status is MetricStatus.UNKNOWN else Decimal(count),
        serialized=None if status is MetricStatus.UNKNOWN else str(count),
        numerator=count,
        reason=reason,
        extra={
            "member_ids": list(unique_members),
            "unresolved_edges": unresolved,
            "formula_version": M05_FORMULA_VERSION,
        },
    )
    return ModuleCycleMetric(
        count=count,
        components=tuple(reported),
        member_ids=unique_members,
        complete=complete and unresolved == 0,
        unresolved_edges=unresolved,
        computation=computation,
    )


def m06_module_coupling(
    module_ids: Sequence[str],
    edges: Sequence[ModuleEdge],
    *,
    file_import_edges: Sequence[tuple[str, str, str, str]] = (),
    unmapped_excluded: int = 0,
    complete: bool,
    threshold: int = FAN_OUT_THRESHOLD_DEFAULT,
) -> ModuleCouplingMetric:
    """Per-module fan_in/out and the file-import external-edge ratio."""

    modules = tuple(sorted(dict.fromkeys(item for item in module_ids if item)))
    fan_in: dict[str, set[str]] = {module: set() for module in modules}
    fan_out: dict[str, set[str]] = {module: set() for module in modules}
    unresolved = 0
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (edge.source, edge.target, edge.edge_type)
        if key in seen:
            continue
        seen.add(key)
        if edge.unknown:
            unresolved += 1
            continue
        if edge.source == edge.target:
            continue
        if edge.source in fan_out:
            fan_out[edge.source].add(edge.target)
        if edge.target in fan_in:
            fan_in[edge.target].add(edge.source)
    records = tuple(
        ModuleCoupling(
            module_id=module,
            fan_in=len(fan_in[module]),
            fan_out=len(fan_out[module]),
            fan_in_ids=tuple(sorted(fan_in[module])),
            fan_out_ids=tuple(sorted(fan_out[module])),
        )
        for module in modules
    )
    max_out = max((item.fan_out for item in records), default=0)
    max_metric = _max_fan_out_metric(
        max_out,
        unresolved=unresolved,
        complete=complete,
        threshold=threshold,
        module_ids=tuple(item.module_id for item in records if item.fan_out == max_out),
    )
    ratio = m06_external_edge_ratio(file_import_edges)
    return ModuleCouplingMetric(
        modules=records,
        max_fan_out=max_metric,
        external_edge_ratio=ratio,
        unresolved_excluded=unresolved,
        unmapped_excluded=unmapped_excluded,
        complete=complete and unresolved == 0,
        threshold=threshold,
        extra={
            "denominator": ratio.denominator,
            "formula_version": M06_FORMULA_VERSION,
            "edge_ids": [edge.relationship_id for edge in edges if edge.relationship_id],
        },
    )


def _max_fan_out_metric(
    max_out: int,
    *,
    unresolved: int,
    complete: bool,
    threshold: int,
    module_ids: tuple[str, ...],
) -> MetricComputation:
    extra = {
        "lower_bound": bool(unresolved or not complete),
        "module_ids": list(module_ids),
        "threshold": threshold,
        "formula_version": M06_FORMULA_VERSION,
    }
    if unresolved or not complete:
        if max_out > threshold:
            return MetricComputation(
                status=MetricStatus.VALUE,
                value=Decimal(max_out),
                serialized=str(max_out),
                numerator=max_out,
                extra=extra,
            )
        return MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=max_out,
            reason="unresolved_imports_lower_bound",
            extra=extra,
        )
    return MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(max_out),
        serialized=str(max_out),
        numerator=max_out,
        extra=extra,
    )


def _witness_ids(
    members: Sequence[str],
    edges: Sequence[ModuleEdge],
    id_by_pair: dict[tuple[str, str, str], str],
    *,
    self_loop: bool,
) -> tuple[str, ...]:
    member_set = set(members)
    found: list[str] = []
    for edge in edges:
        if edge.source not in member_set or edge.target not in member_set:
            continue
        if self_loop and edge.source != edge.target:
            continue
        identity = (
            edge.relationship_id
            or id_by_pair.get((edge.source, edge.target, edge.edge_type))
            or f"{edge.edge_type}:{edge.source}=>{edge.target}"
        )
        found.append(identity)
    return tuple(sorted(dict.fromkeys(found)))


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


class BoundaryPattern(BaseModel):
    """Explicit local disallow pattern. Absent pattern is not a silent default."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    constraint_id: str
    source_pattern: str
    target_pattern: str
    allowed_directions: tuple[str, ...] = ()
    selector_digest: str | None = None

    @field_validator("constraint_id", "source_pattern", "target_pattern", mode="before")
    @classmethod
    def require_text(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("boundary pattern fields must be nonblank")
        return text

    @field_validator("allowed_directions", mode="before")
    @classmethod
    def direction_tokens(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise ValueError("allowed directions must be a list")
        items = tuple(str(item).strip() for item in value)
        if any(not item or ">" not in item for item in items):
            raise ValueError("allowed directions use source>target")
        return items

    @field_validator("selector_digest", mode="before")
    @classmethod
    def empty_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class BoundaryEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    edge_type: str = "imports"
    unknown: bool = False
    evidence_path: str | None = None


class BoundaryViolation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: str
    source: str
    target: str
    evidence_path: str | None = None


class BoundaryViolationMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = M07_FORMULA_VERSION
    constraint_id: str = ""
    source_pattern: str = ""
    target_pattern: str = ""
    allowed_directions: tuple[str, ...] = ()
    count: int = 0
    violations: tuple[BoundaryViolation, ...] = ()
    computation: MetricComputation


class DirectionConstraint(BaseModel):
    """Explicit allowed layer directions. An empty set does not apply the rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    constraint_id: str
    allowed_directions: tuple[str, ...] = ()
    selector_digest: str | None = None

    @field_validator("constraint_id", mode="before")
    @classmethod
    def require_constraint(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("direction constraint id must be nonblank")
        return text

    @field_validator("allowed_directions", mode="before")
    @classmethod
    def direction_tokens(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise ValueError("allowed directions must be a list")
        items = tuple(str(item).strip() for item in value)
        if any(not item or ">" not in item for item in items):
            raise ValueError("allowed directions use source>target")
        return items

    @field_validator("selector_digest", mode="before")
    @classmethod
    def empty_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ModuleLayer(BaseModel):
    """Caller-supplied layer. Folder names are not turned into layers here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module_id: str
    layer: str

    @field_validator("module_id", "layer", mode="before")
    @classmethod
    def require_text(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("module layer fields must be nonblank")
        return text


class DirectionViolation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: str
    source: str
    target: str
    source_layer: str
    target_layer: str
    evidence_path: str | None = None


class DirectionViolationMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = "codestrata.m07.direction-violations.v1"
    constraint_id: str = ""
    allowed_directions: tuple[str, ...] = ()
    count: int = 0
    violations: tuple[DirectionViolation, ...] = ()
    computation: MetricComputation


class FrameworkSubject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_id: str
    layer: str
    layer_confidence: str
    language: str
    framework_structural: bool


class FrameworkLeakageHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_id: str
    framework: str
    symbol: str
    path: str
    language: str


class FrameworkLeakageMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = "codestrata.architecture.framework-leakage.v1"
    count: int = 0
    hits: tuple[FrameworkLeakageHit, ...] = ()
    computation: MetricComputation


class SourceLineFile(BaseModel):
    """Eligible source whose nonblank noncomment lines feed M08."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: str
    component_id: str = ""
    source_text: str = ""
    generated: bool = False
    readable: bool = True
    comment_prefixes: tuple[str, ...] = ("#", "//", "--")

    @field_validator("relative_path", mode="before")
    @classmethod
    def repository_relative(cls, value: object) -> str:
        text = str(value).replace("\\", "/").strip()
        if not text or looks_absolute_path(text):
            raise ValueError("source files require a repository-relative path")
        return text


class ComponentShare(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: str
    lines: int
    witness_path: str


class ConcentrationMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = M08_FORMULA_VERSION
    derivation: str = LINE_COUNT_DERIVATION
    threshold: str = "0.60"
    components: tuple[ComponentShare, ...] = ()
    max_share: MetricComputation
    full_repo_valid: bool = False
    unmapped_files: int = 0
    unreadable_files: int = 0
    generated_excluded: int = 0


class ReachQuery(BaseModel):
    """dependency_view and traversal are independent inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: str
    universe: tuple[str, ...]
    dependency_view: str
    traversal: str
    max_depth: int = Field(ge=1)
    direction: str = "outgoing"
    edge_types: tuple[str, ...] = ("imports", "depends_on")
    partial_universe: bool = False

    @field_validator("seed", mode="before")
    @classmethod
    def require_seed(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("reach seed is required")
        return text

    @model_validator(mode="after")
    def separate_view_and_traversal(self) -> ReachQuery:
        if self.dependency_view not in {"declared", "resolved"}:
            raise ValueError("dependency_view must be declared or resolved")
        if self.traversal not in {"direct", "transitive"}:
            raise ValueError("traversal must be direct or transitive")
        if self.direction not in {"outgoing", "incoming"}:
            raise ValueError("direction must be outgoing or incoming")
        if self.traversal == "direct" and self.max_depth != 1:
            raise ValueError("direct traversal has max_depth 1")
        if self.traversal == "transitive" and self.max_depth < 1:
            raise ValueError("transitive traversal requires a positive bounded max_depth")
        return self


class ReachMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = M09_FORMULA_VERSION
    seed: str
    dependency_view: str
    traversal: str
    direction: str
    max_depth: int
    edge_types: tuple[str, ...]
    universe: tuple[str, ...]
    reached: tuple[str, ...]
    cutoff: bool
    unknown_edges: bool
    partial_universe: bool
    computation: MetricComputation


class NodeCentrality(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    dependency_view: str
    computation: MetricComputation


def boundary_pattern_match(pattern: str, value: str) -> bool:
    """Same glob as crosses_boundary: exact, prefix/**, or one-segment /*."""

    if pattern == value:
        return True
    if pattern.endswith("/**") and value.startswith(pattern[:-3]):
        return True
    if pattern.endswith("/*"):
        prefix = pattern[:-1]
        rest = value[len(prefix) :] if value.startswith(prefix) else None
        return rest is not None and "/" not in rest
    return False


def boundary_config_fields(
    pattern: BoundaryPattern | None,
) -> dict[str, str | int | float | bool | None]:
    """Stable run-configuration fields. Empty means no declared pattern."""

    fields: dict[str, str | int | float | bool | None]
    if pattern is None:
        fields = {
            "boundary.constraint_id": "",
            "boundary.source_pattern": "",
            "boundary.target_pattern": "",
            "boundary.allowed_directions": "",
            "boundary.selector_digest": "",
        }
        return fields
    fields = {
        "boundary.constraint_id": pattern.constraint_id,
        "boundary.source_pattern": pattern.source_pattern,
        "boundary.target_pattern": pattern.target_pattern,
        "boundary.allowed_directions": ",".join(sorted(pattern.allowed_directions)),
        "boundary.selector_digest": pattern.selector_digest or "",
    }
    return fields


def count_nonblank_noncomment_lines(text: str, prefixes: Sequence[str]) -> int:
    """Count lines that are not blank and not a full-line comment."""

    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in prefixes):
            continue
        count += 1
    return count


def m07_boundary_violations(
    edges: Sequence[BoundaryEdge],
    *,
    pattern: BoundaryPattern | None,
    complete: bool,
) -> BoundaryViolationMetric:
    """Count unique disallowed source-target identities. No pattern is not applicable."""

    if pattern is None:
        computation = MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            numerator=0,
            reason="no_declared_pattern",
            extra={"formula_version": M07_FORMULA_VERSION},
        )
        return BoundaryViolationMetric(computation=computation)
    hits: list[BoundaryViolation] = []
    seen: set[tuple[str, str]] = set()
    unknown_relevant = False
    for edge in edges:
        source_hit = boundary_pattern_match(pattern.source_pattern, edge.source)
        target_hit = boundary_pattern_match(pattern.target_pattern, edge.target)
        if edge.unknown and (source_hit or target_hit):
            unknown_relevant = True
            continue
        if not source_hit or not target_hit or edge.source == edge.target:
            continue
        key = (edge.source, edge.target)
        if key in seen:
            continue
        seen.add(key)
        path = edge.evidence_path
        if path and looks_absolute_path(path):
            path = None
        hits.append(
            BoundaryViolation(
                identity=f"{edge.source}->{edge.target}",
                source=edge.source,
                target=edge.target,
                evidence_path=path,
            )
        )
    hits.sort(key=lambda item: item.identity)
    extra = {
        "constraint_id": pattern.constraint_id,
        "source_pattern": pattern.source_pattern,
        "target_pattern": pattern.target_pattern,
        "allowed_directions": list(sorted(pattern.allowed_directions)),
        "identities": [item.identity for item in hits],
        "formula_version": M07_FORMULA_VERSION,
    }
    if hits:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(len(hits)),
            serialized=str(len(hits)),
            numerator=len(hits),
            extra=extra,
        )
    elif unknown_relevant or not complete:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=0,
            reason="unresolved_relevant_edge",
            extra=extra,
        )
    else:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(0),
            serialized="0",
            numerator=0,
            extra=extra,
        )
    return BoundaryViolationMetric(
        constraint_id=pattern.constraint_id,
        source_pattern=pattern.source_pattern,
        target_pattern=pattern.target_pattern,
        allowed_directions=tuple(sorted(pattern.allowed_directions)),
        count=len(hits),
        violations=tuple(hits),
        computation=computation,
    )


def direction_config_fields(
    constraint: DirectionConstraint | None,
) -> dict[str, str]:
    if constraint is None:
        return {
            "direction.constraint_id": "",
            "direction.allowed_directions": "",
            "direction.selector_digest": "",
        }
    return {
        "direction.constraint_id": constraint.constraint_id,
        "direction.allowed_directions": ",".join(sorted(constraint.allowed_directions)),
        "direction.selector_digest": constraint.selector_digest or "",
    }


def m07_direction_violations(
    edges: Sequence[BoundaryEdge],
    layers: Sequence[ModuleLayer],
    *,
    constraint: DirectionConstraint | None,
    complete: bool,
) -> DirectionViolationMetric:
    """Count unique edges outside an explicit allowed-direction set.

    Same-layer edges are allowed. Missing layers and unresolved edges block a
    clean PASS. A known violation remains FAIL. No declared set is not applicable.
    """

    formula = "codestrata.m07.direction-violations.v1"
    if constraint is None or not constraint.allowed_directions:
        computation = MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            numerator=0,
            reason="no_declared_direction",
            extra={"formula_version": formula},
        )
        return DirectionViolationMetric(computation=computation)
    layer_of = {item.module_id: item.layer for item in layers}
    allowed = set(constraint.allowed_directions)
    hits: list[DirectionViolation] = []
    seen: set[tuple[str, str]] = set()
    unclassified = False
    for edge in edges:
        if edge.unknown:
            unclassified = True
            continue
        source_layer = layer_of.get(edge.source, "")
        target_layer = layer_of.get(edge.target, "")
        if (
            not source_layer
            or not target_layer
            or source_layer in {"unknown", "test"}
            or target_layer in {"unknown", "test"}
        ):
            unclassified = True
            continue
        if source_layer == target_layer or f"{source_layer}>{target_layer}" in allowed:
            continue
        key = (edge.source, edge.target)
        if key in seen:
            continue
        seen.add(key)
        path = edge.evidence_path
        if path and looks_absolute_path(path):
            path = None
        hits.append(
            DirectionViolation(
                identity=f"{edge.source}->{edge.target}",
                source=edge.source,
                target=edge.target,
                source_layer=source_layer,
                target_layer=target_layer,
                evidence_path=path,
            )
        )
    hits.sort(key=lambda item: item.identity)
    extra = {
        "constraint_id": constraint.constraint_id,
        "allowed_directions": list(sorted(allowed)),
        "identities": [item.identity for item in hits],
        "formula_version": formula,
    }
    if hits:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(len(hits)),
            serialized=str(len(hits)),
            numerator=len(hits),
            extra=extra,
        )
    elif unclassified or not complete:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=0,
            reason="unresolved_direction",
            extra=extra,
        )
    else:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(0),
            serialized="0",
            numerator=0,
            extra=extra,
        )
    return DirectionViolationMetric(
        constraint_id=constraint.constraint_id,
        allowed_directions=tuple(sorted(allowed)),
        count=len(hits),
        violations=tuple(hits),
        computation=computation,
    )


def framework_leakage_metric(
    subjects: Sequence[FrameworkSubject],
    hits: Sequence[FrameworkLeakageHit],
) -> FrameworkLeakageMetric:
    """Count structural framework symbols on reliably classified domain units.

    A tier that is not framework-structural cannot prove a clean domain.
    A known structural hit still fails when another domain unit is unscanned.
    """

    formula = "codestrata.architecture.framework-leakage.v1"
    domain = [
        item
        for item in subjects
        if item.layer == "domain" and item.layer_confidence != "low"
    ]
    if not domain:
        computation = MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            numerator=0,
            reason="no_domain_units",
            extra={"formula_version": formula},
        )
        return FrameworkLeakageMetric(computation=computation)
    structural_ids = {item.unit_id for item in domain if item.framework_structural}
    incomplete = tuple(sorted(item.unit_id for item in domain if not item.framework_structural))
    matched: list[FrameworkLeakageHit] = []
    seen: set[tuple[str, str, str, str]] = set()
    for hit in hits:
        if hit.unit_id not in structural_ids:
            continue
        key = (hit.unit_id, hit.framework, hit.symbol, hit.path)
        if key in seen:
            continue
        seen.add(key)
        path = hit.path if not looks_absolute_path(hit.path) else ""
        matched.append(hit.model_copy(update={"path": path}))
    matched.sort(key=lambda item: (item.unit_id, item.framework, item.symbol, item.path))
    extra = {
        "identities": [
            f"{item.unit_id}:{item.framework}:{item.symbol}" for item in matched
        ],
        "incomplete_domain_units": list(incomplete),
        "formula_version": formula,
    }
    if matched:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(len(matched)),
            serialized=str(len(matched)),
            numerator=len(matched),
            extra=extra,
        )
    elif incomplete or not structural_ids:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=0,
            reason="unsupported_framework_tier",
            extra=extra,
        )
    else:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(0),
            serialized="0",
            numerator=0,
            extra=extra,
        )
    return FrameworkLeakageMetric(
        count=len(matched),
        hits=tuple(matched),
        computation=computation,
    )


def m08_component_concentration(
    files: Sequence[SourceLineFile],
) -> ConcentrationMetric:
    """Maximum component share of nonblank noncomment lines. Needs two components."""

    mapped: dict[str, int] = {}
    witness: dict[str, tuple[int, str]] = {}
    file_rows: list[dict[str, object]] = []
    unmapped_files = 0
    unreadable_files = 0
    generated_excluded = 0
    unmapped_lines = 0
    for item in sorted(files, key=lambda row: row.relative_path):
        if item.generated:
            generated_excluded += 1
            file_rows.append(
                {
                    "path": item.relative_path,
                    "component_id": item.component_id,
                    "lines": None,
                    "generated": True,
                    "readable": item.readable,
                }
            )
            continue
        if not item.readable:
            unreadable_files += 1
            file_rows.append(
                {
                    "path": item.relative_path,
                    "component_id": item.component_id,
                    "lines": None,
                    "generated": False,
                    "readable": False,
                }
            )
            continue
        lines = count_nonblank_noncomment_lines(item.source_text, item.comment_prefixes)
        file_rows.append(
            {
                "path": item.relative_path,
                "component_id": item.component_id,
                "lines": lines,
                "generated": False,
                "readable": True,
            }
        )
        if not item.component_id:
            unmapped_files += 1
            unmapped_lines += lines
            continue
        mapped[item.component_id] = mapped.get(item.component_id, 0) + lines
        current = witness.get(item.component_id)
        if (
            current is None
            or lines > current[0]
            or (lines == current[0] and item.relative_path < current[1])
        ):
            witness[item.component_id] = (lines, item.relative_path)
    shares = tuple(
        ComponentShare(
            component_id=component_id,
            lines=mapped[component_id],
            witness_path=witness[component_id][1],
        )
        for component_id in sorted(mapped)
    )
    total = sum(mapped.values())
    partial = unmapped_files > 0 or unreadable_files > 0
    base_extra: dict[str, object] = {
        "derivation": LINE_COUNT_DERIVATION,
        "threshold": "0.60",
        "files": file_rows,
        "membership": [{"component_id": item.component_id, "lines": item.lines} for item in shares],
        "unmapped_files": unmapped_files,
        "unmapped_lines": unmapped_lines,
        "unreadable_files": unreadable_files,
        "generated_excluded": generated_excluded,
        "formula_version": M08_FORMULA_VERSION,
    }
    if len(shares) < 2 or total == 0:
        reason = "fewer_than_two_components" if len(shares) < 2 else "empty_denominator"
        computation = MetricComputation(
            status=MetricStatus.NOT_APPLICABLE,
            numerator=0,
            denominator=total,
            reason=reason,
            extra={**base_extra, "full_repo_valid": False},
        )
        return ConcentrationMetric(
            components=shares,
            max_share=computation,
            full_repo_valid=False,
            unmapped_files=unmapped_files,
            unreadable_files=unreadable_files,
            generated_excluded=generated_excluded,
        )
    max_component = min(shares, key=lambda item: (-item.lines, item.component_id))
    share = Decimal(max_component.lines) / Decimal(total)
    observed = serialize_ratio(share)
    extra = {
        **base_extra,
        "max_component_id": max_component.component_id,
        "witness_path": max_component.witness_path,
        "denominator": total,
        "full_repo_valid": not partial,
    }
    if partial:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=max_component.lines,
            denominator=total,
            value=share,
            serialized=observed,
            reason="partial_observed_share",
            extra=extra,
        )
        return ConcentrationMetric(
            components=shares,
            max_share=computation,
            full_repo_valid=False,
            unmapped_files=unmapped_files,
            unreadable_files=unreadable_files,
            generated_excluded=generated_excluded,
        )
    computation = MetricComputation(
        status=MetricStatus.VALUE,
        numerator=max_component.lines,
        denominator=total,
        value=share,
        serialized=observed,
        extra=extra,
    )
    return ConcentrationMetric(
        components=shares,
        max_share=computation,
        full_repo_valid=True,
        unmapped_files=unmapped_files,
        unreadable_files=unreadable_files,
        generated_excluded=generated_excluded,
    )


def m09_structural_centrality(
    node: str,
    universe: Sequence[str],
    edges: Sequence[ModuleEdge],
    *,
    dependency_view: str,
    partial_universe: bool = False,
    unresolved: bool = False,
) -> NodeCentrality:
    """Incoming-neighbor centrality inside V. Self and parallel edges do not inflate it."""

    incoming: list[str] = []
    saw_unknown = unresolved
    for edge in edges:
        if edge.target != node:
            if edge.unknown:
                saw_unknown = True
            continue
        if edge.unknown:
            saw_unknown = True
            continue
        incoming.append(edge.source)
    base = m09_centrality(node, universe, incoming)
    if base.reason == "node_outside_universe":
        return NodeCentrality(
            node_id=node,
            dependency_view=dependency_view,
            computation=base,
        )
    if partial_universe or saw_unknown:
        reason = "partial_universe" if partial_universe else "unresolved_edges"
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=base.numerator,
            denominator=base.denominator,
            reason=reason,
            extra={
                "lower_bound": base.numerator,
                "observed_serialized": base.serialized,
                "seed_excluded": True,
                "dependency_view": dependency_view,
                "formula_version": M09_FORMULA_VERSION,
            },
        )
        return NodeCentrality(
            node_id=node,
            dependency_view=dependency_view,
            computation=computation,
        )
    extra = dict(base.extra)
    extra.update(
        {
            "seed_excluded": True,
            "dependency_view": dependency_view,
            "formula_version": M09_FORMULA_VERSION,
        }
    )
    return NodeCentrality(
        node_id=node,
        dependency_view=dependency_view,
        computation=base.model_copy(update={"extra": extra}),
    )


def m09_reach(
    edges: Sequence[ModuleEdge],
    query: ReachQuery,
) -> ReachMetric:
    """Unique nodes reached from seed, excluding the seed. Cutoff stays UNKNOWN."""

    _validate_reach_query(query)
    universe = tuple(sorted(dict.fromkeys(item for item in query.universe if item)))
    universe_set = set(universe)
    if query.seed not in universe_set:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=0,
            reason="seed_outside_universe",
            extra={"dependency_view": query.dependency_view, "traversal": query.traversal},
        )
        return ReachMetric(
            seed=query.seed,
            dependency_view=query.dependency_view,
            traversal=query.traversal,
            direction=query.direction,
            max_depth=query.max_depth,
            edge_types=tuple(query.edge_types),
            universe=universe,
            reached=(),
            cutoff=False,
            unknown_edges=False,
            partial_universe=query.partial_universe,
            computation=computation,
        )
    allowed = set(query.edge_types)
    oriented: list[ModuleEdge] = []
    seen: set[tuple[str, str, str, bool]] = set()
    for edge in edges:
        if allowed and edge.edge_type not in allowed:
            continue
        source = edge.target if query.direction == "incoming" else edge.source
        target = edge.source if query.direction == "incoming" else edge.target
        key = (source, target, edge.edge_type, edge.unknown)
        if key in seen:
            continue
        seen.add(key)
        oriented.append(
            ModuleEdge(
                source=source,
                target=target,
                edge_type=edge.edge_type,
                unknown=edge.unknown,
                relationship_id=edge.relationship_id,
            )
        )
    adj: dict[str, list[ModuleEdge]] = defaultdict(list)
    for edge in oriented:
        adj[edge.source].append(edge)
    for source in adj:
        adj[source].sort(key=lambda item: (item.target, item.edge_type, item.unknown))
    reached: dict[str, int] = {}
    visited = {query.seed}
    cutoff = False
    unknown_edges = False
    queue: deque[tuple[str, int]] = deque([(query.seed, 0)])
    while queue:
        node, depth = queue.popleft()
        outgoing = adj.get(node, [])
        if depth >= query.max_depth:
            if outgoing:
                cutoff = True
            continue
        for edge in outgoing:
            if edge.unknown:
                unknown_edges = True
                continue
            neighbor = edge.target
            if neighbor == query.seed and neighbor == edge.source:
                continue
            if neighbor not in universe_set:
                unknown_edges = True
                continue
            if neighbor in visited:
                continue
            visited.add(neighbor)
            reached[neighbor] = depth + 1
            queue.append((neighbor, depth + 1))
    members = tuple(sorted(reached))
    incomplete = cutoff or unknown_edges or query.partial_universe
    if cutoff:
        reason = "traversal_bound_truncated"
    elif unknown_edges:
        reason = "lower_bound_with_unknown_completeness"
    elif query.partial_universe:
        reason = "partial_universe"
    else:
        reason = None
    extra = {
        "seed": query.seed,
        "dependency_view": query.dependency_view,
        "traversal": query.traversal,
        "direction": query.direction,
        "max_depth": query.max_depth,
        "cutoff": cutoff,
        "truncated": cutoff,
        "unknown_edges": unknown_edges,
        "partial_universe": query.partial_universe,
        "lower_bound": len(members),
        "reached": list(members),
        "seed_excluded": query.seed not in members,
        "formula_version": M09_FORMULA_VERSION,
    }
    if incomplete:
        computation = MetricComputation(
            status=MetricStatus.UNKNOWN,
            numerator=len(members),
            reason=reason,
            extra=extra,
        )
    else:
        computation = MetricComputation(
            status=MetricStatus.VALUE,
            value=Decimal(len(members)),
            serialized=str(len(members)),
            numerator=len(members),
            extra=extra,
        )
    return ReachMetric(
        seed=query.seed,
        dependency_view=query.dependency_view,
        traversal=query.traversal,
        direction=query.direction,
        max_depth=query.max_depth,
        edge_types=tuple(query.edge_types),
        universe=universe,
        reached=members,
        cutoff=cutoff,
        unknown_edges=unknown_edges,
        partial_universe=query.partial_universe,
        computation=computation,
    )


def _validate_reach_query(query: ReachQuery) -> None:
    if query.dependency_view not in {"declared", "resolved"}:
        raise ValueError("dependency_view must be declared or resolved")
    if query.traversal not in {"direct", "transitive"}:
        raise ValueError("traversal must be direct or transitive")
    if query.direction not in {"outgoing", "incoming"}:
        raise ValueError("direction must be outgoing or incoming")
    if query.traversal == "direct" and query.max_depth != 1:
        raise ValueError("direct traversal has max_depth 1")
    if query.traversal == "transitive" and query.max_depth < 1:
        raise ValueError("transitive traversal requires a positive bounded max_depth")
