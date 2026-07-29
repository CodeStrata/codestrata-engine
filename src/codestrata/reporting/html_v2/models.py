"""HTML Report v2 view-model contracts.

Presentation-only models. Business logic belongs in upstream domain services;
the renderer must not invent findings, recommendations, or enrichment content.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.reporting.ai_readiness.models import AiReadinessReportSection
from codestrata.reporting.architecture.models import ArchitectureReportSection
from codestrata.reporting.cloud.models import CloudReportSection
from codestrata.reporting.dependency.models import DependencyReportSection
from codestrata.reporting.performance.models import PerformanceReportSection
from codestrata.reporting.roadmap.models import RoadmapReportSection
from codestrata.reporting.security.models import SecurityReportSection
from codestrata.reporting.technical_debt.models import TechnicalDebtReportSection
from codestrata.reporting.testing.models import TestingReportSection


class DashboardMetrics(BaseModel):
    """Scannable factual KPI values for the executive dashboard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_count: int = Field(ge=0)
    technology_count: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    recommendations_count: int = Field(ge=0)
    test_file_count: int | None = None
    has_tests: bool | None = None
    test_files_label: str = "Unknown"
    cicd_present: bool | None = None
    cicd_label: str = "Unknown"
    cloud_signal_count: int | None = None
    cloud_signals_primary: str = "Unknown"
    cloud_signals_status: str = "Unknown"
    highest_finding_severity: str = "None Detected"
    repository_size_label: str = "—"


class ReportSummary(BaseModel):
    """Executive overview cards."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_name: str
    assessment_mode: str
    assessment_mode_label: str
    technologies: tuple[str, ...] = ()
    total_findings: int = Field(ge=0)
    findings_by_severity: tuple[tuple[str, int], ...] = ()
    total_recommendations: int = Field(ge=0)
    highest_recommendation_priority: str | None = None
    ai_enrichment_status: str
    ai_enrichment_available: bool = False
    metrics: DashboardMetrics | None = None
    highest_finding_severity: str = "None Detected"

    @field_validator("repository_name", "assessment_mode", "assessment_mode_label", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="summary field")

    @field_validator("technologies", "findings_by_severity", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RepositoryProfileView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    reference: str | None = None
    source_type: str
    file_count: int = Field(ge=0)
    default_branch: str | None = None

    @field_validator("name", "source_type", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository profile field")


class TechnologyItemView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    category: str | None = None
    version: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="technology name")


class VersionHighlightView(BaseModel):
    """Concise version/dependency highlight for the technology summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    kind: str = "dependency"
    detail: str | None = None

    @field_validator("label", "value", "kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="version highlight field")


class EvidenceView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None
    node_id: str | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="evidence field")


