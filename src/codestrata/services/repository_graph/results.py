"""Extraction result, diagnostics, and statistics contracts.

Extractors emit these values. They intentionally omit ``RepositoryGraph`` and
``GraphSnapshot``; only the assembler constructs those.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.models import GraphNode, GraphRelationship, Provenance
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.repository.paths import RepositoryPath
from codestrata.services.repository_graph.enums import ExtractionDiagnosticSeverity


class ExtractionDiagnostic(BaseModel):
    """Recoverable extractor observation (not raised as an exception)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: ExtractionDiagnosticSeverity
    code: str
    message: str
    path: str | None = None
    extractor_id: str | None = None

    @field_validator("code", "message", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="diagnostic field")

    @field_validator("path", "extractor_id", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_nonblank(str(value), label="optional diagnostic field")


class RepositoryExtractionStatistics(BaseModel):
    """Lightweight counters for one extractor contribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    extractor_id: str
    node_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    diagnostic_count: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)

    @field_validator("extractor_id", mode="before")
    @classmethod
    def normalize_extractor_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="extractor_id")


class RepositoryExtractionResult(BaseModel):
    """Immutable contribution from a single Repository Graph extractor.

    ``deleted_repository_paths`` names inventory paths whose file-owned
    subgraphs must be removed by future incremental graph-update logic. This
    milestone does not mutate an existing graph.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    extractor_id: str
    nodes: tuple[GraphNode, ...] = ()
    relationships: tuple[GraphRelationship, ...] = ()
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()
    statistics: RepositoryExtractionStatistics
    provenance: tuple[Provenance, ...] = ()
    deleted_repository_paths: tuple[RepositoryPath, ...] = ()

    @field_validator("extractor_id", mode="before")
    @classmethod
    def normalize_extractor_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="extractor_id")

    @field_validator(
        "nodes",
        "relationships",
        "diagnostics",
        "provenance",
        "deleted_repository_paths",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("deleted_repository_paths", mode="after")
    @classmethod
    def sort_deleted_paths(cls, value: tuple[RepositoryPath, ...]) -> tuple[RepositoryPath, ...]:
        return tuple(sorted(value, key=lambda path: path.root))
