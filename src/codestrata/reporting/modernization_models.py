"""Contracts and exceptions for modernization assessment HTML reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.ai.agents.models import ModernizationAssessmentResult
from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.domain.ai_enrichment import AiEnrichmentResult
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.graph.validation import optional_nonblank, require_nonblank
from codestrata.domain.recommendations import RecommendationResult
from codestrata.models import AnalysisResult
from codestrata.reporting.ai_readiness.models import AiReadinessReportSection
from codestrata.reporting.architecture.models import ArchitectureReportSection
from codestrata.reporting.cloud.models import CloudReportSection
from codestrata.reporting.dependency.models import DependencyReportSection
from codestrata.reporting.performance.models import PerformanceReportSection
from codestrata.reporting.roadmap.models import RoadmapReportSection
from codestrata.reporting.security.models import SecurityReportSection
from codestrata.reporting.technical_debt.models import TechnicalDebtReportSection
from codestrata.reporting.testing.models import TestingReportSection


class AssessmentMode(StrEnum):
    """Execution mode for modernization assessment."""

    DETERMINISTIC = "deterministic"
    AI_ENHANCED = "ai-enhanced"


class AIExecutionStatus(StrEnum):
    """Overall outcome of the optional AI assessment stage.

    Distinguishes lifecycle outcomes so a successful provider call that later
    fails contract validation is never represented as "AI not executed."
    """

    NOT_REQUESTED = "not_requested"
    SUCCEEDED = "succeeded"
    AUTHENTICATION_FAILED = "authentication_failed"
    PROVIDER_FAILED = "provider_failed"
    PARSING_FAILED = "parsing_failed"
    VALIDATION_FAILED = "validation_failed"


class AIExecutionStage(StrEnum):
    """Ordered lifecycle stages for an AI assessment attempt."""

    REQUESTED = "requested"
    PROVIDER_INVOKED = "provider_invoked"
    RESPONSE_RECEIVED = "response_received"
    RESPONSE_PARSED = "response_parsed"
    RESPONSE_VALIDATED = "response_validated"
    RESULT_INCLUDED = "result_included"
    FALLBACK_USED = "fallback_used"


AI_FAILURE_STATUSES = frozenset(
    {
        AIExecutionStatus.AUTHENTICATION_FAILED,
        AIExecutionStatus.PROVIDER_FAILED,
        AIExecutionStatus.PARSING_FAILED,
        AIExecutionStatus.VALIDATION_FAILED,
    }
)

AI_POST_INVOCATION_FAILURE_STATUSES = frozenset(
    {
        AIExecutionStatus.PARSING_FAILED,
        AIExecutionStatus.VALIDATION_FAILED,
    }
)


class AIAttemptInfo(BaseModel):
    """Safe provider-execution metadata retained even when AI content is rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = None
    model_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0.0)
    stop_reason: str | None = None
    stages_completed: tuple[AIExecutionStage, ...] = Field(default_factory=tuple)
    failure_code: str | None = None
    failure_detail: str | None = None


class AssessmentTiming(BaseModel):
    """Wall-clock timing metadata for an assessment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_ms: float = Field(ge=0.0)
    scan_ms: float | None = Field(default=None, ge=0.0)
    analysis_ms: float | None = Field(default=None, ge=0.0)
    static_analysis_ms: float | None = Field(default=None, ge=0.0)
    ai_ms: float | None = Field(default=None, ge=0.0)
    report_ms: float | None = Field(default=None, ge=0.0)
    # Phase 5.19 — optional phase/scale telemetry (schema-compatible additive fields).
    graph_ms: float | None = Field(default=None, ge=0.0)
    rules_ms: float | None = Field(default=None, ge=0.0)
    evidence_ms: float | None = Field(default=None, ge=0.0)
    knowledge_ms: float | None = Field(default=None, ge=0.0)
    files_loaded: int | None = Field(default=None, ge=0)
    files_skipped: int | None = Field(default=None, ge=0)
    cache_hits: int | None = Field(default=None, ge=0)
    cache_misses: int | None = Field(default=None, ge=0)
    peak_rss_mb: float | None = Field(default=None, ge=0.0)


class ModernizationReportError(Exception):
    """Base error for modernization HTML report failures."""


class ModernizationReportValidationError(ModernizationReportError):
    """Raised when report input fails validation before rendering."""


class HighlightedVersionInput(BaseModel):
    """Compact version highlight for Report v2 (not a full dependency dump)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    kind: str = "dependency"
    detail: str | None = None

    @field_validator("label", "value", "kind", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="highlighted version field")

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="version detail")


