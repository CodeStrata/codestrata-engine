"""Deterministic explainability for incremental executions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.incremental.execution_models import IncrementalExecutionResult
from codestrata.application.incremental.models import IncrementalAssessmentPlan
from codestrata.application.incremental.validation_models import IncrementalValidationResult


class IncrementalExplanationKind(StrEnum):
    EXECUTION_MODE = "execution_mode"
    FALLBACK = "fallback"
    FILE_REUSE = "file_reuse"
    FILE_RECOMPUTE = "file_recompute"
    GRAPH_REUSE = "graph_reuse"
    GRAPH_RECOMPUTE = "graph_recompute"
    FINDING_REUSE = "finding_reuse"
    FINDING_RECOMPUTE = "finding_recompute"
    RECOMMENDATION_REUSE = "recommendation_reuse"
    RECOMMENDATION_RECOMPUTE = "recommendation_recompute"
    ROADMAP = "roadmap"
    AI = "ai"
    VALIDATION = "validation"
    COMPATIBILITY = "compatibility"


class IncrementalExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation_id: str
    kind: IncrementalExplanationKind
    subject_kind: str | None = None
    subject_id: str | None = None
    summary: str
    reason_codes: tuple[str, ...] = ()
    related_subject_ids: tuple[str, ...] = ()
    fingerprint_checks: tuple[str, ...] = ()
    compatibility_checks: tuple[str, ...] = ()
    impact_reasons: tuple[str, ...] = ()
    plan_step_ids: tuple[str, ...] = ()
    safe_metadata: dict[str, Any] = Field(default_factory=dict)


class ExplanationFilters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: IncrementalExplanationKind | None = None
    subject_id: str | None = None
    limit: int = Field(default=100, ge=1, le=10_000)


class IncrementalExplainabilityService:
    """Build bounded, deterministic explanations (no LLM)."""

    def explain(
        self,
        *,
        execution: IncrementalExecutionResult,
        plan: IncrementalAssessmentPlan | None = None,
        validation: IncrementalValidationResult | None = None,
        max_explanations: int = 500,
    ) -> tuple[IncrementalExplanation, ...]:
        items: list[IncrementalExplanation] = []

        items.append(
            IncrementalExplanation(
                explanation_id=str(uuid4()),
                kind=IncrementalExplanationKind.EXECUTION_MODE,
                subject_kind="execution",
                subject_id=execution.execution_id,
                summary=(
                    f"Actual execution mode is {execution.mode.value}; "
                    f"status is {execution.status.value}"
                ),
                reason_codes=(execution.mode.value, execution.status.value),
            )
        )

        if execution.fallback_used or execution.fallback_reasons:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.FALLBACK,
                    subject_kind="execution",
                    subject_id=execution.execution_id,
                    summary="Full-rebuild fallback was used",
                    reason_codes=tuple(sorted(set(execution.fallback_reasons))),
                )
            )
        elif plan is not None and not plan.full_rebuild_required:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.EXECUTION_MODE,
                    subject_kind="plan",
                    subject_id=plan.plan_id,
                    summary="Incremental execution was allowed by plan mode and compatibility",
                    reason_codes=(plan.mode.value, "incremental_allowed"),
                )
            )

        if plan is not None and plan.compatibility is not None:
            compat = plan.compatibility
            check_flags = tuple(
                name
                for name, ok in (
                    ("scanner", compat.scanner_compatible),
                    ("parser", compat.parser_compatible),
                    ("graph", compat.graph_compatible),
                    ("rule", compat.rule_compatible),
                    ("recommendation", compat.recommendation_compatible),
                    ("artifact_schema", compat.artifact_schema_compatible),
                    ("tool", compat.tool_compatible),
                )
                if ok
            )
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.COMPATIBILITY,
                    subject_kind="compatibility",
                    subject_id=plan.plan_id,
                    summary=(
                        "Compatibility established"
                        if compat.compatible
                        else "Compatibility not established"
                    ),
                    reason_codes=tuple(sorted(set(compat.blocking_reasons))),
                    compatibility_checks=check_flags,
                )
            )

        if plan is not None:
            change = plan.change_summary or {}
            for path in list(change.get("added_paths", ()))[:50]:
                items.append(
                    IncrementalExplanation(
                        explanation_id=str(uuid4()),
                        kind=IncrementalExplanationKind.FILE_RECOMPUTE,
                        subject_kind="file",
                        subject_id=str(path),
                        summary="File was added and must be rescanned",
                        reason_codes=("file_added",),
                    )
                )
            for path in list(change.get("modified_paths", ()))[:50]:
                items.append(
                    IncrementalExplanation(
                        explanation_id=str(uuid4()),
                        kind=IncrementalExplanationKind.FILE_RECOMPUTE,
                        subject_kind="file",
                        subject_id=str(path),
                        summary="File was modified and must be rescanned",
                        reason_codes=("file_modified",),
                    )
                )
            for path in list(change.get("deleted_paths", ()))[:50]:
                items.append(
                    IncrementalExplanation(
                        explanation_id=str(uuid4()),
                        kind=IncrementalExplanationKind.FILE_RECOMPUTE,
                        subject_kind="file",
                        subject_id=str(path),
                        summary="File was deleted and must be removed from inventory",
                        reason_codes=("file_deleted",),
                    )
                )
            added_count = int(change.get("added_count", change.get("added", 0)) or 0)
            if not change.get("added_paths") and added_count:
                items.append(
                    IncrementalExplanation(
                        explanation_id=str(uuid4()),
                        kind=IncrementalExplanationKind.FILE_RECOMPUTE,
                        subject_kind="files",
                        summary=(
                            f"{int(change.get('added_count', change.get('added', 0)))} "
                            "files added and must be rescanned"
                        ),
                        reason_codes=("file_added",),
                    )
                )
            if not change.get("modified_paths") and int(
                change.get("modified_count", change.get("modified", 0)) or 0
            ):
                items.append(
                    IncrementalExplanation(
                        explanation_id=str(uuid4()),
                        kind=IncrementalExplanationKind.FILE_RECOMPUTE,
                        subject_kind="files",
                        summary=(
                            f"{int(change.get('modified_count', change.get('modified', 0)))} "
                            "files modified and must be rescanned"
                        ),
                        reason_codes=("file_modified",),
                    )
                )

        if execution.reused_counts.findings and not execution.fallback_used:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.FINDING_REUSE,
                    subject_kind="findings",
                    summary=f"{execution.reused_counts.findings} findings reused from base run",
                    reason_codes=("findings_reused",),
                    related_subject_ids=(execution.previous_run_id or "",),
                )
            )
        if execution.recomputed_counts.findings:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.FINDING_RECOMPUTE,
                    subject_kind="findings",
                    summary=(f"{execution.recomputed_counts.findings} findings regenerated"),
                    reason_codes=("findings_regenerated",),
                )
            )
        if execution.reused_counts.recommendations and not execution.fallback_used:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.RECOMMENDATION_REUSE,
                    subject_kind="recommendations",
                    summary=(f"{execution.reused_counts.recommendations} recommendations reused"),
                    reason_codes=("recommendations_reused",),
                )
            )
        if execution.recomputed_counts.recommendations:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.RECOMMENDATION_RECOMPUTE,
                    subject_kind="recommendations",
                    summary=(
                        f"{execution.recomputed_counts.recommendations} recommendations regenerated"
                    ),
                    reason_codes=("recommendations_regenerated",),
                )
            )

        items.append(
            IncrementalExplanation(
                explanation_id=str(uuid4()),
                kind=IncrementalExplanationKind.AI,
                subject_kind="ai",
                summary="AI artifact reuse is disabled; AI reruns when requested",
                reason_codes=("ai_reuse_disabled",),
            )
        )

        if validation is not None:
            items.append(
                IncrementalExplanation(
                    explanation_id=str(uuid4()),
                    kind=IncrementalExplanationKind.VALIDATION,
                    subject_kind="validation",
                    subject_id=validation.validation_id,
                    summary=f"Validation status is {validation.status.value}",
                    reason_codes=(validation.status.value,),
                    safe_metadata={
                        "blocking_count": len(validation.blocking_issues),
                        "warning_count": len(validation.warnings),
                        "equivalent_to_full": validation.equivalent_to_full,
                    },
                )
            )

        bounded = items[: max(1, max_explanations)]
        return tuple(
            sorted(
                bounded,
                key=lambda item: (item.kind.value, item.subject_id or "", item.summary),
            )
        )

    def filter_explanations(
        self,
        explanations: tuple[IncrementalExplanation, ...],
        filters: ExplanationFilters,
    ) -> tuple[IncrementalExplanation, ...]:
        selected = list(explanations)
        if filters.kind is not None:
            selected = [item for item in selected if item.kind is filters.kind]
        if filters.subject_id is not None:
            sid = filters.subject_id.strip()
            selected = [
                item
                for item in selected
                if item.subject_id == sid or sid in item.related_subject_ids
            ]
        return tuple(selected[: filters.limit])
