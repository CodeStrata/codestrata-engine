"""Post-execution incremental validation (deterministic, no AI)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.incremental.equivalence import CompleteAssessmentArtifacts
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionStatus,
)
from codestrata.application.incremental.validation_models import (
    IncrementalValidationCheck,
    IncrementalValidationCheckKind,
    IncrementalValidationIssue,
    IncrementalValidationRequest,
    IncrementalValidationResult,
    IncrementalValidationStatus,
)

logger = logging.getLogger(__name__)


def _as_artifacts(value: object) -> CompleteAssessmentArtifacts:
    from codestrata.application.incremental.equivalence import artifacts_from_assessment_result

    if isinstance(value, CompleteAssessmentArtifacts):
        return value
    return artifacts_from_assessment_result(value)


class IncrementalValidationService:
    """Validate incremental execution results after completion."""

    def validate(self, request: IncrementalValidationRequest) -> IncrementalValidationResult:
        started = datetime.now(UTC)
        checks: list[IncrementalValidationCheck] = []
        issues: list[IncrementalValidationIssue] = []

        checks.append(self._check_execution_integrity(request, issues))
        checks.append(self._check_plan_conformance(request, issues))
        checks.append(self._check_fallback_integrity(request, issues))
        checks.append(self._check_reuse_integrity(request, issues))
        checks.append(self._check_ai_integrity(request, issues))
        equivalence_summary: dict[str, object] = {}
        equivalent: bool | None = None
        if request.enable_equivalence_check and request.full_reference is not None:
            from codestrata.application.incremental.equivalence import (
                AssessmentSemanticComparator,
            )

            t0 = time.perf_counter()
            eq = AssessmentSemanticComparator(max_differences=request.max_issues).compare(
                _as_artifacts(request.execution.assessment_result),
                _as_artifacts(request.full_reference),
            )
            equivalent = eq.equivalent
            equivalence_summary = {
                "equivalent": eq.equivalent,
                "difference_count": len(eq.differences),
            }
            eq_issues: list[IncrementalValidationIssue] = []
            if not eq.equivalent:
                eq_issues.append(
                    IncrementalValidationIssue(
                        code="not_semantically_equivalent",
                        check_kind=IncrementalValidationCheckKind.SEMANTIC_EQUIVALENCE,
                        severity="error",
                        safe_message=(
                            "Incremental result is not semantically equivalent to full assessment"
                        ),
                        blocking=True,
                        metadata={"differences": list(eq.differences)[: request.max_issues]},
                    )
                )
                issues.extend(eq_issues)
            checks.append(
                IncrementalValidationCheck(
                    kind=IncrementalValidationCheckKind.SEMANTIC_EQUIVALENCE,
                    status=(
                        IncrementalValidationStatus.FAILED
                        if eq_issues
                        else IncrementalValidationStatus.PASSED
                    ),
                    issues=tuple(eq_issues),
                    checked_count=1,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            )

        blocking = tuple(item for item in issues if item.blocking)
        warnings = tuple(item for item in issues if not item.blocking)
        if blocking:
            status = IncrementalValidationStatus.FAILED
        elif warnings:
            status = IncrementalValidationStatus.PASSED_WITH_WARNINGS
        else:
            status = IncrementalValidationStatus.PASSED

        result = IncrementalValidationResult(
            validation_id=str(uuid4()),
            execution_id=request.execution.execution_id,
            plan_id=request.execution.plan_id,
            repository_id=request.execution.repository_id,
            run_id=request.execution.run_id,
            status=status,
            checks=tuple(checks),
            blocking_issues=blocking[: request.max_issues],
            warnings=warnings[: request.max_issues],
            equivalent_to_full=equivalent,
            equivalence_summary=equivalence_summary,
            started_at=started,
            completed_at=datetime.now(UTC),
        )
        logger.info(
            "incremental.validation_complete",
            extra={
                "validation_id": result.validation_id,
                "execution_id": result.execution_id,
                "status": result.status.value,
                "blocking_count": len(result.blocking_issues),
            },
        )
        return result

    def _check_execution_integrity(
        self,
        request: IncrementalValidationRequest,
        issues: list[IncrementalValidationIssue],
    ) -> IncrementalValidationCheck:
        t0 = time.perf_counter()
        local: list[IncrementalValidationIssue] = []
        execution = request.execution
        if execution.status not in {
            IncrementalExecutionStatus.COMPLETED,
            IncrementalExecutionStatus.FALLBACK_COMPLETED,
        }:
            local.append(
                IncrementalValidationIssue(
                    code="execution_not_completed",
                    check_kind=IncrementalValidationCheckKind.EXECUTION_INTEGRITY,
                    safe_message=f"Execution status is {execution.status.value}",
                    blocking=True,
                )
            )
        if execution.run_id is None or execution.snapshot_id is None:
            local.append(
                IncrementalValidationIssue(
                    code="missing_run_or_snapshot",
                    check_kind=IncrementalValidationCheckKind.EXECUTION_INTEGRITY,
                    safe_message="Completed execution must produce run_id and snapshot_id",
                    blocking=True,
                )
            )
        if execution.assessment_result is None:
            local.append(
                IncrementalValidationIssue(
                    code="missing_assessment_result",
                    check_kind=IncrementalValidationCheckKind.EXECUTION_INTEGRITY,
                    safe_message="Completed execution must include assessment_result",
                    blocking=True,
                )
            )
        issues.extend(local)
        return IncrementalValidationCheck(
            kind=IncrementalValidationCheckKind.EXECUTION_INTEGRITY,
            status=(
                IncrementalValidationStatus.FAILED if local else IncrementalValidationStatus.PASSED
            ),
            issues=tuple(local),
            checked_count=3,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _check_plan_conformance(
        self,
        request: IncrementalValidationRequest,
        issues: list[IncrementalValidationIssue],
    ) -> IncrementalValidationCheck:
        t0 = time.perf_counter()
        local: list[IncrementalValidationIssue] = []
        plan = request.plan
        execution = request.execution
        if plan is not None and plan.full_rebuild_required and not execution.fallback_used:
            if execution.mode is not IncrementalExecutionMode.FULL_REBUILD_FALLBACK:
                local.append(
                    IncrementalValidationIssue(
                        code="plan_required_full_rebuild_not_honored",
                        check_kind=IncrementalValidationCheckKind.PLAN_CONFORMANCE,
                        safe_message="Plan required full rebuild but execution did not fall back",
                        blocking=True,
                    )
                )
        if plan is not None and execution.plan_id not in {None, plan.plan_id}:
            local.append(
                IncrementalValidationIssue(
                    code="plan_id_mismatch",
                    check_kind=IncrementalValidationCheckKind.PLAN_CONFORMANCE,
                    safe_message="Execution plan_id does not match provided plan",
                    blocking=True,
                    related_ids=(execution.plan_id or "", plan.plan_id),
                )
            )
        issues.extend(local)
        return IncrementalValidationCheck(
            kind=IncrementalValidationCheckKind.PLAN_CONFORMANCE,
            status=(
                IncrementalValidationStatus.FAILED if local else IncrementalValidationStatus.PASSED
            ),
            issues=tuple(local),
            checked_count=2,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _check_fallback_integrity(
        self,
        request: IncrementalValidationRequest,
        issues: list[IncrementalValidationIssue],
    ) -> IncrementalValidationCheck:
        t0 = time.perf_counter()
        local: list[IncrementalValidationIssue] = []
        execution = request.execution
        if execution.fallback_used:
            if not execution.fallback_reasons:
                local.append(
                    IncrementalValidationIssue(
                        code="fallback_missing_reasons",
                        check_kind=IncrementalValidationCheckKind.FALLBACK_INTEGRITY,
                        safe_message="Fallback used without reason codes",
                        blocking=True,
                    )
                )
            if execution.mode is not IncrementalExecutionMode.FULL_REBUILD_FALLBACK:
                local.append(
                    IncrementalValidationIssue(
                        code="fallback_mode_mismatch",
                        check_kind=IncrementalValidationCheckKind.FALLBACK_INTEGRITY,
                        safe_message="fallback_used is true but mode is not full_rebuild_fallback",
                        blocking=True,
                    )
                )
        issues.extend(local)
        return IncrementalValidationCheck(
            kind=IncrementalValidationCheckKind.FALLBACK_INTEGRITY,
            status=(
                IncrementalValidationStatus.FAILED if local else IncrementalValidationStatus.PASSED
            ),
            issues=tuple(local),
            checked_count=2,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _check_reuse_integrity(
        self,
        request: IncrementalValidationRequest,
        issues: list[IncrementalValidationIssue],
    ) -> IncrementalValidationCheck:
        t0 = time.perf_counter()
        local: list[IncrementalValidationIssue] = []
        execution = request.execution
        if execution.fallback_used:
            # Discarded partial reuse must not appear as final reuse.
            if execution.reused_counts.findings or execution.reused_counts.recommendations:
                local.append(
                    IncrementalValidationIssue(
                        code="fallback_with_reuse_counts",
                        check_kind=IncrementalValidationCheckKind.REUSE_INTEGRITY,
                        severity="warning",
                        safe_message="Fallback result reported reuse counts; treating as warning",
                        blocking=False,
                    )
                )
        if execution.reused_counts.ai_artifacts > 0:
            local.append(
                IncrementalValidationIssue(
                    code="ai_reuse_not_allowed",
                    check_kind=IncrementalValidationCheckKind.AI_ARTIFACT_INTEGRITY,
                    safe_message="AI artifact reuse is disabled in Phase 2F.3",
                    blocking=True,
                )
            )
        issues.extend(local)
        status = IncrementalValidationStatus.PASSED
        if any(item.blocking for item in local):
            status = IncrementalValidationStatus.FAILED
        elif local:
            status = IncrementalValidationStatus.PASSED_WITH_WARNINGS
        return IncrementalValidationCheck(
            kind=IncrementalValidationCheckKind.REUSE_INTEGRITY,
            status=status,
            issues=tuple(local),
            checked_count=2,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _check_ai_integrity(
        self,
        request: IncrementalValidationRequest,
        issues: list[IncrementalValidationIssue],
    ) -> IncrementalValidationCheck:
        t0 = time.perf_counter()
        local: list[IncrementalValidationIssue] = []
        if request.execution.reused_counts.ai_artifacts > 0:
            local.append(
                IncrementalValidationIssue(
                    code="ai_artifacts_reused",
                    check_kind=IncrementalValidationCheckKind.AI_ARTIFACT_INTEGRITY,
                    safe_message="AI artifacts must not be reused",
                    blocking=True,
                )
            )
        issues.extend(local)
        return IncrementalValidationCheck(
            kind=IncrementalValidationCheckKind.AI_ARTIFACT_INTEGRITY,
            status=(
                IncrementalValidationStatus.FAILED if local else IncrementalValidationStatus.PASSED
            ),
            issues=tuple(local),
            checked_count=1,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
