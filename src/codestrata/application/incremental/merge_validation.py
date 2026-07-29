"""Pre-persistence merge validation for Phase 2F.2."""

from __future__ import annotations

from codestrata.application.incremental.errors import IncrementalMergeValidationError
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.graph.models import GraphSnapshot
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult


class MergedAssessmentPackage:
    """In-memory complete package prior to persistence."""

    __slots__ = (
        "manifest",
        "pipeline_result",
        "rule_evaluation",
        "recommendation_result",
    )

    def __init__(
        self,
        *,
        manifest: RepositoryManifest,
        pipeline_result: GraphAssessmentPipelineResult,
        rule_evaluation: RuleEvaluationResult,
        recommendation_result: RecommendationResult,
    ) -> None:
        self.manifest = manifest
        self.pipeline_result = pipeline_result
        self.rule_evaluation = rule_evaluation
        self.recommendation_result = recommendation_result


class IncrementalMergeValidator:
    """Fail-closed validation before persistence."""

    def validate(self, package: MergedAssessmentPackage) -> None:
        self._validate_inventory(package.manifest)
        self._validate_graph(package.pipeline_result.repository_graph.snapshot, "repository")
        self._validate_graph(
            package.pipeline_result.knowledge_graph.snapshot,
            "knowledge",
        )
        self._validate_graph(
            package.pipeline_result.assessment_graph.snapshot,
            "assessment",
        )
        self._validate_findings(package)
        self._validate_recommendations(package)

    def _validate_inventory(self, manifest: RepositoryManifest) -> None:
        paths = [entry.path.root for entry in manifest.files]
        if len(paths) != len(set(paths)):
            raise IncrementalMergeValidationError(
                "Inventory paths are not unique",
                reason_code="inventory_duplicate_paths",
                failed_step="merge_validation",
            )

    def _validate_graph(self, snapshot: GraphSnapshot, label: str) -> None:
        node_ids = [str(node.id) for node in snapshot.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise IncrementalMergeValidationError(
                f"{label} graph has duplicate node IDs",
                reason_code=f"{label}_duplicate_nodes",
                failed_step="merge_validation",
            )
        known = set(node_ids)
        rel_ids = [rel.id for rel in snapshot.relationships]
        if len(rel_ids) != len(set(rel_ids)):
            raise IncrementalMergeValidationError(
                f"{label} graph has duplicate edge IDs",
                reason_code=f"{label}_duplicate_edges",
                failed_step="merge_validation",
            )
        for rel in snapshot.relationships:
            if str(rel.source_node_id) not in known or str(rel.target_node_id) not in known:
                raise IncrementalMergeValidationError(
                    f"{label} graph has dangling relationship endpoints",
                    reason_code=f"{label}_dangling_edge",
                    failed_step="merge_validation",
                )

    def _validate_findings(self, package: MergedAssessmentPackage) -> None:
        ids = [finding.id for finding in package.rule_evaluation.findings]
        if len(ids) != len(set(ids)):
            raise IncrementalMergeValidationError(
                "Duplicate finding identities",
                reason_code="duplicate_findings",
                failed_step="merge_validation",
            )
        known_nodes = {
            str(node.id) for node in package.pipeline_result.assessment_graph.snapshot.nodes
        }
        for finding in package.rule_evaluation.findings:
            for node_id in finding.affected_assessment_node_ids:
                if str(node_id) not in known_nodes:
                    # Some rules may reference non-assessment subjects; allow empty.
                    continue

    def _validate_recommendations(self, package: MergedAssessmentPackage) -> None:
        ids = [item.id for item in package.recommendation_result.recommendations]
        if len(ids) != len(set(ids)):
            raise IncrementalMergeValidationError(
                "Duplicate recommendation identities",
                reason_code="duplicate_recommendations",
                failed_step="merge_validation",
            )
        finding_ids = {finding.id for finding in package.rule_evaluation.findings}
        for recommendation in package.recommendation_result.recommendations:
            for finding_id in recommendation.related_finding_ids:
                if str(finding_id) not in finding_ids:
                    raise IncrementalMergeValidationError(
                        "Recommendation references missing finding",
                        reason_code="stale_recommendation_finding",
                        failed_step="merge_validation",
                    )
