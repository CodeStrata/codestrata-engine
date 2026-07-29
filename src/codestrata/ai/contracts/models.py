"""Immutable LLM evidence contract models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

LLM_CONTRACT_SCHEMA_VERSION = "1.1.0"


class LLMSectionTruncation(BaseModel):
    """Explicit truncation metadata for a contract collection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    truncated: bool = False
    original_count: int = Field(ge=0)
    included_count: int = Field(ge=0)


class LLMEvidenceLocation(BaseModel):
    """Repository-relative evidence location for LLM consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    excerpt: str | None = None


class LLMTechnologyEvidence(BaseModel):
    """Detected technology evidence for LLM consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    category: str
    version: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class LLMFindingEvidence(BaseModel):
    """Finding evidence for LLM consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str | None = None
    rule_id: str | None = None
    group_id: str | None = None
    title: str
    category: str
    severity: str
    source: str | None = None
    summary: str
    customer_visibility: str | None = None
    modernization_relevance: str | None = None
    occurrence_count: int | None = Field(default=None, ge=1)
    affected_file_count: int | None = Field(default=None, ge=0)
    mapping_rationale: str | None = None
    evidence: list[LLMEvidenceLocation] = Field(default_factory=list)
    affected_technologies: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    evidence_truncation: LLMSectionTruncation


class LLMRepositoryContext(BaseModel):
    """Repository identity and inventory summary for LLM consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source_type: str
    default_branch: str | None = None
    commit_sha: str | None = None
    file_count: int = Field(ge=0)


class LLMMetricsContext(BaseModel):
    """Compact deterministic metrics derived from analysis facts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_count: int | None = None
    source_file_count: int | None = None
    test_file_count: int | None = None
    finding_count: int = Field(ge=0)
    technology_count: int = Field(ge=0)
    recommendation_count: int = Field(default=0, ge=0)


class LLMFactsSummary(BaseModel):
    """Compact deterministic repository fact summary for AI context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    architecture: dict[str, Any] = Field(default_factory=dict)
    build: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, Any] = Field(default_factory=dict)
    cicd: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    cloud_readiness: dict[str, Any] = Field(default_factory=dict)


class LLMStaticAnalysisSummary(BaseModel):
    """Static-analysis profile and count summary for AI context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: str | None = None
    status: str | None = None
    provider: str | None = None
    provider_version: str | None = None
    rulesets: list[str] = Field(default_factory=list)
    eligible_file_count: int = 0
    files_analyzed: int = 0
    raw_observation_count: int = 0
    grouped_finding_count: int = 0
    primary_count: int = 0
    supporting_count: int = 0
    informational_count: int = 0
    suppressed_from_html_count: int = 0


class LLMRecommendationEvidence(BaseModel):
    """Compact deterministic recommendation for AI consolidation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    priority: str
    category: str
    related_finding_ids: list[str] = Field(default_factory=list)
    summary: str


class LLMContextBudgetMetadata(BaseModel):
    """Deterministic AI-context budgeting metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_finding_count: int = Field(ge=0)
    included_finding_count: int = Field(ge=0)
    omitted_informational_count: int = Field(ge=0)
    estimated_input_tokens: int = Field(ge=0)
    static_analysis_profile: str | None = None


class LLMAnalysisContext(BaseModel):
    """Provider-neutral LLM analysis evidence contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = LLM_CONTRACT_SCHEMA_VERSION
    repository: LLMRepositoryContext
    technologies: list[LLMTechnologyEvidence] = Field(default_factory=list)
    metrics: LLMMetricsContext
    findings: list[LLMFindingEvidence] = Field(default_factory=list)
    findings_truncation: LLMSectionTruncation
    facts_summary: LLMFactsSummary = Field(default_factory=LLMFactsSummary)
    static_analysis_summary: LLMStaticAnalysisSummary = Field(
        default_factory=LLMStaticAnalysisSummary
    )
    deterministic_recommendations: list[LLMRecommendationEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    budget: LLMContextBudgetMetadata | None = None

    def model_dump_json_ready(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary using mode='json'."""

        return self.model_dump(mode="json")
