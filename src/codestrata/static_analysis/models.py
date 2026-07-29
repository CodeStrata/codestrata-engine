"""Provider-neutral static-analysis domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from codestrata.models.enums import FindingCategory, Severity
from codestrata.models.finding import Finding
from codestrata.models.repository import Repository
from codestrata.models.technology import Technology
from codestrata.static_analysis.visibility import CustomerVisibility, ModernizationRelevance


class StaticAnalysisStatus(StrEnum):
    """Execution outcome for an external static-analysis provider."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    FAILED = "failed"


class StaticAnalysisContext(BaseModel):
    """Resolved inputs passed to a static-analysis provider."""

    repository: Repository
    repository_path: str
    detected_technologies: list[Technology] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    output_directory: str | None = None


class StaticAnalysisObservation(BaseModel):
    """Raw provider observation retained for machine-readable reports."""

    observation_id: str
    provider_id: str
    provider_name: str
    provider_version: str | None = None
    rule_id: str
    external_rule_id: str | None = None
    provider_priority: int | None = None
    provider_category: str | None = None
    normalized_category: FindingCategory
    normalized_severity: Severity
    customer_visibility: CustomerVisibility
    modernization_relevance: ModernizationRelevance
    file_path: str
    line_number: int | None = None
    column_number: int | None = None
    end_line_number: int | None = None
    end_column_number: int | None = None
    message: str
    title: str
    group_id: str | None = None
    mapping_rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StaticAnalysisGroup(BaseModel):
    """Grouped remediation pattern derived from repeated observations."""

    group_id: str
    provider_id: str
    provider_name: str
    rule_id: str
    title: str
    description: str
    category: FindingCategory
    severity: Severity
    customer_visibility: CustomerVisibility
    modernization_relevance: ModernizationRelevance
    occurrence_count: int = Field(ge=1)
    affected_file_count: int = Field(ge=0)
    representative_locations: list[dict[str, Any]] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    mapping_rationale: str = ""


class StaticAnalysisResult(BaseModel):
    """Outcome of one external static-analysis provider execution."""

    provider_id: str
    provider_name: str
    provider_version: str | None = None
    status: StaticAnalysisStatus
    findings: list[Finding] = Field(default_factory=list)
    files_analyzed: int = 0
    eligible_file_count: int = 0
    duration_ms: float | None = None
    command_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    profile: str | None = None
    observations: list[StaticAnalysisObservation] = Field(default_factory=list)
    groups: list[StaticAnalysisGroup] = Field(default_factory=list)
    raw_observation_count: int = 0
    grouped_finding_count: int = 0
    primary_count: int = 0
    supporting_count: int = 0
    informational_count: int = 0
    suppressed_from_html_count: int = 0


def _rebuild_dependent_models() -> None:
    """Rebuild AnalysisResult once StaticAnalysisResult is fully defined."""

    try:
        from codestrata.models.analysis_result import _rebuild_analysis_result_model
    except ImportError:
        return
    _rebuild_analysis_result_model()


_rebuild_dependent_models()
