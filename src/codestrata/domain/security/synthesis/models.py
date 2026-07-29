"""Security synthesis domain models (Phase 4.5.5).

Themes, conclusions, and recommendations derived from the assessment inventory.
No scores, grades, risk indices, business-impact claims, or AI narrative.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.security.assessment.enums import SecuritySourceRole
from codestrata.domain.security.synthesis.enums import (
    SecurityConclusionAudience,
    SecurityConclusionKind,
    SecurityRecommendationKind,
    SecuritySynthesisStatus,
    SecurityThemeKind,
    SecurityThemeScope,
)
from codestrata.domain.security.synthesis.identifiers import SYNTHESIS_VERSION


def _normalize_count_map(value: object) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("count maps must be dictionaries")
    return {str(key): int(item) for key, item in sorted(value.items())}


class SecurityTheme(BaseModel):
    """Inventory-derived Security theme (no synthetic score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme_id: str
    kind: SecurityThemeKind
    title: str
    description: str
    scope: SecurityThemeScope = SecurityThemeScope.REPOSITORY
    source_role: SecuritySourceRole = SecuritySourceRole.UNKNOWN
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    category_ids: tuple[str, ...] = ()
    counts: dict[str, int] = Field(default_factory=dict)
    ordering_key: str = ""

    @field_validator("theme_id", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="theme field")

    @field_validator(
        "finding_ids",
        "hotspot_ids",
        "diagnostic_ids",
        "rule_ids",
        "category_ids",
        mode="before",
    )
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


class SecurityConcentrationFact(BaseModel):
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
    source_role: SecuritySourceRole = SecuritySourceRole.PRODUCTION
    supporting_finding_ids: tuple[str, ...] = ()
    supporting_hotspot_ids: tuple[str, ...] = ()
    supporting_rule_ids: tuple[str, ...] = ()

    @field_validator("fact_id", "kind", "subject", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="concentration fact field")

    @field_validator(
        "supporting_finding_ids",
        "supporting_hotspot_ids",
        "supporting_rule_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())


class SecurityConclusion(BaseModel):
    """Deterministic Security conclusion with bounded template text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    conclusion_version: str = SYNTHESIS_VERSION
    policy_id: str
    kind: SecurityConclusionKind
    audience: SecurityConclusionAudience
    title: str
    summary: str
    technical_interpretation: str
    source_role: SecuritySourceRole = SecuritySourceRole.UNKNOWN
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    concentration_fact_ids: tuple[str, ...] = ()
    recommendation_ids: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("security",)
    business_impact: str = "unknown"
    confidence: str = "high"
    provenance: str = "security_synthesis"
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
        "diagnostic_ids",
        "rule_ids",
        "concentration_fact_ids",
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


class SecurityRecommendation(BaseModel):
    """Factual/conditional recommendation referencing one or more conclusions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    kind: SecurityRecommendationKind
    title: str
    action: str
    rationale: str
    conclusion_ids: tuple[str, ...] = ()
    theme_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()
    hotspot_ids: tuple[str, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()
    conditional: bool = True
    audience: SecurityConclusionAudience = (
        SecurityConclusionAudience.PRODUCTION_HEALTH
    )
    effort_band: str = "unknown"
    business_impact: str = "unknown"
    provenance: str = "security_synthesis"
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
        "diagnostic_ids",
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


class SecuritySynthesisResult(BaseModel):
    """Complete synthesis payload attached to the assessment section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SecuritySynthesisStatus = SecuritySynthesisStatus.SUCCEEDED
    synthesis_version: str = SYNTHESIS_VERSION
    themes: tuple[SecurityTheme, ...] = ()
    theme_ids: tuple[str, ...] = ()
    concentration_facts: tuple[SecurityConcentrationFact, ...] = ()
    conclusions: tuple[SecurityConclusion, ...] = ()
    conclusion_ids: tuple[str, ...] = ()
    recommendations: tuple[SecurityRecommendation, ...] = ()
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
        return (
            optional_nonblank(str(value), label="synthesis_version") or SYNTHESIS_VERSION
        )
