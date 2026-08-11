"""Technology Inventory presentation models (Epic 3 Slice 3.2).

Reporting-layer only. Projects existing AnalysisResult technologies and
repository facts — does not invent detections or modernization claims.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

TECHNOLOGY_INVENTORY_SECTION_ID = "report.technology_inventory"
TECHNOLOGY_INVENTORY_SECTION_VERSION = "1.0.0"


class TechnologyInventoryFact(BaseModel):
    """One factual technology detection for customer display."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    category: str
    version: str | None = None
    version_state: str = "unavailable"
    source: str | None = None
    evidence_paths: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_label: str = "unavailable"
    limitations: tuple[str, ...] = ()

    @field_validator("name", "category", "version_state", "confidence_label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="technology inventory fact field")

    @field_validator("version", "source", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional technology field")

    @field_validator("evidence_paths", "limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class TechnologyInventoryGroup(BaseModel):
    """Named factual group (languages, frameworks, …). Empty groups are omitted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: str
    title: str
    facts: tuple[TechnologyInventoryFact, ...] = ()

    @field_validator("group_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="inventory group field")

    @field_validator("facts", mode="before")
    @classmethod
    def normalize_facts(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RepositoryCompositionView(BaseModel):
    """Observable repository composition metrics (scanned scope, not production proof)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_files: int | None = None
    source_files: int | None = None
    test_files: int | None = None
    application_count: int | None = None
    modules: tuple[str, ...] = ()
    manifest_paths: tuple[str, ...] = ()
    build_file_paths: tuple[str, ...] = ()
    ecosystems: tuple[str, ...] = ()
    scope_note: str = (
        "Counts reflect files observed during this assessment scan. "
        "They are not a certification of production deployment scope."
    )

    @field_validator("modules", "manifest_paths", "build_file_paths", "ecosystems", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("scope_note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str:
        return require_nonblank(str(value), label="scope_note")


class TechnologyInventorySection(BaseModel):
    """Customer Technology Inventory section payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str = TECHNOLOGY_INVENTORY_SECTION_ID
    section_version: str = TECHNOLOGY_INVENTORY_SECTION_VERSION
    status: str
    status_label: str
    confidence: str
    confidence_label: str
    limitations: tuple[str, ...] = ()
    groups: tuple[TechnologyInventoryGroup, ...] = ()
    composition: RepositoryCompositionView | None = None
    fact_count: int = Field(default=0, ge=0)

    @field_validator(
        "section_id",
        "section_version",
        "status",
        "status_label",
        "confidence",
        "confidence_label",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="technology inventory section field")

    @field_validator("limitations", "groups", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
