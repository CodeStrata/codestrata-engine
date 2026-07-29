"""Telemetry summaries for language evidence collection (no source payloads)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.language.executor import LanguageEvidenceExecutionResult
from codestrata.domain.evidence.language.models import AggregatedLanguageEvidence
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class LanguageEvidenceTelemetry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    detected_languages: tuple[str, ...] = ()
    applicable_provider_ids: tuple[str, ...] = ()
    failed_provider_ids: tuple[str, ...] = ()
    provider_records: tuple[dict[str, object], ...] = ()
    evidence_item_count: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    contributing_provider_ids: tuple[str, ...] = ()
    configuration_fingerprint: str = ""

    @field_validator("repository_id", mode="before")
    @classmethod
    def normalize_repo(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_id")

    @field_validator(
        "detected_languages",
        "applicable_provider_ids",
        "failed_provider_ids",
        "provider_records",
        "contributing_provider_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


def build_telemetry(
    *,
    repository_id: str,
    execution: LanguageEvidenceExecutionResult,
    aggregated: AggregatedLanguageEvidence,
    configuration_fingerprint: str = "",
) -> LanguageEvidenceTelemetry:
    provider_records: tuple[dict[str, object], ...] = tuple(
        {
            "provider_id": record.provider_id,
            "status": str(record.status),
            "duration_ms": record.duration_ms,
            "evidence_count": record.evidence_count,
            "message": record.message,
        }
        for record in execution.records
    )
    evidence_count = (
        len(aggregated.source_units)
        + len(aggregated.dependencies)
        + len(aggregated.framework_usages)
    )
    return LanguageEvidenceTelemetry(
        repository_id=repository_id,
        detected_languages=execution.plan.detected_languages,
        applicable_provider_ids=execution.plan.applicable_provider_ids,
        failed_provider_ids=execution.failed_provider_ids,
        provider_records=provider_records,
        evidence_item_count=evidence_count,
        conflict_count=len(aggregated.conflicts),
        contributing_provider_ids=aggregated.contributing_provider_ids,
        configuration_fingerprint=configuration_fingerprint,
    )
