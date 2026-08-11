"""EvidenceLocation — repository-relative or symbolic location envelope."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import optional_nonblank
from codestrata.domain.traceability.enums import LocationKind, LocationPrecision
from codestrata.domain.traceability.validators import (
    TraceabilityValidationError,
    optional_positive_int,
    optional_traceability_path,
)


class EvidenceLocation(BaseModel):
    """Where evidence was observed.

    File-backed locations use repository-relative POSIX paths via the canonical
    ``domain.repository.paths`` normalizer. Symbolic-only locations may omit
    ``path`` when ``symbolic_reference`` is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    column_start: int | None = Field(default=None, ge=1)
    column_end: int | None = Field(default=None, ge=1)
    symbolic_reference: str | None = None
    location_kind: LocationKind = LocationKind.FILE
    precision: LocationPrecision = LocationPrecision.PATH_ONLY

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> str | None:
        return optional_traceability_path(value)

    @field_validator("symbolic_reference", mode="before")
    @classmethod
    def normalize_symbolic(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="symbolic_reference")

    @field_validator("line_start", "line_end", "column_start", "column_end", mode="before")
    @classmethod
    def normalize_positions(cls, value: object) -> int | None:
        return optional_positive_int(value, label="location position")

    @model_validator(mode="after")
    def validate_location(self) -> EvidenceLocation:
        if self.path is None and self.symbolic_reference is None:
            raise TraceabilityValidationError(
                "EvidenceLocation requires path and/or symbolic_reference"
            )

        if self.path is None:
            if self.location_kind is LocationKind.FILE_SPAN:
                raise TraceabilityValidationError(
                    "file_span locations require a repository-relative path"
                )
            if self.location_kind is LocationKind.FILE:
                object.__setattr__(self, "location_kind", LocationKind.SYMBOLIC)
            if self.precision is LocationPrecision.PATH_ONLY:
                object.__setattr__(self, "precision", LocationPrecision.SYMBOLIC_ONLY)
        elif (
            self.line_start is not None
            and self.location_kind is LocationKind.FILE
        ):
            object.__setattr__(self, "location_kind", LocationKind.FILE_SPAN)

        _validate_span_pair(self.line_start, self.line_end, "line_start", "line_end")
        _validate_span_pair(
            self.column_start, self.column_end, "column_start", "column_end"
        )

        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_start == self.line_end
            and self.column_start is not None
            and self.column_end is not None
            and self.column_end < self.column_start
        ):
            raise TraceabilityValidationError(
                "column_end must be >= column_start on the same line"
            )

        return self


def _validate_span_pair(
    start: int | None,
    end: int | None,
    start_name: str,
    end_name: str,
) -> None:
    if start is None and end is None:
        return
    if start is None or end is None:
        raise TraceabilityValidationError(
            f"{start_name} and {end_name} must both be set"
        )
    if end < start:
        raise TraceabilityValidationError(f"{end_name} must be >= {start_name}")
