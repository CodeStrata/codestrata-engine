"""Architecture conclusion domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.architecture.conclusions.enums import (
    ConclusionMateriality,
    ConclusionStatus,
    ModernizationWave,
)
from codestrata.domain.architecture.conclusions.identifiers import validate_category_id
from codestrata.domain.architecture.conclusions.relationships import SeveritySummary
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import MatchEvidenceConfidence


class ArchitectureConclusion(BaseModel):
    """Deterministic interpretation of one or more architecture findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_id: str
    conclusion_version: str = "1.0.0"
    policy_id: str
    category: str
    title: str
    summary: str
    technical_interpretation: str
    executive_interpretation: str
    affected_scope: tuple[str, ...] = ()
    assessment_dimensions: tuple[str, ...] = ("architecture",)
    taxonomy_ids: tuple[str, ...] = ()
    source_finding_ids: tuple[str, ...] = ()
    source_positive_evidence_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    primary_finding_id: str | None = None
    related_finding_ids: tuple[str, ...] = ()
    severity_summary: SeveritySummary
    business_impact: str = "unknown"
    confidence: MatchEvidenceConfidence = MatchEvidenceConfidence.MEDIUM
    coverage: dict[str, str] = Field(default_factory=dict)
    materiality: ConclusionMateriality = ConclusionMateriality.UNDETERMINED
    modernization_relevance: ModernizationWave = ModernizationWave.WAVE_2_FOUNDATION
    consolidated_recommendation_ids: tuple[str, ...] = ()
    report_sections: tuple[str, ...] = ("architecture",)
    limitations: tuple[str, ...] = ()
    provenance: str = "architecture_conclusions"
    status: ConclusionStatus = ConclusionStatus.ESTABLISHED
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "conclusion_id",
        "conclusion_version",
        "policy_id",
        "title",
        "summary",
        "technical_interpretation",
        "executive_interpretation",
        "business_impact",
        "provenance",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="conclusion field")

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> str:
        return validate_category_id(str(value))

    @field_validator(
        "affected_scope",
        "assessment_dimensions",
        "taxonomy_ids",
        "source_finding_ids",
        "source_positive_evidence_ids",
        "supporting_evidence_ids",
        "related_finding_ids",
        "consolidated_recommendation_ids",
        "report_sections",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("primary_finding_id", mode="before")
    @classmethod
    def normalize_primary(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="primary_finding_id")

    @field_validator("coverage", "metadata", mode="before")
    @classmethod
    def normalize_maps(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("mapping fields must be dictionaries")
        return {str(key): str(item) for key, item in value.items()}


class ConsolidatedRecommendation(BaseModel):
    """Coordinated recommendation group for a conclusion (does not replace rule recs)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_group_id: str
    title: str
    primary_action: str
    rationale: str
    affected_scope: tuple[str, ...] = ()
    source_recommendation_ids: tuple[str, ...] = ()
    source_finding_ids: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    effort_band: str = "medium"
    validation_steps: tuple[str, ...] = ()
    sequencing_guidance: str = ""
    modernization_wave: ModernizationWave = ModernizationWave.WAVE_2_FOUNDATION
    confidence: MatchEvidenceConfidence = MatchEvidenceConfidence.MEDIUM
    limitations: tuple[str, ...] = ()

    @field_validator(
        "recommendation_group_id",
        "title",
        "primary_action",
        "rationale",
        "effort_band",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation group field")

    @field_validator(
        "affected_scope",
        "source_recommendation_ids",
        "source_finding_ids",
        "prerequisites",
        "validation_steps",
        "limitations",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())

    @field_validator("sequencing_guidance", mode="before")
    @classmethod
    def normalize_guidance(cls, value: object) -> str:
        return str(value or "").strip()


class ArchitectureSummary(BaseModel):
    """Assessment-ready architecture summary (optional enrichment)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion_count: int = Field(default=0, ge=0)
    finding_count: int = Field(default=0, ge=0)
    material_conclusion_count: int = Field(default=0, ge=0)
    highest_severity: str | None = None
    business_impact: str = "unknown"
    coverage_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    headline: str = ""

    @field_validator("coverage_notes", "limitations", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[str, ...]:
        return tuple(str(item).strip() for item in as_tuple(value) if str(item).strip())
