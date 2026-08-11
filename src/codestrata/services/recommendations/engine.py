"""Deterministic Recommendation Engine."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import Recommendation, RecommendationResult
from codestrata.domain.rules import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.recommendations.context import RecommendationContext
from codestrata.services.recommendations.protocol import RecommendationProvider
from codestrata.services.recommendations.providers import builtin_recommendation_providers
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class RecommendationEngine:
    """Derive actionable recommendations from Phase 3 findings."""

    def __init__(
        self,
        providers: Sequence[RecommendationProvider] | None = None,
    ) -> None:
        loaded: tuple[RecommendationProvider, ...]
        if providers is not None:
            loaded = tuple(providers)
        else:
            loaded = tuple(builtin_recommendation_providers())  # type: ignore[arg-type]
        self._providers: tuple[RecommendationProvider, ...] = tuple(
            sorted(loaded, key=lambda provider: provider.id())
        )

    @property
    def providers(self) -> tuple[RecommendationProvider, ...]:
        return self._providers

    def evaluate(self, context: RecommendationContext) -> RecommendationResult:
        """Evaluate providers without mutating graphs/findings or calling AI."""

        from codestrata.application.recommendations.confidence import (
            apply_recommendation_confidence,
        )
        from codestrata.application.recommendations.priority_calibration import (
            apply_recommendation_priority,
        )
        from codestrata.application.traceability.recommendation import (
            merge_recommendation_traceability,
        )

        recommendations_by_id: dict[str, Recommendation] = {}
        recommendation_order: list[str] = []
        evaluated: list[str] = []
        skipped: list[str] = []
        matched_finding_ids: set[str] = set()

        finding_rule_ids = {finding.rule_id for finding in context.findings}
        for provider in self._providers:
            supported = provider.supported_finding_rule_ids()
            if not finding_rule_ids.intersection(supported):
                skipped.append(provider.id())
                continue
            evaluated.append(provider.id())
            for finding in context.findings:
                if finding.rule_id not in supported:
                    continue
                produced = provider.recommend(finding, context)
                if produced:
                    matched_finding_ids.add(finding.id)
                for recommendation in produced:
                    existing = recommendations_by_id.get(recommendation.id)
                    if existing is None:
                        with_confidence = apply_recommendation_confidence(
                            recommendation,
                            findings=context.findings,
                        )
                        recommendations_by_id[recommendation.id] = (
                            apply_recommendation_priority(
                                with_confidence,
                                findings=context.findings,
                            )
                        )
                        recommendation_order.append(recommendation.id)
                        continue
                    recommendations_by_id[recommendation.id] = merge_recommendation_traceability(
                        existing,
                        recommendation,
                        findings=context.findings,
                    )

        unmatched = tuple(
            finding.id for finding in context.findings if finding.id not in matched_finding_ids
        )
        return RecommendationResult.from_recommendations(
            recommendations=tuple(
                recommendations_by_id[item_id] for item_id in recommendation_order
            ),
            providers_evaluated=tuple(evaluated),
            providers_skipped=tuple(skipped),
            unmatched_finding_ids=unmatched,
        )

    def evaluate_from_rule_result(
        self,
        *,
        rule_context: RuleContext,
        evaluation: RuleEvaluationResult,
    ) -> RecommendationResult:
        return self.evaluate(
            RecommendationContext.from_rule_evaluation(
                rule_context=rule_context,
                evaluation=evaluation,
            )
        )

    def evaluate_pipeline_result(
        self,
        *,
        pipeline_result: GraphAssessmentPipelineResult,
        evaluation: RuleEvaluationResult,
    ) -> RecommendationResult:
        return self.evaluate_from_rule_result(
            rule_context=rule_context_from_pipeline(pipeline_result),
            evaluation=evaluation,
        )
