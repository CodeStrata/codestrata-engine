"""AI Readiness synthesis domain models (Phase 4.8.5).

Themes, conclusions, and recommendations derived from the assessment inventory.
No scores, grades, readiness indices, modernization guidance, or AI narrative.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.ai_readiness.synthesis.enums import (
    AiReadinessConclusionAudience,
    AiReadinessConclusionKind,
    AiReadinessRecommendationKind,
    AiReadinessSynthesisStatus,
    AiReadinessThemeKind,
    AiReadinessThemeScope,
)
from codestrata.domain.ai_readiness.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


def _normalize_count_map(value: object) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("count maps must be dictionaries")
    return {str(key): int(item) for key, item in sorted(value.items())}


class AiReadinessTheme(BaseModel):
    """Inventory-derived AI Readiness theme (no synthetic score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    kind: AiReadinessThemeKind
    title: str
    description: str
    scope: AiReadinessThemeScope = AiReadinessThemeScope.REPOSITORY
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    counts: dict[str, int] = Field(default_factory=dict)
    ordering_key: str = ""

    @field_validator("theme_id", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme field")

    @field_validator("finding_ids", "rule_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("counts", mode="before")
    @classmethod
    def normalize_counts(cls, value: object) -> dict[str, int]:
        return _normalize_count_map(value)

    @field_validator("ordering_key", mode="before")
    @classmethod
    def normalize_ordering(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class AiReadinessConclusion(BaseModel):
    """Deterministic AI Readiness conclusion with bounded template text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    conclusion_version: str = SYNTHESIS_VERSION
    policy_id: str
    kind: AiReadinessConclusionKind
    audience: AiReadinessConclusionAudience
    title: str
    summary: str
    technical_interpretation: str
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("ai_readiness",)
    business_impact: str = "unknown"
    confidence: str = "high"
    provenance: str = "ai_readiness_synthesis"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "conclusion_id",
        "conclusion_version",
        "policy_id",
        "title",
        "summary",
        "technical_interpretation",
        "business_impact",
        "confidence",
        "provenance",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion field")

    @field_validator(
        "theme_ids",
        "finding_ids",
        "rule_ids",
        "recommendation_ids",
        "assessment_dimensions",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in value.items()}


class AiReadinessRecommendation(BaseModel):
    """Observation-oriented recommendation referencing conclusions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    kind: AiReadinessRecommendationKind
    title: str
    action: str
    rationale: str
    conclusion_ids: tuple[str, ...] = ()
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    conditional: bool = True
    audience: AiReadinessConclusionAudience = AiReadinessConclusionAudience.HYGIENE
    effort_band: str = "unknown"
    business_impact: str = "unknown"
    provenance: str = "ai_readiness_synthesis"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "recommendation_id",
        "title",
        "action",
        "rationale",
        "effort_band",
        "business_impact",
        "provenance",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation field")

    @field_validator(
        "conclusion_ids",
        "theme_ids",
        "finding_ids",
        "rule_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return {str(key): str(item) for key, item in value.items()}


class AiReadinessSynthesisResult(BaseModel):
    """Complete synthesis payload attached to the assessment section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AiReadinessSynthesisStatus = AiReadinessSynthesisStatus.SUCCEEDED
    synthesis_version: str = SYNTHESIS_VERSION
    overall_posture_summary: str = ""
    themes: tuple[AiReadinessTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    conclusions: tuple[AiReadinessConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[AiReadinessRecommendation, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @field_validator(
        "theme_ids",
        "conclusion_ids",
        "recommendation_ids",
        "diagnostics",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("themes", "conclusions", "recommendations", mode="before")
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("synthesis_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return optional_nonblank(str(value), label="synthesis_version") or SYNTHESIS_VERSION

    @field_validator("overall_posture_summary", mode="before")
    @classmethod
    def normalize_posture(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()
