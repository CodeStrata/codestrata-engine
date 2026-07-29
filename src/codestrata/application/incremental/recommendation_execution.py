"""Incremental recommendation execution."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import Recommendation, RecommendationResult
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.recommendations import RecommendationEngine


class IncrementalRecommendationExecutor:
    """Regenerate recommendations from merged findings (selective deferred)."""

    def __init__(
        self,
        *,
        engine: RecommendationEngine | None = None,
        allow_reuse: bool = True,
    ) -> None:
        self._engine = engine or RecommendationEngine()
        self._allow_reuse = allow_reuse

    def execute(
        self,
        *,
        pipeline_result: GraphAssessmentPipelineResult,
        evaluation: RuleEvaluationResult,
        previous_recommendations: Sequence[Recommendation] = (),
        unchanged_finding_ids: frozenset[str] = frozenset(),
    ) -> tuple[RecommendationResult, int, int]:
        # Phase 2F.2: providers lack selective scope → full regeneration.
        result = self._engine.evaluate_pipeline_result(
            pipeline_result=pipeline_result,
            evaluation=evaluation,
        )
        if not self._allow_reuse or not unchanged_finding_ids:
            return result, 0, len(result.recommendations)

        reused = 0
        for recommendation in previous_recommendations:
            related = frozenset(str(item) for item in recommendation.related_finding_ids)
            if related and related <= unchanged_finding_ids:
                reused += 1
        # Still return fully regenerated result for equivalence; reuse count is advisory.
        return result, reused, len(result.recommendations)
