"""Normalized language evidence models (provider outputs; not findings)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.capabilities import (
    DependencySemantics,
    SourceClassification,
)
from codestrata.domain.evidence.language.capability_catalog import ProviderCoverageSummary
from codestrata.domain.evidence.language.identifiers import stable_evidence_id
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class SourceUnitEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    unit_id: str
    language: str
    paths: tuple[str, ...] = ()
    layer_hint: str = "unknown"
    layer_confidence: str = "low"
    role_hint: str = "architectural_module"
    classification: SourceClassification = SourceClassification.SOURCE
    file_count: int = Field(default=0, ge=0)
    provenance: EvidenceProvenance

    @field_validator("evidence_id", "unit_id", "language", "layer_hint", "role_hint", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="source unit field").lower()

    @field_validator("paths", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        items = {
            str(item).replace("\\", "/")
            for item in as_tuple(value)
            if str(item).strip()
        }
        return tuple(sorted(items))


class DependencyEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    source_unit_id: str
    target_unit_id: str
    language: str
    semantics: DependencySemantics = DependencySemantics.RUNTIME
    evidence_paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    provenance: EvidenceProvenance

    @field_validator(
        "evidence_id",
        "source_unit_id",
        "target_unit_id",
        "language",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency field").lower()

    @field_validator("evidence_paths", "symbols", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class FrameworkUsageEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    unit_id: str
    language: str
    framework_id: str
    symbol: str
    path: str
    usage_kind: str = "annotation"
    provenance: EvidenceProvenance

    @field_validator(
        "evidence_id",
        "unit_id",
        "language",
        "framework_id",
        "symbol",
        "path",
        "usage_kind",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="framework evidence field")


class LanguageEvidenceBundle(BaseModel):
    """Normalized evidence produced by one provider collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_version: str
    language: str
    source_units: tuple[SourceUnitEvidence, ...] = ()
    dependencies: tuple[DependencyEvidence, ...] = ()
    framework_usages: tuple[FrameworkUsageEvidence, ...] = ()
    coverage: ProviderCoverageSummary = Field(default_factory=ProviderCoverageSummary)
    diagnostics: tuple[str, ...] = ()

    @field_validator("provider_id", "provider_version", "language", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="bundle field").lower()

    @field_validator(
        "source_units",
        "dependencies",
        "framework_usages",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class AggregatedLanguageEvidence(BaseModel):
    """Merged multi-provider evidence for architecture view construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    bundles: tuple[LanguageEvidenceBundle, ...] = ()
    source_units: tuple[SourceUnitEvidence, ...] = ()
    dependencies: tuple[DependencyEvidence, ...] = ()
    framework_usages: tuple[FrameworkUsageEvidence, ...] = ()
    conflicts: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    contributing_provider_ids: tuple[str, ...] = ()

    @field_validator("repository_id", mode="before")
    @classmethod
    def normalize_repo(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_id")

    @field_validator(
        "bundles",
        "source_units",
        "dependencies",
        "framework_usages",
        "conflicts",
        "diagnostics",
        "contributing_provider_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


def make_source_unit_id(*, provider_id: str, unit_id: str, language: str) -> str:
    return stable_evidence_id("source_unit", provider_id, language, unit_id)


def make_dependency_id(
    *,
    provider_id: str,
    source: str,
    target: str,
    semantics: str,
    language: str,
) -> str:
    return stable_evidence_id("dependency", provider_id, language, source, target, semantics)


def make_framework_id(
    *,
    provider_id: str,
    unit_id: str,
    framework: str,
    symbol: str,
    path: str,
) -> str:
    return stable_evidence_id("framework", provider_id, unit_id, framework, symbol, path)
