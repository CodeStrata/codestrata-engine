"""Operational orchestrator for plan → execute → validate → record (2F.3)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from codestrata.application.incremental.equivalence import AssessmentSemanticComparator
from codestrata.application.incremental.errors import IncrementalRolloutDisabledError
from codestrata.application.incremental.execution import IncrementalAssessmentExecutor
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionRequest,
    IncrementalExecutionStatus,
)
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.explainability import IncrementalExplainabilityService
from codestrata.application.incremental.metrics import IncrementalMetricsCalculator
from codestrata.application.incremental.models import (
    IncrementalAssessmentPlan,
    IncrementalPlanningRequest,
)
from codestrata.application.incremental.provenance import IncrementalExecutionRecordStore
from codestrata.application.incremental.rollout import (
    IncrementalRolloutMode,
    IncrementalRolloutPolicy,
)
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.application.incremental.validation import IncrementalValidationService
from codestrata.application.incremental.validation_models import (
    IncrementalValidationRequest,
    IncrementalValidationStatus,
)

logger = logging.getLogger(__name__)


class IncrementalOperationsService:
    """Transport-neutral incremental plan/execute/inspect workflow."""

    def __init__(
        self,
        *,
        planning_service: IncrementalPlanningService,
        executor: IncrementalAssessmentExecutor | None = None,
        validation_service: IncrementalValidationService | None = None,
        metrics_calculator: IncrementalMetricsCalculator | None = None,
        explainability: IncrementalExplainabilityService | None = None,
        record_store: IncrementalExecutionRecordStore | None = None,
        rollout: IncrementalRolloutPolicy | None = None,
    ) -> None:
        self._planning = planning_service
        self._executor = executor
        self._validation = validation_service or IncrementalValidationService()
        self._metrics = metrics_calculator or IncrementalMetricsCalculator()
        self._explainability = explainability or IncrementalExplainabilityService()
        self._store = record_store
        self._rollout = rollout or IncrementalRolloutPolicy()

    def create_plan(
        self,
        request: IncrementalPlanningRequest,
    ) -> IncrementalAssessmentPlan:
        if not self._rollout.allows_planning:
            raise IncrementalRolloutDisabledError(
                "Incremental planning is disabled (rollout_mode=off)",
                reason_code="rollout_off",
            )
        return self._planning.create_plan(request)

    def execute(
        self,
        request: IncrementalExecutionRequest,
        *,
        plan: IncrementalAssessmentPlan | None = None,
        full_reference: Any | None = None,
        enable_equivalence_check: bool | None = None,
    ) -> IncrementalExecutionRecord:
        if not self._rollout.allows_execution:
            raise IncrementalRolloutDisabledError(
                "Incremental execution requires rollout_mode opt_in "
                f"(current={self._rollout.mode.value})",
                reason_code="rollout_blocks_execution",
            )
        if self._executor is None:
            raise IncrementalRolloutDisabledError(
                "Incremental executor is not configured",
                reason_code="executor_missing",
            )

        resolved_plan = plan or request.plan
        if resolved_plan is None:
            # Plan first when caller did not supply one.
            if request.candidate is None:
                raise IncrementalRolloutDisabledError(
                    "Plan or candidate state is required for incremental execution",
                    reason_code="missing_plan_or_candidate",
                )
            resolved_plan = self.create_plan(
                IncrementalPlanningRequest(
                    repository_identifier=request.repository,
                    previous_run_id=request.previous_run_id,
                    branch=request.branch,
                    candidate=request.candidate,
                )
            )

        exec_request = request.model_copy(update={"plan": resolved_plan})
        started = datetime.now(UTC)
        execution = self._executor.execute(exec_request)

        validation = None
        validation_ms = 0
        if self._rollout.validate_after_execution:
            t0 = time.perf_counter()
            eq_enabled = (
                self._rollout.enable_equivalence_check
                if enable_equivalence_check is None
                else enable_equivalence_check
            )
            reference = full_reference
            if eq_enabled and reference is None and execution.assessment_result is not None:
                # Equivalence requires an explicit full reference; skip silently when absent.
                eq_enabled = False
            validation = self._validation.validate(
                IncrementalValidationRequest(
                    execution=execution,
                    plan=resolved_plan,
                    candidate=request.candidate,
                    enable_equivalence_check=eq_enabled,
                    full_reference=reference,
                )
            )
            validation_ms = int((time.perf_counter() - t0) * 1000)

        result_obj = execution.assessment_result
        findings_count = int(getattr(result_obj, "findings_count", 0) or 0) if result_obj else None
        recommendations_count = (
            int(getattr(result_obj, "recommendations_count", 0) or 0) if result_obj else None
        )
        metrics = self._metrics.calculate(
            execution,
            plan=resolved_plan,
            validation_duration_ms=validation_ms,
            final_findings_count=findings_count,
            final_recommendations_count=recommendations_count,
        )

        explanations = self._explainability.explain(
            execution=execution,
            plan=resolved_plan,
            validation=validation,
            max_explanations=self._rollout.max_explanations,
        )

        trusted = True
        warnings = list(execution.warnings)
        if validation is not None:
            if validation.status is IncrementalValidationStatus.FAILED:
                trusted = False
                warnings.append("validation_failed")
            elif validation.status is IncrementalValidationStatus.PASSED_WITH_WARNINGS:
                warnings.append("validation_warnings")
            for issue in validation.blocking_issues:
                warnings.append(issue.code)
        if metrics.metric_warnings:
            warnings.extend(metrics.metric_warnings)
            if self._rollout.fallback_on_metric_inconsistency:
                # Mark untrusted when metrics are inconsistent; do not rewrite artifacts.
                if "findings_reuse_recompute_mismatch" in metrics.metric_warnings:
                    trusted = False

        record = IncrementalExecutionRecord(
            execution_id=execution.execution_id or str(uuid4()),
            plan_id=execution.plan_id or resolved_plan.plan_id,
            repository_id=execution.repository_id,
            base_run_id=execution.previous_run_id,
            base_snapshot_id=execution.previous_snapshot_id,
            run_id=execution.run_id,
            snapshot_id=execution.snapshot_id,
            requested_strategy=resolved_plan.mode,
            actual_mode=execution.mode,
            status=execution.status,
            fallback_used=execution.fallback_used,
            fallback_reasons=execution.fallback_reasons,
            compatibility_summary=_compat_summary(resolved_plan),
            change_summary=_change_summary(resolved_plan),
            impact_summary=_impact_summary(resolved_plan),
            reuse_summary=execution.reused_counts.model_dump(mode="json"),
            recompute_summary=execution.recomputed_counts.model_dump(mode="json"),
            metrics=metrics,
            validation=validation,
            explanations=explanations,
            warnings=tuple(sorted(set(warnings))),
            trusted=trusted,
            started_at=execution.started_at or started,
            completed_at=execution.completed_at or datetime.now(UTC),
        )

        if self._rollout.persist_execution_records and self._store is not None:
            self._store.save(record)

        logger.info(
            "incremental.operations_complete",
            extra={
                "execution_id": record.execution_id,
                "plan_id": record.plan_id,
                "repository_id": record.repository_id,
                "run_id": record.run_id,
                "actual_mode": record.actual_mode.value,
                "rollout_mode": self._rollout.mode.value,
                "validation_status": (validation.status.value if validation is not None else None),
                "trusted": record.trusted,
                "fallback_used": record.fallback_used,
                "overall_reuse_ratio": (
                    metrics.overall_reuse_ratio if metrics is not None else None
                ),
                "explanation_count": len(explanations),
            },
        )
        return record


def _compat_summary(plan: IncrementalAssessmentPlan) -> dict[str, Any]:
    if plan.compatibility is None:
        return {}
    c = plan.compatibility
    return {
        "compatible": c.compatible,
        "blocking_reasons": list(c.blocking_reasons),
    }


def _change_summary(plan: IncrementalAssessmentPlan) -> dict[str, Any]:
    return dict(plan.change_summary or {})


def _impact_summary(plan: IncrementalAssessmentPlan) -> dict[str, Any]:
    return dict(plan.impact_summary or {})


# Keep semantic comparator import reachable for diagnostic composition.
_ = (
    AssessmentSemanticComparator,
    IncrementalExecutionMode,
    IncrementalExecutionStatus,
    IncrementalRolloutMode,
)
