"""Facts for E02.1 SQLite / hosted / portfolio tracing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Classification = Literal["retain", "adapt", "deprecate", "quarantine"]


@dataclass(frozen=True, slots=True)
class Surface:
    """One inspected Engine surface and its E02.1 classification."""

    id: str
    classification: Classification
    summary: str
    paths: tuple[str, ...]
    in_supported_runtime: bool
    in_default_dependency_closure: bool


@dataclass(frozen=True, slots=True)
class FactoryComposition:
    """Runtime and source composition of the knowledge-store factory."""

    constructs_class: str
    source_imports_sqlite_store: bool
    return_annotation: str | None
    module: str


@dataclass(frozen=True, slots=True)
class CompositionCall:
    relative_path: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencyInventory:
    default: tuple[str, ...]
    extras: dict[str, tuple[str, ...]]
    forbidden_in_default: tuple[str, ...]
    sqlite3_is_stdlib: bool
    mcp_is_optional_extra: bool


@dataclass(frozen=True, slots=True)
class SnapshotLayout:
    knowledge_directory: str
    database_filename: str
    schema_version: int
    blob_kinds: tuple[str, ...]
    layout_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConsumerHit:
    consumer_root: str
    relative_path: str
    module: str
    lineno: int


@dataclass(frozen=True, slots=True)
class CallPathInventory:
    factory: FactoryComposition
    composition_calls: tuple[CompositionCall, ...]
    sqlite3_production_modules: tuple[str, ...]
    hosted_modules: tuple[str, ...]
    portfolio_modules: tuple[str, ...]
    dependencies: DependencyInventory
    snapshots: SnapshotLayout
    platform_consumers: tuple[ConsumerHit, ...]
    vscode_python_codestrata_imports: int
    workers_codestrata_imports: int
    surfaces: tuple[Surface, ...]
    read_only: bool = True
