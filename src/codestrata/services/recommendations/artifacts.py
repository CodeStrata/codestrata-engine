"""Persist Recommendation Engine artifacts."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.recommendations import RecommendationResult
from codestrata.services.artifact_serialization import dumps_stable_json, recommendations_payload

RECOMMENDATIONS_FILENAME = "recommendations.json"


class RecommendationsArtifactWriteResult(BaseModel):
    """Result of writing recommendations.json."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    recommendation_count: int = Field(ge=0)
    providers_evaluated_count: int = Field(ge=0)


def write_recommendations_artifact(
    result: RecommendationResult,
    run_directory: Path,
) -> RecommendationsArtifactWriteResult:
    """Write deterministic recommendations.json under the assessment run directory."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / RECOMMENDATIONS_FILENAME
    path.write_text(dumps_stable_json(recommendations_payload(result)), encoding="utf-8")
    return RecommendationsArtifactWriteResult(
        path=path,
        recommendation_count=result.recommendation_count,
        providers_evaluated_count=len(result.providers_evaluated),
    )


def format_recommendation_console_summary(result: RecommendationResult) -> tuple[str, ...]:
    """Return concise console lines for recommendation evaluation."""

    return (f"Recommendations: {result.recommendation_count}",)
