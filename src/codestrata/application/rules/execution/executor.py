"""Execute a launch-catalog plan through the E03.1 compiler and E03.2 operators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codestrata.application.rules.execution.budgets import (
    execution_budgets,
    operator_limits_from_budgets,
    wall_seconds_for_workload,
)
from codestrata.application.rules.execution.planner import LaunchExecutionPlan, PlannedRule
from codestrata.application.rules.execution.process_guard import (
    IsolatedOutcome,
    in_process_evaluate,
    run_isolated_evaluation,
)
from codestrata.application.rules.execution.purpose import admit_execution_purpose
from codestrata.domain.contracts.enums import (
    CoverageState,
    ExecutionPurpose,
    JobTerminalState,
    ResultStatus,
)
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.compiler_models import COMPILER_VERSION, ConditionPlan
from codestrata.domain.rules.deadlines import regex_timeout_seconds
from codestrata.domain.rules.errors import RuleEvidenceError
from codestrata.domain.rules.evidence_contract import (
    evidence_from_operator_members,
    validate_launch_evidence,
)
from codestrata.domain.rules.execution_models import (
    LaunchDiagnostic,
    LaunchEvidence,
    LaunchExecutionBody,
    LaunchRuleRecord,
)
from codestrata.domain.rules.operators.models import OperatorContext, OperatorResult


def _plan_uses_matches(plan: ConditionPlan) -> bool:
    if plan.operator == "matches":
        return True
    return any(_plan_uses_matches(operand) for operand in plan.operands)


def _deadline_for_rule(plan: ConditionPlan, budgets: BudgetLimits) -> float:
    if _plan_uses_matches(plan):
        return min(float(budgets.rule_hard_deadline_seconds), regex_timeout_seconds(budgets))
    return float(budgets.rule_hard_deadline_seconds)


def _facts_digest(context: OperatorContext) -> str:
    payload = context.model_dump(mode="json")
    payload.pop("limits", None)
    return digest_canonical(payload)


def _record_for_unselected(entry: PlannedRule) -> LaunchRuleRecord:
    status = ResultStatus.ERROR if entry.coverage_state is CoverageState.ERROR else None
    return LaunchRuleRecord(
        rule_id=entry.rule_id,
        rule_revision=entry.rule_revision,
        plan_digest=entry.plan.plan_digest if entry.plan is not None else "uncompiled",
        status=status,
        coverage_state=entry.coverage_state,
        enabled=entry.enabled,
        suppressed=entry.suppressed,
        reason=entry.reason,
        diagnostics=(
            ()
            if entry.reason is None
            else (LaunchDiagnostic(code=entry.reason, message=entry.reason, rule_id=entry.rule_id),)
        ),
    )


def _bound_diagnostics(
    items: tuple[LaunchDiagnostic, ...],
    budgets: BudgetLimits,
) -> tuple[LaunchDiagnostic, ...]:
    encoded = 0
    kept: list[LaunchDiagnostic] = []
    for item in items:
        size = len(item.message.encode("utf-8"))
        if encoded + size > budgets.max_output_artifact_bytes:
            kept.append(
                LaunchDiagnostic(
                    code="diagnostic_truncated",
                    message="bounded diagnostics truncated",
                    rule_id=item.rule_id,
                )
            )
            break
        kept.append(item)
        encoded += size
    return tuple(kept)


def _result_from_outcome(
    entry: PlannedRule,
    outcome: IsolatedOutcome,
    *,
    evidence_paths: dict[str, str],
    extractor_version: str,
    budgets: BudgetLimits,
) -> LaunchRuleRecord:
    if outcome.terminal is not JobTerminalState.COMPLETED or outcome.result is None:
        failure_reason = outcome.reason or "process_terminated"
        diagnostics = tuple(
            LaunchDiagnostic(code=code, message=code, rule_id=entry.rule_id)
            for code in (outcome.diagnostics or (failure_reason,))
        )
        return LaunchRuleRecord(
            rule_id=entry.rule_id,
            rule_revision=entry.rule_revision,
            plan_digest=entry.plan.plan_digest if entry.plan is not None else "uncompiled",
            status=ResultStatus.ERROR,
            coverage_state=CoverageState.ERROR,
            enabled=entry.enabled,
            suppressed=entry.suppressed,
            reason=failure_reason,
            diagnostics=_bound_diagnostics(diagnostics, budgets),
        )
    operator = OperatorResult.model_validate(outcome.result)
    status = interpret_operator_result(operator)
    evidence: tuple[LaunchEvidence, ...] = ()
    reason: str | None = operator.reason
    notes: list[LaunchDiagnostic] = []
    if operator.error:
        notes.append(
            LaunchDiagnostic(
                code=operator.reason or "operator_error",
                message=str((operator.details or {}).get("message") or operator.reason or "ERROR"),
                rule_id=entry.rule_id,
            )
        )
    try:
        if operator.members:
            evidence = evidence_from_operator_members(
                operator.members,
                source_kind="operator_members",
                extractor_version=extractor_version,
                relative_paths=evidence_paths,
            )
        elif status is ResultStatus.FAIL:
            subject = entry.rule_id
            evidence = validate_launch_evidence(
                (
                    LaunchEvidence(
                        subject_id=subject,
                        source_kind="rule_subject",
                        extractor_version=extractor_version,
                    ),
                )
            )
    except RuleEvidenceError as error:
        status = ResultStatus.ERROR
        reason = error.reason_code
        notes.append(
            LaunchDiagnostic(
                code=error.reason_code,
                message=error.safe_message,
                rule_id=entry.rule_id,
            )
        )
        evidence = ()
    coverage = entry.coverage_state
    if entry.suppressed:
        coverage = CoverageState.SUPPRESSED
    elif status is ResultStatus.ERROR:
        coverage = CoverageState.ERROR
    elif status is ResultStatus.UNKNOWN:
        coverage = CoverageState.UNKNOWN
    elif status is ResultStatus.NOT_APPLICABLE:
        coverage = CoverageState.NOT_APPLICABLE
    return LaunchRuleRecord(
        rule_id=entry.rule_id,
        rule_revision=entry.rule_revision,
        plan_digest=entry.plan.plan_digest if entry.plan is not None else "uncompiled",
        status=status,
        coverage_state=coverage,
        enabled=entry.enabled,
        suppressed=entry.suppressed,
        reason=reason,
        evidence=evidence,
        diagnostics=_bound_diagnostics(tuple(notes), budgets),
        operator_reason=operator.reason,
    )


def execute_launch_plan(
    plan: LaunchExecutionPlan,
    context: OperatorContext,
    *,
    package_purpose: ExecutionPurpose,
    requested_purpose: ExecutionPurpose | None = None,
    budgets: BudgetLimits | None = None,
    isolate: bool = True,
    cancel_requested: Callable[[], bool] | None = None,
    evidence_paths: dict[str, str] | None = None,
    extractor_version: str = "1.0.0",
    eligible_files: int = 1,
    isolate_fn: Callable[..., IsolatedOutcome] | None = None,
) -> LaunchExecutionBody:
    """Run selected YAML rules. Never calls SharedRule.evaluate()."""

    requested = requested_purpose or plan.purpose
    admit_execution_purpose(package_purpose=package_purpose, requested_purpose=requested)
    bound = budgets or execution_budgets()
    _ = wall_seconds_for_workload(bound, eligible_files=eligible_files)
    limits = operator_limits_from_budgets(bound)
    operating = context.model_copy(update={"limits": limits})
    runner = isolate_fn or run_isolated_evaluation
    records: list[LaunchRuleRecord] = []
    for entry in plan.entries:
        if not entry.selected or entry.plan is None or entry.plan.condition is None:
            records.append(_record_for_unselected(entry))
            continue
        payload: dict[str, Any] = {
            "plan": entry.plan.condition.model_dump(mode="json"),
            "context": operating.model_dump(mode="json"),
            "limits": limits.model_dump(mode="json"),
        }
        deadline = _deadline_for_rule(entry.plan.condition, bound)
        if isolate:
            outcome = runner(
                payload,
                budgets=bound,
                hard_deadline_seconds=deadline,
                cancel_requested=cancel_requested,
                local_job_id=f"rule:{entry.rule_id}",
            )
        else:
            try:
                outcome = IsolatedOutcome(
                    terminal=JobTerminalState.COMPLETED,
                    result=in_process_evaluate(payload),
                )
            except Exception as error:  # noqa: BLE001
                outcome = IsolatedOutcome(
                    terminal=JobTerminalState.FAILED,
                    reason=type(error).__name__,
                )
        records.append(
            _result_from_outcome(
                entry,
                outcome,
                evidence_paths=evidence_paths or {},
                extractor_version=extractor_version,
                budgets=bound,
            )
        )
    body = LaunchExecutionBody(
        compiler_version=COMPILER_VERSION,
        purpose=requested,
        plan_digest=plan.plan_digest,
        facts_digest=_facts_digest(operating),
        records=tuple(sorted(records, key=lambda item: item.rule_id)),
        limitations=plan.limitations,
    )
    if requested is ExecutionPurpose.PREVIEW:
        if body.preview_cannot_authorize_production is not True:
            raise ValueError("preview results cannot authorize production")
    return body
