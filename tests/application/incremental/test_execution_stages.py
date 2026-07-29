"""Stage executor unit tests for rules, recommendations, and merge validation."""

from __future__ import annotations

from codestrata.application.incremental.merge import IncrementalArtifactMerger
from codestrata.application.incremental.merge_validation import IncrementalMergeValidator
from codestrata.application.incremental.recommendation_execution import (
    IncrementalRecommendationExecutor,
)
from codestrata.application.incremental.rule_execution import (
    DefaultRuleScopeProvider,
    IncrementalRuleExecutor,
)
from codestrata.domain.assessment_graph import AssessmentGraph
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.graph.models import GraphSnapshot
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository_graph import RepositoryGraph
from codestrata.services.engineering_knowledge import load_builtin_engineering_knowledge_catalog
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.knowledge_pipeline import KnowledgePipeline
from tests.application.incremental.helpers import entry, manifest
from tests.application.knowledge.queries.conftest_helpers import (
    build_assessment_graph_payload,
    build_repository_graph_payload,
)


def _pipeline_result() -> GraphAssessmentPipelineResult:
    repo_payload = build_repository_graph_payload()
    snapshot = GraphSnapshot.model_validate(
        {
            "metadata": repo_payload["metadata"],
            "nodes": repo_payload["nodes"],
            "relationships": repo_payload["relationships"],
        }
    )
    repository_graph = RepositoryGraph(snapshot)
    knowledge_graph = load_builtin_engineering_knowledge_catalog()
    bindings = KnowledgePipeline().bind(repository_graph, knowledge_graph)
    module_node = next(
        node
        for node in repository_graph.nodes
        if node.properties.get("name") == "module-a"
    )
    assessment_payload = build_assessment_graph_payload(module_node)
    assessment_graph = AssessmentGraph(GraphSnapshot.model_validate(assessment_payload))
    return GraphAssessmentPipelineResult(
        manifest=manifest(entry("a/A.java", "a" * 64)),
        repository_graph=repository_graph,
        knowledge_graph=knowledge_graph,
        binding_result=bindings,
        assessment_graph=assessment_graph,
    )


def test_default_rule_scope_not_selective() -> None:
    assert DefaultRuleScopeProvider().supports_selective_execution() is False


def test_rule_and_recommendation_full_rerun() -> None:
    pipeline = _pipeline_result()
    evaluation, reused, recomputed = IncrementalRuleExecutor().execute(pipeline)
    assert reused == 0
    assert recomputed == len(evaluation.findings)
    result, reused_r, recomputed_r = IncrementalRecommendationExecutor().execute(
        pipeline_result=pipeline,
        evaluation=evaluation,
    )
    assert isinstance(result, RecommendationResult)
    assert reused_r == 0
    assert recomputed_r == len(result.recommendations)


def test_artifact_merger_and_validator() -> None:
    pipeline = _pipeline_result()
    evaluation = RuleEvaluationResult.from_findings(
        findings=(),
        rules_evaluated=(),
    )
    recommendations = RecommendationResult.from_recommendations(
        recommendations=(),
        providers_evaluated=(),
    )
    package, reuse, recompute = IncrementalArtifactMerger().merge(
        manifest=pipeline.manifest,
        pipeline_result=pipeline,
        rule_evaluation=evaluation,
        recommendation_result=recommendations,
        reused_files=3,
        recomputed_files=1,
    )
    IncrementalMergeValidator().validate(package)
    assert reuse.files == 3
    assert recompute.files == 1
    assert recompute.repository_graph_nodes >= 1
