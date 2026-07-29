"""Repository onboarding domain models (Phase 5.11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.onboarding.enums import OnboardingStatus
from codestrata.domain.onboarding.identifiers import (
    ONBOARDING_SCHEMA_NAME,
    ONBOARDING_SCHEMA_VERSION,
)


class RepositoryOnboardingManifest(BaseModel):
    """Persisted metadata for one completed (or partial) repository onboard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = ONBOARDING_SCHEMA_NAME
    schema_version: str = ONBOARDING_SCHEMA_VERSION
    repository_id: str
    repository_name: str
    scan_id: str
    assessment_version: str | None = None
    report_version: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    index_fingerprint: str | None = None
    languages_detected: tuple[str, ...] = ()
    frameworks_detected: tuple[str, ...] = ()
    scan_timestamp: datetime
    codestrata_version: str
    findings_count: int = Field(default=0, ge=0)
    recommendations_count: int = Field(default=0, ge=0)
    roadmap_initiative_count: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    knowledge_corpus_id: str | None = None
    knowledge_snapshot_id: str | None = None
    html_report_path: str | None = None
    json_report_path: str | None = None
    run_directory: str | None = None
    status: OnboardingStatus = OnboardingStatus.SUCCEEDED
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "schema_name",
        "schema_version",
        "repository_id",
        "repository_name",
        "scan_id",
        "report_version",
        "codestrata_version",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="onboarding manifest field")

    @field_validator(
        "assessment_version",
        "embedding_provider",
        "embedding_model",
        "index_fingerprint",
        "knowledge_corpus_id",
        "knowledge_snapshot_id",
        "html_report_path",
        "json_report_path",
        "run_directory",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional onboarding manifest field")

    @field_validator("languages_detected", "frameworks_detected", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class OnboardingSummary(BaseModel):
    """Console-oriented completion summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_analyzed: str
    languages_detected: tuple[str, ...] = ()
    frameworks_detected: tuple[str, ...] = ()
    findings_count: int = Field(default=0, ge=0)
    recommendations_count: int = Field(default=0, ge=0)
    roadmap_initiative_count: int = Field(default=0, ge=0)
    chunks_indexed: int = Field(default=0, ge=0)
    reports_generated: tuple[str, ...] = ()
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    knowledge_repository_id: str | None = None
    knowledge_run_id: str | None = None
    status: OnboardingStatus = OnboardingStatus.SUCCEEDED

    @field_validator("repository_analyzed", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_analyzed")

    @field_validator(
        "languages_detected",
        "frameworks_detected",
        "reports_generated",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class OnboardingResult(BaseModel):
    """Outcome of one ``codestrata onboard`` orchestration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: OnboardingStatus
    summary: OnboardingSummary
    manifest: RepositoryOnboardingManifest
    manifest_path: str | None = None
    assessment_run_directory: str | None = None
    warnings: tuple[str, ...] = ()
    existing_repository: bool = False

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)
