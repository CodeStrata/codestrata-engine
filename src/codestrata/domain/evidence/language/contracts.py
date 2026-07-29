"""Language evidence provider contract and result models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.evidence.language.capabilities import (
    ProviderApplicabilityStatus,
    ProviderExecutionStatus,
)
from codestrata.domain.evidence.language.capability_catalog import ProviderCapabilitySet
from codestrata.domain.evidence.language.identifiers import (
    LanguageEvidenceProviderId,
    validate_provider_id,
)
from codestrata.domain.evidence.language.models import LanguageEvidenceBundle
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class LanguageEvidenceProviderMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: LanguageEvidenceProviderId
    provider_version: str
    title: str
    description: str
    supported_languages: tuple[str, ...] = ()
    supported_file_extensions: tuple[str, ...] = ()
    supported_frameworks: tuple[str, ...] = ()
    capabilities: ProviderCapabilitySet = Field(default_factory=ProviderCapabilitySet)
    documentation_reference: str | None = None
    enabled_by_default: bool = True

    @field_validator("provider_id", mode="before")
    @classmethod
    def normalize_provider_id(cls, value: object) -> LanguageEvidenceProviderId | object:
        if isinstance(value, LanguageEvidenceProviderId):
            return value
        return LanguageEvidenceProviderId(validate_provider_id(str(value)))

    @field_validator("provider_version", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="provider metadata field")

    @field_validator(
        "supported_languages",
        "supported_file_extensions",
        "supported_frameworks",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted({str(item).strip().lower() for item in as_tuple(value) if str(item).strip()})
        )

    @field_validator("documentation_reference", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="documentation_reference")


class ProviderApplicability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ProviderApplicabilityStatus
    message: str | None = None
    detected_languages: tuple[str, ...] = ()

    @classmethod
    def applicable(cls, *, detected_languages: tuple[str, ...] = ()) -> ProviderApplicability:
        return cls(
            status=ProviderApplicabilityStatus.APPLICABLE,
            detected_languages=tuple(sorted(set(detected_languages))),
        )

    @classmethod
    def not_applicable(cls, message: str) -> ProviderApplicability:
        return cls(status=ProviderApplicabilityStatus.NOT_APPLICABLE, message=message)

    @classmethod
    def insufficient_input(cls, message: str) -> ProviderApplicability:
        return cls(status=ProviderApplicabilityStatus.INSUFFICIENT_INPUT, message=message)

    @property
    def is_applicable(self) -> bool:
        return self.status is ProviderApplicabilityStatus.APPLICABLE


class LanguageEvidenceContext(BaseModel):
    """Inputs for provider collection (no network/AI; application-built)."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    repository_id: str
    relative_paths: tuple[str, ...] = ()
    file_texts: dict[str, str] = Field(default_factory=dict)
    detected_languages: tuple[str, ...] = ()
    configuration: dict[str, str] = Field(default_factory=dict)

    @field_validator("repository_id", mode="before")
    @classmethod
    def normalize_repo(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_id")

    @field_validator("relative_paths", "detected_languages", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class LanguageEvidenceCollectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ProviderExecutionStatus
    bundle: LanguageEvidenceBundle | None = None
    message: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)

    @classmethod
    def succeeded(cls, bundle: LanguageEvidenceBundle, *, duration_ms: int | None = None) -> (
        LanguageEvidenceCollectionResult
    ):
        return cls(
            status=ProviderExecutionStatus.SUCCEEDED,
            bundle=bundle,
            duration_ms=duration_ms,
        )

    @classmethod
    def partially_succeeded(
        cls,
        bundle: LanguageEvidenceBundle,
        *,
        message: str,
        duration_ms: int | None = None,
    ) -> LanguageEvidenceCollectionResult:
        return cls(
            status=ProviderExecutionStatus.PARTIALLY_SUCCEEDED,
            bundle=bundle,
            message=message,
            duration_ms=duration_ms,
        )

    @classmethod
    def failed(cls, message: str, *, duration_ms: int | None = None) -> (
        LanguageEvidenceCollectionResult
    ):
        return cls(
            status=ProviderExecutionStatus.FAILED,
            message=require_nonblank(message, label="failure message"),
            duration_ms=duration_ms,
        )

    @classmethod
    def not_applicable(cls, message: str) -> LanguageEvidenceCollectionResult:
        return cls(
            status=ProviderExecutionStatus.NOT_APPLICABLE,
            message=message,
        )

    @classmethod
    def insufficient_input(cls, message: str) -> LanguageEvidenceCollectionResult:
        return cls(
            status=ProviderExecutionStatus.INSUFFICIENT_INPUT,
            message=message,
        )


@runtime_checkable
class LanguageEvidenceProvider(Protocol):
    """Collects and normalizes language evidence; never creates Findings."""

    @property
    def metadata(self) -> LanguageEvidenceProviderMetadata: ...

    def evaluate_applicability(self, context: LanguageEvidenceContext) -> ProviderApplicability: ...

    def collect(self, context: LanguageEvidenceContext) -> LanguageEvidenceCollectionResult: ...

    def explain_applicability(self, context: LanguageEvidenceContext) -> dict[str, Any]: ...
