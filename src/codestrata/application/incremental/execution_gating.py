"""Plan gating helpers for incremental execution."""

from __future__ import annotations

from codestrata.application.incremental.execution_policies import IncrementalExecutionPolicy
from codestrata.application.incremental.models import (
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
    IncrementalStepType,
)

_UNSUPPORTED_SELECTIVE_STEPS = frozenset(
    {
        IncrementalStepType.RECOMPUTE_IMPACTED_REPOSITORY_GRAPH,
        IncrementalStepType.RECOMPUTE_IMPACTED_KNOWLEDGE_GRAPH,
        IncrementalStepType.RECOMPUTE_IMPACTED_ASSESSMENT_GRAPH,
        IncrementalStepType.RERUN_IMPACTED_RULES,
        IncrementalStepType.REGENERATE_IMPACTED_RECOMMENDATIONS,
    }
)


def evaluate_selective_eligibility(
    plan: IncrementalAssessmentPlan,
    policy: IncrementalExecutionPolicy,
) -> tuple[bool, tuple[str, ...]]:
    """Return (eligible, reasons) for selective incremental execution."""

    reasons: list[str] = []
    if not policy.execution_enabled:
        reasons.append("execution_disabled")
    if not policy.enabled and not policy.execution_enabled:
        # execution_enabled is the hard gate; planning enabled alone is insufficient
        pass
    if plan.mode is IncrementalPlanMode.FULL_REBUILD or plan.full_rebuild_required:
        reasons.append("plan_requires_full_rebuild")
        reasons.extend(plan.full_rebuild_reasons)
    if plan.mode not in {
        IncrementalPlanMode.INCREMENTAL_CANDIDATE,
        IncrementalPlanMode.NO_CHANGES,
        IncrementalPlanMode.METADATA_ONLY,
    }:
        reasons.append("unsupported_plan_mode")
    if plan.compatibility is not None and not plan.compatibility.compatible:
        reasons.append("compatibility_failed")
        reasons.extend(plan.compatibility.blocking_reasons)

    impact = plan.impact_summary or {}
    if impact.get("truncated"):
        reasons.append("impact_truncated")
    if impact.get("requires_full_rebuild"):
        reasons.append("impact_requires_full_rebuild")
    unknown = impact.get("unknown_impacts") or []
    if any("unmapped_source" in str(item) for item in unknown):
        reasons.append("unknown_source_impact")
    if any(str(item) == "unclassified_source_change" for item in unknown):
        reasons.append("unknown_source_impact")

    change = plan.change_summary or {}
    change_count = int(change.get("change_count") or 0)
    if change_count > policy.max_changed_files:
        reasons.append("too_many_changed_files")

    for step in plan.steps:
        if step.step_type in _UNSUPPORTED_SELECTIVE_STEPS:
            # Stage-level execution still allowed: these become full stage recomputes.
            continue
        if step.step_type is IncrementalStepType.FULL_REBUILD:
            reasons.append("plan_contains_full_rebuild_step")

    # NO_CHANGES / METADATA_ONLY are eligible for stage reuse path when execution on.
    if plan.mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE:
        if not policy.allow_selective_scan:
            reasons.append("selective_scan_disabled")
        if not policy.allow_graph_merge:
            reasons.append("graph_merge_disabled")

    unique = tuple(dict.fromkeys(reasons))
    return (len(unique) == 0), unique
