"""Shared Rule Platform executor."""

from __future__ import annotations

import time
from collections import Counter

from codestrata.application.rules.errors import RuleExecutionError
from codestrata.application.rules.models import (
    RuleExecutionPlan,
    RulePlatformExecutionResult,
    RuleRuleResultRecord,
    RuleTelemetry,
)
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.suppression_service import RuleSuppressionService
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleApplicabilityStatus,
    RuleResultStatus,
    RuleSkipReason,
)
from codestrata.domain.rules.errors import RuleDomainError, RuleResultValidationError
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult
from codestrata.domain.rules.validation import validate_evaluation_result


class RuleExecutor:
    def __init__(self, *, suppression_service: RuleSuppressionService | None = None) -> None:
        self._suppressions = suppression_service or RuleSuppressionService()

    def execute(
        self,
        registry: RuleRegistry,
        plan: RuleExecutionPlan,
        context: RuleExecutionContext,
    ) -> RulePlatformExecutionResult:
        started = time.perf_counter()
        records: list[RuleRuleResultRecord] = []
        matches: list[RuleMatch] = []
        suppressed_matches: list[RuleMatch] = []
        applied_suppressions = []
        category_counts: Counter[str] = Counter()
        matched_rules = 0
        not_applicable = 0
        suppressed_rules = 0
        failed_rules = 0
        validation_failures = 0

        for rule_id in plan.execution_order:
            rule = registry.get(rule_id)
            meta = rule.metadata
            category_counts[meta.category.value] += 1
            try:
                applicability = rule.evaluate_applicability(context)
                if applicability.status is RuleApplicabilityStatus.NOT_APPLICABLE:
                    not_applicable += 1
                    evaluation = SharedRuleEvaluationResult.not_applicable(
                        reason=applicability.reason_code or RuleSkipReason.OTHER,
                        message=applicability.message,
                    )
                    records.append(
                        RuleRuleResultRecord(
                            rule_id=rule_id,
                            status=RuleResultStatus.NOT_APPLICABLE,
                            evaluation=evaluation,
                            category=meta.category,
                        )
                    )
                    continue

                raw = rule.evaluate(context)
                evaluation = validate_evaluation_result(
                    raw, policy=context.policy, rule_id=rule_id
                )
            except RuleResultValidationError as error:
                validation_failures += 1
                failed_rules += 1
                evaluation = SharedRuleEvaluationResult.failed(
                    error.safe_message, rule_id=rule_id
                )
                if context.policy.fail_on_rule_error:
                    raise RuleExecutionError(
                        error.safe_message,
                        reason_code=error.reason_code,
                        rule_id=rule_id,
                    ) from error
                records.append(
                    RuleRuleResultRecord(
                        rule_id=rule_id,
                        status=RuleResultStatus.FAILED,
                        evaluation=evaluation,
                        category=meta.category,
                    )
                )
                continue
            except RuleDomainError as error:
                failed_rules += 1
                evaluation = SharedRuleEvaluationResult.failed(
                    error.safe_message, rule_id=rule_id
                )
                if context.policy.fail_on_rule_error:
                    raise RuleExecutionError(
                        error.safe_message,
                        reason_code=error.reason_code,
                        rule_id=rule_id,
                    ) from error
                records.append(
                    RuleRuleResultRecord(
                        rule_id=rule_id,
                        status=RuleResultStatus.FAILED,
                        evaluation=evaluation,
                        category=meta.category,
                    )
                )
                continue
            except Exception as error:  # noqa: BLE001 — isolate unexpected rule failures
                failed_rules += 1
                evaluation = SharedRuleEvaluationResult.failed(
                    f"Unexpected rule failure: {type(error).__name__}",
                    rule_id=rule_id,
                )
                if context.policy.fail_on_rule_error:
                    raise RuleExecutionError(
                        evaluation.failure_message or "rule failed",
                        reason_code="unexpected_rule_failure",
                        rule_id=rule_id,
                    ) from error
                records.append(
                    RuleRuleResultRecord(
                        rule_id=rule_id,
                        status=RuleResultStatus.FAILED,
                        evaluation=evaluation,
                        category=meta.category,
                    )
                )
                continue

            if evaluation.status is RuleResultStatus.MATCHED:
                kept: list[RuleMatch] = []
                rule_suppressed = False
                for match in evaluation.matches:
                    decision = self._suppressions.decide(
                        match,
                        repository_id=context.repository.repository_id,
                    )
                    if decision.suppressed and decision.suppression is not None:
                        rule_suppressed = True
                        suppressed_matches.append(match)
                        applied_suppressions.append(decision.suppression)
                    else:
                        kept.append(match)
                if kept:
                    matched_rules += 1
                    matches.extend(kept)
                    status = RuleResultStatus.MATCHED
                    evaluation = SharedRuleEvaluationResult.matched(tuple(kept))
                elif rule_suppressed:
                    suppressed_rules += 1
                    status = RuleResultStatus.SUPPRESSED
                    evaluation = SharedRuleEvaluationResult(
                        status=RuleResultStatus.SUPPRESSED,
                        matches=(),
                        suppression=applied_suppressions[-1],
                        diagnostics=evaluation.diagnostics,
                    )
                else:
                    status = RuleResultStatus.NOT_MATCHED
                    evaluation = SharedRuleEvaluationResult.not_matched()
            else:
                status = evaluation.status
                if status is RuleResultStatus.NOT_APPLICABLE:
                    not_applicable += 1
                elif status is RuleResultStatus.FAILED:
                    failed_rules += 1

            records.append(
                RuleRuleResultRecord(
                    rule_id=rule_id,
                    status=status,
                    evaluation=evaluation,
                    category=meta.category,
                )
            )

            if len(matches) > context.policy.max_total_matches:
                raise RuleExecutionError(
                    "Exceeded max_total_matches",
                    reason_code="max_total_matches",
                )

        duration_ms = int((time.perf_counter() - started) * 1000)
        ordered_matches = tuple(
            sorted(matches, key=lambda item: (str(item.rule_id), item.title, item.summary))
        )
        telemetry = RuleTelemetry(
            registered_rules=registry.size,
            planned_rules=len(plan.execution_order),
            executed_rules=len(plan.execution_order),
            matched_rules=matched_rules,
            matches_produced=len(ordered_matches),
            not_applicable_rules=not_applicable,
            suppressed_rules=suppressed_rules,
            failed_rules=failed_rules,
            duration_ms=duration_ms,
            category_counts=dict(sorted(category_counts.items())),
            actual_reuse_count=0,
            fallback_count=1 if plan.full_execution_fallback_reason else 0,
            validation_failures=validation_failures,
        )
        return RulePlatformExecutionResult(
            plan=plan,
            records=tuple(records),
            matches=ordered_matches,
            suppressed_matches=tuple(suppressed_matches),
            suppressions=tuple(applied_suppressions),
            telemetry=telemetry,
        )
