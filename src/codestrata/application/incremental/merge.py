"""Assemble complete merged assessment artifacts with reuse/recompute counts."""

from __future__ import annotations

from codestrata.application.incremental.execution_models import (
    IncrementalRecomputeCounts,
    IncrementalReuseCounts,
)
from codestrata.application.incremental.merge_validation import MergedAssessmentPackage
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult


class IncrementalArtifactMerger:
    """Package complete stage outputs for validation and persistence."""

    def merge(
        self,
        *,
        manifest: RepositoryManifest,
        pipeline_result: GraphAssessmentPipelineResult,
        rule_evaluation: RuleEvaluationResult,
        recommendation_result: RecommendationResult,
        reused_files: int = 0,
        recomputed_files: int = 0,
        reused_findings: int = 0,
        recomputed_findings: int = 0,
        reused_recommendations: int = 0,
        recomputed_recommendations: int = 0,
    ) -> tuple[MergedAssessmentPackage, IncrementalReuseCounts, IncrementalRecomputeCounts]:
        package = MergedAssessmentPackage(
            manifest=manifest,
            pipeline_result=pipeline_result,
            rule_evaluation=rule_evaluation,
            recommendation_result=recommendation_result,
        )
        rg = pipeline_result.repository_graph.snapshot
        kg = pipeline_result.knowledge_graph.snapshot
        ag = pipeline_result.assessment_graph.snapshot
        reuse = IncrementalReuseCounts(
            files=reused_files,
            findings=reused_findings,
            recommendations=reused_recommendations,
        )
        recompute = IncrementalRecomputeCounts(
            files=recomputed_files,
            repository_graph_nodes=len(rg.nodes),
            repository_graph_edges=len(rg.relationships),
            knowledge_graph_nodes=len(kg.nodes),
            knowledge_graph_edges=len(kg.relationships),
            assessment_graph_nodes=len(ag.nodes),
            assessment_graph_edges=len(ag.relationships),
            findings=recomputed_findings,
            recommendations=recomputed_recommendations,
            ai_artifacts=0,
        )
        return package, reuse, recompute
