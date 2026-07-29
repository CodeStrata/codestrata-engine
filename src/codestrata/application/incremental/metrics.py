"""Execution telemetry models and deterministic metrics calculation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.errors import IncrementalMetricsError
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionResult,
)
from codestrata.application.incremental.models import IncrementalAssessmentPlan


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    value = numerator / denominator
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return round(value, 6)


class IncrementalExecutionMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_duration_ms: int = Field(ge=0, default=0)
    planning_duration_ms: int = Field(ge=0, default=0)
    scanning_duration_ms: int = Field(ge=0, default=0)
    merge_duration_ms: int = Field(ge=0, default=0)
    rule_duration_ms: int = Field(ge=0, default=0)
    recommendation_duration_ms: int = Field(ge=0, default=0)
    validation_duration_ms: int = Field(ge=0, default=0)
    persistence_duration_ms: int = Field(ge=0, default=0)
    total_files: int = Field(ge=0, default=0)
    changed_files: int = Field(ge=0, default=0)
    added_files: int = Field(ge=0, default=0)
    modified_files: int = Field(ge=0, default=0)
    deleted_files: int = Field(ge=0, default=0)
    files_reused: int = Field(ge=0, default=0)
    files_rescanned: int = Field(ge=0, default=0)
    repository_graph_nodes_reused: int = Field(ge=0, default=0)
    repository_graph_nodes_recomputed: int = Field(ge=0, default=0)
    repository_graph_edges_reused: int = Field(ge=0, default=0)
    repository_graph_edges_recomputed: int = Field(ge=0, default=0)
    knowledge_graph_nodes_reused: int = Field(ge=0, default=0)
    knowledge_graph_nodes_recomputed: int = Field(ge=0, default=0)
    knowledge_graph_edges_reused: int = Field(ge=0, default=0)
    knowledge_graph_edges_recomputed: int = Field(ge=0, default=0)
    assessment_graph_nodes_reused: int = Field(ge=0, default=0)
    assessment_graph_nodes_recomputed: int = Field(ge=0, default=0)
    assessment_graph_edges_reused: int = Field(ge=0, default=0)
    assessment_graph_edges_recomputed: int = Field(ge=0, default=0)
    findings_reused: int = Field(ge=0, default=0)
    findings_regenerated: int = Field(ge=0, default=0)
    recommendations_reused: int = Field(ge=0, default=0)
    recommendations_regenerated: int = Field(ge=0, default=0)
    roadmap_reused: int = Field(ge=0, default=0)
    roadmap_regenerated: int = Field(ge=0, default=0)
    ai_artifacts_reused: int = Field(ge=0, default=0)
    ai_artifacts_regenerated: int = Field(ge=0, default=0)
    change_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    file_reuse_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    graph_reuse_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    finding_reuse_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    recommendation_reuse_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_reuse_ratio: float = Field(ge=0.0, le=1.0, default=0.0)
    fallback_used: bool = False
    fallback_reason_codes: tuple[str, ...] = ()
    metric_warnings: tuple[str, ...] = ()


class IncrementalMetricsCalculator:
    """Derive metrics from actual execution results (not plan estimates alone)."""

    def calculate(
        self,
        execution: IncrementalExecutionResult,
        *,
        plan: IncrementalAssessmentPlan | None = None,
        validation_duration_ms: int = 0,
        final_findings_count: int | None = None,
        final_recommendations_count: int | None = None,
    ) -> IncrementalExecutionMetrics:
        duration_ms = 0
        if execution.completed_at is not None:
            duration_ms = max(
                0,
                int((execution.completed_at - execution.started_at).total_seconds() * 1000),
            )

        fallback = execution.fallback_used or (
            execution.mode is IncrementalExecutionMode.FULL_REBUILD_FALLBACK
        )
        reuse = execution.reused_counts
        recompute = execution.recomputed_counts
        warnings: list[str] = []

        if fallback:
            # Discarded partial work must not count as reuse in the final result.
            files_reused = 0
            findings_reused = 0
            recommendations_reused = 0
            repo_nodes_reused = 0
            repo_edges_reused = 0
            knowledge_nodes_reused = 0
            knowledge_edges_reused = 0
            assessment_nodes_reused = 0
            assessment_edges_reused = 0
            roadmap_reused = 0
            ai_reused = 0
        else:
            files_reused = reuse.files
            findings_reused = reuse.findings
            recommendations_reused = reuse.recommendations
            repo_nodes_reused = reuse.repository_graph_nodes
            repo_edges_reused = reuse.repository_graph_edges
            knowledge_nodes_reused = reuse.knowledge_graph_nodes
            knowledge_edges_reused = reuse.knowledge_graph_edges
            assessment_nodes_reused = reuse.assessment_graph_nodes
            assessment_edges_reused = reuse.assessment_graph_edges
            roadmap_reused = reuse.roadmap_phases
            ai_reused = reuse.ai_artifacts

        files_rescanned = recompute.files
        findings_regenerated = recompute.findings
        recommendations_regenerated = recompute.recommendations

        added = modified = deleted = changed = total_files = 0
        if plan is not None:
            summary = plan.change_summary or {}
            added = int(summary.get("added_count", summary.get("added", 0)) or 0)
            modified = int(summary.get("modified_count", summary.get("modified", 0)) or 0)
            deleted = int(summary.get("deleted_count", summary.get("deleted", 0)) or 0)
            changed = int(summary.get("change_count", added + modified + deleted) or 0)
            unchanged = int(summary.get("unchanged_count", 0) or 0)
            total_files = changed + unchanged

        if final_findings_count is not None:
            if (
                findings_reused + findings_regenerated
                not in {
                    0,
                    final_findings_count,
                }
                and findings_reused + findings_regenerated != final_findings_count
            ):
                # Allow zero when counts were not tracked during stage rebuild.
                if findings_reused + findings_regenerated > 0:
                    warnings.append("findings_reuse_recompute_mismatch")
        if final_recommendations_count is not None:
            if (
                recommendations_reused + recommendations_regenerated > 0
                and recommendations_reused + recommendations_regenerated
                != final_recommendations_count
            ):
                warnings.append("recommendations_reuse_recompute_mismatch")

        if ai_reused > 0:
            raise IncrementalMetricsError(
                "AI artifact reuse must remain disabled",
                reason_code="ai_reuse_metrics_violation",
                execution_id=execution.execution_id,
                plan_id=execution.plan_id,
            )

        graph_reused = (
            repo_nodes_reused
            + repo_edges_reused
            + knowledge_nodes_reused
            + knowledge_edges_reused
            + assessment_nodes_reused
            + assessment_edges_reused
        )
        graph_recomputed = (
            recompute.repository_graph_nodes
            + recompute.repository_graph_edges
            + recompute.knowledge_graph_nodes
            + recompute.knowledge_graph_edges
            + recompute.assessment_graph_nodes
            + recompute.assessment_graph_edges
        )
        overall_reused = files_reused + findings_reused + recommendations_reused + graph_reused
        overall_total = overall_reused + (
            files_rescanned + findings_regenerated + recommendations_regenerated + graph_recomputed
        )

        return IncrementalExecutionMetrics(
            execution_duration_ms=duration_ms,
            validation_duration_ms=max(0, validation_duration_ms),
            total_files=total_files,
            changed_files=changed,
            added_files=added,
            modified_files=modified,
            deleted_files=deleted,
            files_reused=files_reused,
            files_rescanned=files_rescanned,
            repository_graph_nodes_reused=repo_nodes_reused,
            repository_graph_nodes_recomputed=recompute.repository_graph_nodes,
            repository_graph_edges_reused=repo_edges_reused,
            repository_graph_edges_recomputed=recompute.repository_graph_edges,
            knowledge_graph_nodes_reused=knowledge_nodes_reused,
            knowledge_graph_nodes_recomputed=recompute.knowledge_graph_nodes,
            knowledge_graph_edges_reused=knowledge_edges_reused,
            knowledge_graph_edges_recomputed=recompute.knowledge_graph_edges,
            assessment_graph_nodes_reused=assessment_nodes_reused,
            assessment_graph_nodes_recomputed=recompute.assessment_graph_nodes,
            assessment_graph_edges_reused=assessment_edges_reused,
            assessment_graph_edges_recomputed=recompute.assessment_graph_edges,
            findings_reused=findings_reused,
            findings_regenerated=findings_regenerated,
            recommendations_reused=recommendations_reused,
            recommendations_regenerated=recommendations_regenerated,
            roadmap_reused=roadmap_reused,
            roadmap_regenerated=recompute.roadmap_phases,
            ai_artifacts_reused=0,
            ai_artifacts_regenerated=recompute.ai_artifacts,
            change_ratio=_ratio(changed, total_files),
            file_reuse_ratio=_ratio(
                files_reused,
                max(total_files, files_reused + files_rescanned),
            ),
            graph_reuse_ratio=_ratio(
                graph_reused,
                (
                    max(graph_reused + graph_recomputed, 1)
                    if graph_reused or graph_recomputed
                    else 0
                ),
            ),
            finding_reuse_ratio=_ratio(
                findings_reused,
                max(findings_reused + findings_regenerated, final_findings_count or 0),
            ),
            recommendation_reuse_ratio=_ratio(
                recommendations_reused,
                max(
                    recommendations_reused + recommendations_regenerated,
                    final_recommendations_count or 0,
                ),
            ),
            overall_reuse_ratio=_ratio(overall_reused, overall_total),
            fallback_used=fallback,
            fallback_reason_codes=tuple(sorted(set(execution.fallback_reasons))),
            metric_warnings=tuple(sorted(set(warnings))),
        )
