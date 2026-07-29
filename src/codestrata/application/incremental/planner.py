"""Deterministic incremental assessment planner (planning only)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.incremental.models import (
    CompatibilityResult,
    ImpactAnalysis,
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
    IncrementalPlanStep,
    IncrementalStepType,
    RepositoryChangeSet,
    ReuseAssessment,
    ReuseDecision,
)
from codestrata.application.incremental.policies import IncrementalPlanningPolicy

logger = logging.getLogger(__name__)


class IncrementalPlanner:
    """Build a deterministic plan without executing assessment work."""

    def plan(
        self,
        *,
        repository_id: str | None,
        previous_run_id: str | None,
        previous_snapshot_id: str | None,
        candidate_snapshot_id: str | None,
        changes: RepositoryChangeSet,
        compatibility: CompatibilityResult,
        impact: ImpactAnalysis,
        reuse: tuple[ReuseAssessment, ...],
        policy: IncrementalPlanningPolicy | None = None,
        warnings: tuple[str, ...] = (),
    ) -> IncrementalAssessmentPlan:
        policy = policy or IncrementalPlanningPolicy()
        rebuild_reasons: list[str] = []
        if impact.requires_full_rebuild:
            rebuild_reasons.extend(impact.full_rebuild_reasons)
        if not compatibility.compatible:
            rebuild_reasons.extend(compatibility.blocking_reasons)
        if any(item.decision is ReuseDecision.FULL_REBUILD for item in reuse):
            rebuild_reasons.append("reuse_policy_full_rebuild")
        if any(item.decision is ReuseDecision.UNSUPPORTED for item in reuse):
            rebuild_reasons.append("reuse_unsupported")

        unique_rebuild = tuple(dict.fromkeys(rebuild_reasons))
        mode = _select_mode(changes, unique_rebuild, policy)

        if mode is IncrementalPlanMode.FULL_REBUILD or unique_rebuild:
            steps = (
                IncrementalPlanStep(
                    sequence=1,
                    step_type=IncrementalStepType.FULL_REBUILD,
                    reasons=unique_rebuild or ("full_rebuild_required",),
                ),
            )
            plan = IncrementalAssessmentPlan(
                plan_id=str(uuid4()),
                mode=IncrementalPlanMode.FULL_REBUILD,
                repository_id=repository_id,
                previous_run_id=previous_run_id,
                previous_snapshot_id=previous_snapshot_id,
                candidate_snapshot_id=candidate_snapshot_id,
                compatibility=compatibility,
                change_summary=_change_summary(changes),
                impact_summary=_impact_summary(impact),
                reuse_summary=_reuse_summary(reuse),
                steps=steps,
                full_rebuild_required=True,
                full_rebuild_reasons=unique_rebuild or ("full_rebuild_required",),
                warnings=warnings,
                created_at=datetime.now(UTC),
            )
            _log_plan(plan)
            return plan

        built_steps = _build_reuse_steps(reuse, changes, impact, mode)
        plan = IncrementalAssessmentPlan(
            plan_id=str(uuid4()),
            mode=mode,
            repository_id=repository_id,
            previous_run_id=previous_run_id,
            previous_snapshot_id=previous_snapshot_id,
            candidate_snapshot_id=candidate_snapshot_id,
            compatibility=compatibility,
            change_summary=_change_summary(changes),
            impact_summary=_impact_summary(impact),
            reuse_summary=_reuse_summary(reuse),
            steps=tuple(built_steps),
            full_rebuild_required=False,
            full_rebuild_reasons=(),
            warnings=warnings,
            created_at=datetime.now(UTC),
        )
        _log_plan(plan)
        return plan


def _select_mode(
    changes: RepositoryChangeSet,
    rebuild_reasons: tuple[str, ...],
    policy: IncrementalPlanningPolicy,
) -> IncrementalPlanMode:
    if rebuild_reasons:
        return IncrementalPlanMode.FULL_REBUILD
    if changes.change_count == 0:
        return IncrementalPlanMode.NO_CHANGES
    if changes.has_documentation_only_changes or (
        policy.allow_metadata_only_noop
        and changes.metadata_changed
        and not changes.added
        and not changes.modified
        and not changes.deleted
        and not changes.unknown
    ):
        return IncrementalPlanMode.METADATA_ONLY
    return IncrementalPlanMode.INCREMENTAL_CANDIDATE


def _build_reuse_steps(
    reuse: tuple[ReuseAssessment, ...],
    changes: RepositoryChangeSet,
    impact: ImpactAnalysis,
    mode: IncrementalPlanMode,
) -> list[IncrementalPlanStep]:
    by_subject = {item.subject_kind: item for item in reuse}
    steps: list[IncrementalPlanStep] = []
    sequence = 1

    def add(
        step_type: IncrementalStepType,
        *,
        reasons: tuple[str, ...] = (),
        subject_ids: tuple[str, ...] = (),
        depends_on: tuple[int, ...] = (),
        reusable: int = 0,
        recompute: int = 0,
    ) -> int:
        nonlocal sequence
        steps.append(
            IncrementalPlanStep(
                sequence=sequence,
                step_type=step_type,
                subject_ids=subject_ids,
                reasons=reasons,
                depends_on_steps=depends_on,
                reusable_count=reusable,
                recompute_count=recompute,
            )
        )
        current = sequence
        sequence += 1
        return current

    inventory = by_subject.get("inventory")
    if inventory is not None and inventory.decision is ReuseDecision.REUSABLE:
        inv_seq = add(
            IncrementalStepType.REUSE_INVENTORY,
            reasons=inventory.reasons,
            reusable=1,
        )
    else:
        inv_seq = add(
            IncrementalStepType.RECOMPUTE_INVENTORY,
            reasons=inventory.reasons if inventory else ("inventory_recompute",),
            recompute=1,
        )

    tech = by_subject.get("technology_detection")
    if tech is not None and tech.decision is ReuseDecision.REUSABLE:
        tech_seq = add(
            IncrementalStepType.REUSE_TECHNOLOGY_DETECTION,
            reasons=tech.reasons,
            depends_on=(inv_seq,),
            reusable=1,
        )
    else:
        tech_seq = add(
            IncrementalStepType.RECOMPUTE_TECHNOLOGY_DETECTION,
            reasons=tech.reasons if tech else ("technology_recompute",),
            depends_on=(inv_seq,),
            recompute=1,
        )

    repo_graph = by_subject.get("repository_graph")
    if repo_graph is not None and repo_graph.decision is ReuseDecision.REUSABLE:
        rg_seq = add(
            IncrementalStepType.REUSE_REPOSITORY_GRAPH,
            reasons=repo_graph.reasons,
            depends_on=(tech_seq,),
            reusable=1,
        )
    elif mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE and impact.impacted_components:
        rg_seq = add(
            IncrementalStepType.RECOMPUTE_IMPACTED_REPOSITORY_GRAPH,
            reasons=repo_graph.reasons if repo_graph else ("impacted_graph",),
            subject_ids=tuple(item.entity_id for item in impact.impacted_components),
            depends_on=(tech_seq,),
            recompute=len(impact.impacted_components),
        )
    else:
        rg_seq = add(
            IncrementalStepType.REBUILD_REPOSITORY_GRAPH,
            reasons=repo_graph.reasons if repo_graph else ("rebuild_graph",),
            depends_on=(tech_seq,),
            recompute=1,
        )

    ekg = by_subject.get("engineering_knowledge_graph")
    if ekg is not None and ekg.decision is ReuseDecision.REUSABLE:
        ekg_seq = add(
            IncrementalStepType.REUSE_KNOWLEDGE_GRAPH,
            reasons=ekg.reasons,
            depends_on=(rg_seq,),
            reusable=1,
        )
    elif mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE:
        ekg_seq = add(
            IncrementalStepType.RECOMPUTE_IMPACTED_KNOWLEDGE_GRAPH,
            reasons=ekg.reasons if ekg else ("impacted_knowledge",),
            depends_on=(rg_seq,),
            recompute=1,
        )
    else:
        ekg_seq = add(
            IncrementalStepType.REBUILD_KNOWLEDGE_GRAPH,
            reasons=ekg.reasons if ekg else ("rebuild_knowledge",),
            depends_on=(rg_seq,),
            recompute=1,
        )

    ag = by_subject.get("assessment_graph")
    if ag is not None and ag.decision is ReuseDecision.REUSABLE:
        ag_seq = add(
            IncrementalStepType.REUSE_ASSESSMENT_GRAPH,
            reasons=ag.reasons,
            depends_on=(ekg_seq,),
            reusable=1,
        )
    elif mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE:
        ag_seq = add(
            IncrementalStepType.RECOMPUTE_IMPACTED_ASSESSMENT_GRAPH,
            reasons=ag.reasons if ag else ("impacted_assessment",),
            depends_on=(ekg_seq,),
            recompute=1,
        )
    else:
        ag_seq = add(
            IncrementalStepType.REBUILD_ASSESSMENT_GRAPH,
            reasons=ag.reasons if ag else ("rebuild_assessment",),
            depends_on=(ekg_seq,),
            recompute=1,
        )

    findings = by_subject.get("findings")
    if findings is not None and findings.decision is ReuseDecision.REUSABLE:
        find_seq = add(
            IncrementalStepType.REUSE_FINDINGS,
            reasons=findings.reasons,
            depends_on=(ag_seq,),
            reusable=1,
        )
    elif mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE and impact.impacted_findings:
        find_seq = add(
            IncrementalStepType.RERUN_IMPACTED_RULES,
            reasons=findings.reasons if findings else ("impacted_rules",),
            subject_ids=tuple(item.entity_id for item in impact.impacted_findings),
            depends_on=(ag_seq,),
            recompute=len(impact.impacted_findings),
            reusable=max(0, 0),
        )
    else:
        find_seq = add(
            IncrementalStepType.RERUN_ALL_RULES,
            reasons=findings.reasons if findings else ("rerun_all_rules",),
            depends_on=(ag_seq,),
            recompute=1,
        )

    recs = by_subject.get("recommendations")
    if recs is not None and recs.decision is ReuseDecision.REUSABLE:
        rec_seq = add(
            IncrementalStepType.REUSE_RECOMMENDATIONS,
            reasons=recs.reasons,
            depends_on=(find_seq,),
            reusable=1,
        )
    elif mode is IncrementalPlanMode.INCREMENTAL_CANDIDATE and impact.impacted_recommendations:
        rec_seq = add(
            IncrementalStepType.REGENERATE_IMPACTED_RECOMMENDATIONS,
            reasons=recs.reasons if recs else ("impacted_recommendations",),
            subject_ids=tuple(item.entity_id for item in impact.impacted_recommendations),
            depends_on=(find_seq,),
            recompute=len(impact.impacted_recommendations),
        )
    else:
        rec_seq = add(
            IncrementalStepType.REGENERATE_ALL_RECOMMENDATIONS,
            reasons=recs.reasons if recs else ("regenerate_all",),
            depends_on=(find_seq,),
            recompute=1,
        )

    ai = by_subject.get("ai_enrichment")
    if ai is not None and ai.decision is ReuseDecision.REUSABLE:
        ai_seq = add(
            IncrementalStepType.REUSE_AI_ENRICHMENT,
            reasons=ai.reasons,
            depends_on=(rec_seq,),
            reusable=1,
        )
    else:
        ai_seq = add(
            IncrementalStepType.RERUN_AI_ENRICHMENT,
            reasons=ai.reasons if ai else ("ai_recompute",),
            depends_on=(rec_seq,),
            recompute=1,
        )

    validate_seq = add(
        IncrementalStepType.VALIDATE_INCREMENTAL_RESULT,
        reasons=("planning_declaration_only",),
        depends_on=(ai_seq,),
    )
    add(
        IncrementalStepType.PERSIST_RESULT,
        reasons=("planning_declaration_only",),
        depends_on=(validate_seq,),
    )
    del changes  # used only for mode selection upstream
    return steps


def _change_summary(changes: RepositoryChangeSet) -> dict[str, object]:
    return {
        "change_count": changes.change_count,
        "unchanged_count": changes.unchanged_count,
        "added": len(changes.added),
        "modified": len(changes.modified),
        "deleted": len(changes.deleted),
        "metadata_changed": len(changes.metadata_changed),
        "unknown": len(changes.unknown),
        "has_source_changes": changes.has_source_changes,
        "has_build_changes": changes.has_build_changes,
        "has_configuration_changes": changes.has_configuration_changes,
        "has_dependency_manifest_changes": changes.has_dependency_manifest_changes,
        "has_documentation_only_changes": changes.has_documentation_only_changes,
    }


def _impact_summary(impact: ImpactAnalysis) -> dict[str, object]:
    return {
        "directly_changed_files": len(impact.directly_changed_files),
        "impacted_components": len(impact.impacted_components),
        "impacted_findings": len(impact.impacted_findings),
        "impacted_recommendations": len(impact.impacted_recommendations),
        "truncated": impact.truncated,
        "requires_full_rebuild": impact.requires_full_rebuild,
        "full_rebuild_reasons": list(impact.full_rebuild_reasons),
        "unknown_impacts": list(impact.unknown_impacts),
    }


def _reuse_summary(reuse: tuple[ReuseAssessment, ...]) -> dict[str, object]:
    counts = {
        "reusable": 0,
        "recompute": 0,
        "full_rebuild": 0,
        "unsupported": 0,
    }
    for item in reuse:
        counts[item.decision.value] = counts.get(item.decision.value, 0) + 1
    return {
        "counts": counts,
        "subjects": {item.subject_kind: item.decision.value for item in reuse},
    }


def _log_plan(plan: IncrementalAssessmentPlan) -> None:
    logger.info(
        "incremental.plan_created",
        extra={
            "plan_id": plan.plan_id,
            "repository_id": plan.repository_id,
            "previous_run_id": plan.previous_run_id,
            "previous_snapshot_id": plan.previous_snapshot_id,
            "mode": plan.mode.value,
            "changed_file_count": plan.change_summary.get("change_count"),
            "full_rebuild_required": plan.full_rebuild_required,
        },
    )