class FindingView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    title: str
    description: str
    severity: str
    category: str
    affected_nodes: tuple[str, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()

    @field_validator(
        "finding_id",
        "rule_id",
        "title",
        "description",
        "severity",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding view field")

    @field_validator("affected_nodes", "evidence", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class RecommendationActionView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int = Field(ge=1)
    title: str
    description: str
    command: str | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="action field")


class RecommendationView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    title: str
    summary: str
    rationale: str
    priority: str
    category: str
    related_finding_ids: tuple[str, ...] = ()
    related_finding_titles: tuple[str, ...] = ()
    affected_nodes: tuple[str, ...] = ()
    actions: tuple[RecommendationActionView, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    effort: str = "unknown"
    risk: str = "medium"
    dependencies: tuple[str, ...] = ()
    priority_score: float = 0.0
    presentation_bucket: str = "future"

    @field_validator(
        "recommendation_id",
        "title",
        "summary",
        "rationale",
        "priority",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation view field")

    @field_validator(
        "related_finding_ids",
        "related_finding_titles",
        "affected_nodes",
        "actions",
        "evidence",
        "dependencies",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class AiThemeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    summary: str
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()


class AiPriorityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    rationale: str
    priority: str
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()


class AiRiskView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    summary: str
    severity: str
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()


class AiNextStepView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order: int = Field(ge=1)
    title: str
    summary: str
    related_finding_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()


class AiEnrichmentView(BaseModel):
    """AI-generated interpretation; never merged into deterministic sections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str
    narrative: str
    posture: str | None = None
    themes: tuple[AiThemeView, ...] = ()
    priorities: tuple[AiPriorityView, ...] = ()
    risks: tuple[AiRiskView, ...] = ()
    suggested_next_steps: tuple[AiNextStepView, ...] = ()
    referenced_finding_ids: tuple[str, ...] = ()
    referenced_recommendation_ids: tuple[str, ...] = ()
    provider: str
    model_id: str
    advisor_version: str | None = None
    prompt_version: str | None = None
    generated_at_utc: str | None = None
    request_id: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    limitations: tuple[str, ...] = ()
    disclaimer: str = (
        "Modernization Advisor interpretation. Findings and Priority Actions "
        "from the assessment remain the source of truth."
    )


class ArtifactRefView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    relative_path: str

    @field_validator("label", "relative_path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="artifact ref field")


class AssessmentMetadataView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_at_utc: str
    report_title: str
    organization_name: str | None = None
    confidentiality_notice: str | None = None
    warnings: tuple[str, ...] = ()
    timing_total_ms: float | None = None
    timing_scan_ms: float | None = None
    timing_analysis_ms: float | None = None
    timing_ai_ms: float | None = None
    timing_report_ms: float | None = None
    ai_status: str
    model_id: str | None = None
    report_version: str = "3.0"
    engine_version: str = "0.1.0"
    advisor_version: str | None = None
    repository_name: str | None = None


class AssessmentSummaryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rules_evaluated: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    recommendations_count: int = Field(ge=0)
    findings_by_severity: tuple[tuple[str, int], ...] = ()
    recommendations_by_priority: tuple[tuple[str, int], ...] = ()
    summary_text: str


class ReportOutlineEntry(BaseModel):
    """Single table-of-contents entry for a customer report section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section_id: str
    title: str

    @field_validator("section_id", "title", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="outline entry field")


class EngineeringRiskThemeView(BaseModel):
    """One themed risk group for leadership Engineering Risks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme: str
    items: tuple[str, ...] = ()

    @field_validator("theme", mode="before")
    @classmethod
    def normalize_theme(cls, value: object) -> str:
        return require_nonblank(str(value), label="risk theme")

    @field_validator("items", mode="before")
    @classmethod
    def normalize_items(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class ExecutiveSummaryNarrative(BaseModel):
    """VP-facing executive summary answers (Phase 7.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    should_i_care: str
    why_now: str
    what_next: str

    @field_validator("should_i_care", "why_now", "what_next", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="executive summary field")


class AssessmentScopeView(BaseModel):
    """Compact Assessment Scope for the technical appendix only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assessed_packs: tuple[str, ...] = ()
    not_assessed_packs: tuple[tuple[str, str], ...] = ()

    @field_validator("assessed_packs", "not_assessed_packs", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


class CustomerReportDocument(BaseModel):
    """Renderer-neutral customer presentation document (Phase 6.3).

    Assembled once from assessment artifacts; HTML/PDF/Markdown renderers
    consume this model without re-running analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: ReportSummary
    repository: RepositoryProfileView
    technologies: tuple[TechnologyItemView, ...] = ()
    version_highlights: tuple[VersionHighlightView, ...] = ()
    assessment_summary: AssessmentSummaryView
    findings: tuple[FindingView, ...] = ()
    recommendations: tuple[RecommendationView, ...] = ()
    priority_actions: tuple[RecommendationView, ...] = ()
    ai_enrichment: AiEnrichmentView | None = None
    architecture_report: ArchitectureReportSection | None = None
    technical_debt_report: TechnicalDebtReportSection | None = None
    dependency_report: DependencyReportSection | None = None
    security_report: SecurityReportSection | None = None
    testing_report: TestingReportSection | None = None
    cloud_report: CloudReportSection | None = None
    ai_readiness_report: AiReadinessReportSection | None = None
    performance_report: PerformanceReportSection | None = None
    roadmap_report: RoadmapReportSection | None = None
    artifacts: tuple[ArtifactRefView, ...] = ()
    metadata: AssessmentMetadataView
    outline: tuple[ReportOutlineEntry, ...] = ()
    leadership_verdict: str = ""
    executive_summary: ExecutiveSummaryNarrative | None = None
    key_takeaways: tuple[str, ...] = ()
    engineering_risks: tuple[EngineeringRiskThemeView, ...] = ()
    modernization_opportunities: tuple[str, ...] = ()
    assessment_scope: AssessmentScopeView | None = None
    provenance_note: str = (
        "Findings and Priority Actions reflect repository evidence from this assessment. "
        "Modernization Advisor, when present, is interpretive commentary only."
    )

    @field_validator(
        "technologies",
        "version_highlights",
        "findings",
        "recommendations",
        "priority_actions",
        "artifacts",
        "outline",
        "key_takeaways",
        "engineering_risks",
        "modernization_opportunities",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)


# Backward-compatible alias used by existing imports and tests.
HtmlReportViewModel = CustomerReportDocument


def severity_rank(severity: str) -> int:
    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "informational": 4,
        "info": 4,
    }
    return order.get(severity.lower(), 99)


def priority_rank(priority: str) -> int:
    order = {
        "immediate": 0,
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return order.get(priority.lower(), 99)


def count_by_key(items: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return tuple(sorted(counts.items(), key=lambda pair: (severity_rank(pair[0]), pair[0])))


def as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})
