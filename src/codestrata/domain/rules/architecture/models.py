"""Typed architecture analysis view consumed by SharedRules (no I/O)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class ArchitectureUnit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_id: str
    layer: str = "unknown"
    # architectural_module | nested_package | composition_root | registration | unknown
    role: str = "architectural_module"
    # high | medium | low — reliability of layer assignment
    classification_confidence: str = "low"
    path_prefixes: tuple[str, ...] = ()
    file_count: int = Field(default=0, ge=0)
    # Raw nested packages collapsed into this primary unit (deterministic, sorted).
    collapsed_packages: tuple[str, ...] = ()
    primary: bool = True

    @field_validator("unit_id", "layer", "role", "classification_confidence", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="architecture unit field").lower()

    @field_validator("path_prefixes", "collapsed_packages", mode="before")
    @classmethod
    def normalize_prefixes(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class ArchitectureDependencyEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_unit_id: str
    target_unit_id: str
    evidence_paths: tuple[str, ...] = ()
    import_symbols: tuple[str, ...] = ()
    # runtime | type_only | registration | init_aggregation | parent_child | collapsed | unknown
    edge_kind: str = "runtime"
    # included | excluded
    normalization: str = "included"
    exclusion_reason: str | None = None
    raw_source_package: str | None = None
    raw_target_package: str | None = None

    @field_validator(
        "source_unit_id",
        "target_unit_id",
        "edge_kind",
        "normalization",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="edge field").lower()

    @field_validator(
        "exclusion_reason",
        "raw_source_package",
        "raw_target_package",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional edge field")

    @field_validator("evidence_paths", "import_symbols", mode="before")
    @classmethod
    def normalize_seq(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class ArchitectureFrameworkHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit_id: str
    layer: str
    framework: str
    symbol: str
    path: str

    @field_validator("unit_id", "layer", "framework", "symbol", "path", mode="before")
    @classmethod
    def normalize(cls, value: object) -> str:
        return require_nonblank(str(value), label="framework hit field")


class ArchitectureAnalysisView(BaseModel):
    """Precomputed architecture facts for SharedRules (immutable).

    ``units`` / ``edges`` are the *primary architectural graph* after unit
    selection and dependency normalization. Package-level detail remains in
    ``raw_*`` counters and edge provenance fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    units: tuple[ArchitectureUnit, ...] = ()
    edges: tuple[ArchitectureDependencyEdge, ...] = ()
    framework_hits: tuple[ArchitectureFrameworkHit, ...] = ()
    files_considered: int = Field(default=0, ge=0)
    files_parsed: int = Field(default=0, ge=0)
    layer_model: str = "heuristic_path_markers"
    layer_order: tuple[str, ...] = (
        "domain",
        "application",
        "infrastructure",
        "persistence",
        "api",
        "presentation",
        "config",
        "test",
        "unknown",
    )
    allowed_layer_edges: tuple[str, ...] = ()
    # Backward-compatible alias for extraction coverage.
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    graph_fingerprint: str = ""
    unit_selection_policy: str = "top_level_source_packages"
    module_depth: int = Field(default=2, ge=1, le=8)
    raw_package_count: int = Field(default=0, ge=0)
    raw_edge_count: int = Field(default=0, ge=0)
    primary_unit_count: int = Field(default=0, ge=0)
    included_edge_count: int = Field(default=0, ge=0)
    excluded_edge_count: int = Field(default=0, ge=0)
    normalization_notes: tuple[str, ...] = ()

    @property
    def unit_map(self) -> dict[str, ArchitectureUnit]:
        return {unit.unit_id: unit for unit in self.units}

    def primary_units(self) -> tuple[ArchitectureUnit, ...]:
        return tuple(unit for unit in self.units if unit.primary)

    def included_edges(self) -> tuple[ArchitectureDependencyEdge, ...]:
        return tuple(edge for edge in self.edges if edge.normalization == "included")

    def adjacency(self) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {unit.unit_id: [] for unit in self.primary_units()}
        for edge in self.included_edges():
            if edge.source_unit_id not in graph or edge.target_unit_id not in graph:
                continue
            graph.setdefault(edge.source_unit_id, []).append(edge.target_unit_id)
        for key in graph:
            graph[key] = sorted(set(graph[key]))
        return graph
