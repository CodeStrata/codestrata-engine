"""Provenance models for language evidence."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class EvidenceProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    provider_version: str
    source_analyzer: str = "language_evidence_provider"
    extraction_method: str = "source_parse"
    origin: EvidenceOrigin = EvidenceOrigin.SOURCE_PARSE
    source_path: str | None = None
    transformation_chain: tuple[str, ...] = ()
    configuration_fingerprint: str = ""
    notes: tuple[str, ...] = ()

    @field_validator(
        "provider_id",
        "provider_version",
        "source_analyzer",
        "extraction_method",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="provenance field")

    @field_validator("source_path", mode="before")
    @classmethod
    def normalize_optional_path(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="source_path")

    @field_validator("configuration_fingerprint", mode="before")
    @classmethod
    def normalize_fingerprint(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("transformation_chain", "notes", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())
