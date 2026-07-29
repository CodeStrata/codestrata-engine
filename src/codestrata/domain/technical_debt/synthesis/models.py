"""Technical Debt synthesis domain models (Phase 4.3.5).

Themes, conclusions, and recommendations derived from the assessment inventory.
No composite debt scores, fabricated priority, or financial/effort estimates.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.technical_debt.assessment.enums import TechnicalDebtSourceRole
from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
    TechnicalDebtConclusionKind,
    TechnicalDebtSynthesisStatus,
)
from codestrata.domain.technical_debt.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.technical_debt.taxonomy import TechnicalDebtCategory


class TechnicalDebtTheme(BaseModel):
    """Debt theme derived from taxonomy + rule ID (inventory aggregation)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    taxonomy_id: str = TechnicalDebtCategory.COMPLEXITY.value
    rule_id: str
    title: str
    source_role: TechnicalDebtSourceRole = TechnicalDebtSourceRole.PRODUCTION
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    finding_count: int = Field(default=0, ge=0)
    high_severity_count: int = Field(default=0, ge=0)
    medium_severity_count: int = Field(default=0, ge=0)

    @field_validator("theme_id", "taxonomy_id", "rule_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme field")

    @field_validator("finding_ids", "hotspot_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtConcentrationFact(BaseModel):
    """Transparent concentration fact using counts and proportions only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str
    kind: str
    subject: str
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    exceeds_threshold: bool = False
    source_role: TechnicalDebtSourceRole = TechnicalDebtSourceRole.PRODUCTION
    supporting_finding_ids: tuple[str, ...] = ()
    supporting_hotspot_ids: tuple[str, ...] = ()

    @field_validator("fact_id", "kind", "subject", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="concentration fact field")

    @field_validator("supporting_finding_ids", "supporting_hotspot_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class TechnicalDebtConclusion(BaseModel):
    """Deterministic Technical Debt conclusion with bounded template text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    conclusion_version: str = SYNTHESIS_VERSION
    policy_id: str
    kind: TechnicalDebtConclusionKind
    audience: TechnicalDebtConclusionAudience
    title: str
    summary: str
    technical_interpretation: str
    source_role: TechnicalDebtSourceRole = TechnicalDebtSourceRole.PRODUCTION
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    concentration_fact_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    taxonomy_ids: tuple[str, ...] = (TechnicalDebtCategory.COMPLEXITY.value,)
    assessment_dimensions: tuple[str, ...] = ("technical-debt",)
    business_impact: str = "unknown"
    confidence: str = "high"
    provenance: str = "technical_debt_synthesis"
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
        "hotspot_ids",
        "concentration_fact_ids",
        "recommendation_ids",
        "taxonomy_ids",
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


class TechnicalDebtRecommendation(BaseModel):
    """Factual/conditional recommendation referencing one or more conclusions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    action: str
    rationale: str
    conclusion_ids: tuple[str, ...] = ()
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    conditional: bool = True
    audience: TechnicalDebtConclusionAudience = (
        TechnicalDebtConclusionAudience.PRODUCTION_HEALTH
    )
    effort_band: str = "unknown"
    business_impact: str = "unknown"
    provenance: str = "technical_debt_synthesis"
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
        "hotspot_ids",
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


class TechnicalDebtSynthesisResult(BaseModel):
    """Complete synthesis payload attached to the assessment section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: TechnicalDebtSynthesisStatus = TechnicalDebtSynthesisStatus.SUCCEEDED
    synthesis_version: str = SYNTHESIS_VERSION
    themes: tuple[TechnicalDebtTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    concentration_facts: tuple[TechnicalDebtConcentrationFact, ...] = ()
    conclusions: tuple[TechnicalDebtConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[TechnicalDebtRecommendation, ...] = ()
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

    @field_validator(
        "themes",
        "concentration_facts",
        "conclusions",
        "recommendations",
        mode="before",
    )
    @classmethod
    def normalize_objects(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @field_validator("synthesis_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return optional_nonblank(str(value), label="synthesis_version") or SYNTHESIS_VERSION
