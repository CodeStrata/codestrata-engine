"""Immutable AI enrichment narrative models.

These models describe interpretive modernization narrative derived from
deterministic findings and recommendations. They never mutate those sources.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.ai_enrichment.enums import EnrichmentPriorityLevel
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

AI_ENRICHMENT_RESULT_VERSION = "1.0.0"


class ExecutiveSummary(BaseModel):
    """Concise executive narrative for the assessed repository."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str
    narrative: str
    posture: str | None = None

    @field_validator("headline", "narrative", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="executive summary field")

    @field_validator("posture", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="posture")


class ModernizationTheme(BaseModel):
    """A thematic modernization focus area grounded in supplied evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    summary: str
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme field")

    @field_validator("related_finding_ids", "related_recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return _normalize_id_tuple(value)


class ModernizationPriority(BaseModel):
    """A prioritized modernization focus drawn from findings/recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    rationale: str
    priority: EnrichmentPriorityLevel
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()

    @field_validator("title", "rationale", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="priority field")

    @field_validator("related_finding_ids", "related_recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return _normalize_id_tuple(value)


class ModernizationRisk(BaseModel):
    """A major risk called out in the modernization narrative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    summary: str
    severity: EnrichmentPriorityLevel = EnrichmentPriorityLevel.MEDIUM
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="risk field")

    @field_validator("related_finding_ids", "related_recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return _normalize_id_tuple(value)


class SuggestedNextStep(BaseModel):
    """An actionable next step grounded in deterministic recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int = Field(ge=1)
    title: str
    summary: str
    related_recommendation_ids: tuple[str, ...] = ()
    related_finding_ids: tuple[str, ...] = ()

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="next step field")

    @field_validator("related_finding_ids", "related_recommendation_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return _normalize_id_tuple(value)


class AiProviderMetadata(BaseModel):
    """Provider and Modernization Advisor metadata for one enrichment invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model_id: str
    advisor_version: str = "1.0.0"
    prompt_version: str = "1.1.0"
    generated_at_utc: str | None = None
    request_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    stop_reason: str | None = None

    @field_validator("provider", "model_id", "advisor_version", "prompt_version", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="provider metadata field")

    @field_validator("request_id", "stop_reason", "generated_at_utc", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional provider metadata")


class AiEnrichmentResult(BaseModel):
    """Validated AI modernization narrative over deterministic evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = AI_ENRICHMENT_RESULT_VERSION
    executive_summary: ExecutiveSummary
    themes: tuple[ModernizationTheme, ...] = ()
    priorities: tuple[ModernizationPriority, ...] = ()
    risks: tuple[ModernizationRisk, ...] = ()
    suggested_next_steps: tuple[SuggestedNextStep, ...] = ()
    referenced_finding_ids: tuple[str, ...] = ()
    referenced_recommendation_ids: tuple[str, ...] = ()
    provider_metadata: AiProviderMetadata
    limitations: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "themes",
        "priorities",
        "risks",
        "suggested_next_steps",
        "referenced_finding_ids",
        "referenced_recommendation_ids",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("referenced_finding_ids", "referenced_recommendation_ids", mode="after")
    @classmethod
    def sort_referenced_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({require_nonblank(item, label="referenced id") for item in value}))

    @field_validator("suggested_next_steps", mode="after")
    @classmethod
    def sort_steps(
        cls,
        value: tuple[SuggestedNextStep, ...],
    ) -> tuple[SuggestedNextStep, ...]:
        return tuple(sorted(value, key=lambda item: (item.order, item.title)))

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @model_validator(mode="after")
    def aggregate_referenced_ids(self) -> AiEnrichmentResult:
        finding_ids = set(self.referenced_finding_ids)
        recommendation_ids = set(self.referenced_recommendation_ids)
        for theme in self.themes:
            finding_ids.update(theme.related_finding_ids)
            recommendation_ids.update(theme.related_recommendation_ids)
        for priority in self.priorities:
            finding_ids.update(priority.related_finding_ids)
            recommendation_ids.update(priority.related_recommendation_ids)
        for risk in self.risks:
            finding_ids.update(risk.related_finding_ids)
            recommendation_ids.update(risk.related_recommendation_ids)
        for step in self.suggested_next_steps:
            finding_ids.update(step.related_finding_ids)
            recommendation_ids.update(step.related_recommendation_ids)
        object.__setattr__(
            self,
            "referenced_finding_ids",
            tuple(sorted(finding_ids)),
        )
        object.__setattr__(
            self,
            "referenced_recommendation_ids",
            tuple(sorted(recommendation_ids)),
        )
        return self


def _normalize_id_tuple(value: object) -> tuple[str, ...]:
    items = as_tuple(value)
    return tuple(sorted({require_nonblank(str(item), label="id") for item in items}))
