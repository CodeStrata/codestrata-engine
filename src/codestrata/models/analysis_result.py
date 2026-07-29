"""Domain model representing the complete repository analysis result."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from codestrata.models.finding import Finding
from codestrata.models.recommendation import Recommendation
from codestrata.models.repository import Repository
from codestrata.models.repository_facts import RepositoryFacts
from codestrata.models.scan_comparison import ScanComparison
from codestrata.models.technology import Technology

if TYPE_CHECKING:
    from codestrata.static_analysis.models import StaticAnalysisResult


class AnalysisResult(BaseModel):
    """Represents the complete output of one repository analysis."""

    id: UUID = Field(default_factory=uuid4)
    repository: Repository
    technologies: list[Technology] = Field(default_factory=list)
    facts: RepositoryFacts = Field(default_factory=RepositoryFacts)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    static_analysis_results: list[StaticAnalysisResult] = Field(default_factory=list)
    comparison: ScanComparison | None = None
    executive_summary: str | None = None
    modernization_score: float | None = Field(default=None, ge=0.0, le=100.0)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    analyzer_version: str | None = None
    ruleset_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_analysis_dates(self) -> AnalysisResult:
        """Ensure analysis completion is not earlier than its start."""

        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at")

        return self


def _rebuild_analysis_result_model() -> None:
    """Resolve the StaticAnalysisResult forward reference after both modules load."""

    from codestrata.static_analysis.models import StaticAnalysisResult

    AnalysisResult.model_rebuild(_types_namespace={"StaticAnalysisResult": StaticAnalysisResult})