class ReportArtifactInput(BaseModel):
    """Relative artifact reference for Report v2 (no absolute paths)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    relative_path: str

    @field_validator("label", "relative_path", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="artifact field")


class ModernizationReportInput(BaseModel):
    """Validated input for a customer-facing modernization HTML report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_result: AnalysisResult
    assessment_mode: AssessmentMode = AssessmentMode.DETERMINISTIC
    analysis_context: LLMAnalysisContext | None = None
    assessment_result: ModernizationAssessmentResult | None = None
    ai_status: AIExecutionStatus = AIExecutionStatus.NOT_REQUESTED
    ai_failure_message: str | None = None
    ai_attempt: AIAttemptInfo | None = None
    generated_at_utc: datetime
    report_title: str = "Engineering Assessment"
    organization_name: str | None = None
    repository_display_name: str | None = None
    repository_reference: str | None = None
    confidentiality_notice: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    timing: AssessmentTiming | None = None
    # Phase 3 / Report v2 inputs (optional; do not alter report.json schema).
    assessment_rule_evaluation: RuleEvaluationResult | None = None
    assessment_recommendation_result: RecommendationResult | None = None
    ai_enrichment: AiEnrichmentResult | None = None
    highlighted_versions: tuple[HighlightedVersionInput, ...] = Field(default_factory=tuple)
    report_artifacts: tuple[ReportArtifactInput, ...] = Field(default_factory=tuple)
    # Phase 4.2.5 — optional architecture report presentation (additive under assessment).
    architecture_report: ArchitectureReportSection | None = None
    # Phase 4.3.6 — optional technical debt report presentation (additive under assessment).
    technical_debt_report: TechnicalDebtReportSection | None = None
    # Phase 4.4.6 — optional dependency report presentation (additive under assessment).
    dependency_report: DependencyReportSection | None = None
    # Phase 4.5.6 — optional security report presentation (additive under assessment).
    security_report: SecurityReportSection | None = None
    # Phase 4.6.6 — optional testing report presentation (additive under assessment).
    testing_report: TestingReportSection | None = None
    # Phase 4.7.6 — optional cloud report presentation (additive under assessment).
    cloud_report: CloudReportSection | None = None
    # Phase 4.8.6 — optional AI readiness report presentation (additive under assessment).
    ai_readiness_report: AiReadinessReportSection | None = None
    # Phase 4.9.6 — optional performance report presentation (additive under assessment).
    performance_report: PerformanceReportSection | None = None
    # Phase 5.10 — optional modernization roadmap (additive under assessment.roadmap).
    roadmap_report: RoadmapReportSection | None = None
    # Phase 5.12 — optional knowledge identity for report manifest.
    knowledge_repository_id: str | None = None
    knowledge_run_id: str | None = None
    # Phase 7.1.1 — smart default assessment activation plan (JSON explainability).
    assessment_activation: dict[str, Any] | None = None

    @field_validator("generated_at_utc")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at_utc must be timezone-aware UTC")
        return value

    @field_validator("report_title")
    @classmethod
    def validate_report_title(cls, value: str) -> str:
        compact = value.strip()
        if not compact:
            raise ValueError("report_title must be a nonempty string")
        return compact

    @field_validator("repository_reference")
    @classmethod
    def validate_repository_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        return compact or None

    @model_validator(mode="after")
    def validate_mode_payload(self) -> ModernizationReportInput:
        if self.assessment_mode == AssessmentMode.AI_ENHANCED:
            if self.ai_status == AIExecutionStatus.SUCCEEDED:
                if self.analysis_context is None:
                    raise ValueError("AI-enhanced reports require analysis_context")
                if self.assessment_result is None:
                    raise ValueError("AI-enhanced reports require assessment_result")
            elif self.ai_status in AI_FAILURE_STATUSES:
                if self.assessment_result is not None:
                    raise ValueError("Failed AI assessments must not include assessment_result")
            elif self.ai_status == AIExecutionStatus.NOT_REQUESTED:
                raise ValueError(
                    "AI-enhanced mode requires an AI execution status other than not_requested"
                )
            elif self.assessment_result is not None:
                raise ValueError("AI assessment_result requires ai_status=succeeded")
        elif self.assessment_result is not None:
            raise ValueError("Deterministic reports must not include assessment_result")
        return self

    @property
    def ai_executed(self) -> bool:
        """True when a validated AI result is included in the customer-facing report."""

        return (
            self.assessment_mode == AssessmentMode.AI_ENHANCED
            and self.ai_status == AIExecutionStatus.SUCCEEDED
            and self.assessment_result is not None
        )

    @property
    def ai_provider_invoked(self) -> bool:
        """True when the AI provider was invoked (success or post-call failure)."""

        if self.ai_attempt is None:
            return self.ai_status in {
                AIExecutionStatus.SUCCEEDED,
                *AI_POST_INVOCATION_FAILURE_STATUSES,
                AIExecutionStatus.PROVIDER_FAILED,
            }
        return AIExecutionStage.PROVIDER_INVOKED in self.ai_attempt.stages_completed

    @property
    def ai_fallback_used(self) -> bool:
        return self.ai_status in AI_FAILURE_STATUSES
