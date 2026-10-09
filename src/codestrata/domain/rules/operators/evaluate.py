"""Dispatch the declared bounded operator set (Engine §5 / E03.2)."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from decimal import Decimal

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.formulas import serialize_ratio
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.contracts.rules import BOUNDED_OPERATORS
from codestrata.domain.rules.compiler_models import ConditionPlan
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError
from codestrata.domain.rules.operators.graph import (
    op_crosses_boundary,
    op_cycle,
    op_degree,
    op_exists_path,
    op_neighbors,
    op_reachable,
)
from codestrata.domain.rules.operators.models import (
    Comparator,
    CostMeter,
    FactSlot,
    FactStatus,
    OperatorCall,
    OperatorContext,
    OperatorResult,
    Truth,
    boolean_result,
    error_result,
    metric_result,
)
from codestrata.domain.rules.operators.numeric import (
    as_number,
    op_count,
    op_distinct,
    op_max,
    op_min,
    op_percentile,
    op_ratio,
    op_sum,
)
from codestrata.domain.rules.operators.truth import fold_and, fold_or, kleene_not

SELECTION = frozenset({"all", "any", "not", "equals", "in", "matches", "exists"})
NUMERIC = frozenset({"count", "sum", "min", "max", "ratio", "distinct", "percentile"})
GRAPH = frozenset({"neighbors", "degree", "exists_path", "reachable", "cycle", "crosses_boundary"})
CHANGE = frozenset({"changed", "introduced", "removed", "increased_by", "decreased_by", "compare"})
COMPOSITION = frozenset({"threshold", "and", "or", "metric_ref"})


def operator_call_from_plan(plan: ConditionPlan) -> OperatorCall:
    inline_values = tuple(
        operand.value
        for operand in plan.operands
        if operand.value is not None and not operand.operands
    )
    return OperatorCall(
        operator=plan.operator,
        fact=plan.fact,
        value=plan.value,
        values=inline_values,
        edge_types=tuple(plan.edge_types),
        traversal=plan.traversal,
        max_depth=plan.max_depth,
        dependency_view=plan.dependency_view,
        operands=tuple(operator_call_from_plan(item) for item in plan.operands),
    )


def evaluate_plan(plan: ConditionPlan, context: OperatorContext) -> OperatorResult:
    return evaluate_operator(operator_call_from_plan(plan), context)


def evaluate_operator(call: OperatorCall, context: OperatorContext) -> OperatorResult:
    meter = CostMeter(context.limits)
    try:
        return _evaluate(call, context, meter)
    except OperatorBudgetError as error:
        return error_result(error, meter=meter)
    except OperatorEvaluationError as error:
        return error_result(error, meter=meter)
    except ValueError as error:
        return error_result(
            OperatorEvaluationError(
                str(error),
                reason_code="invalid_operands",
                operator=call.operator,
            ),
            meter=meter,
        )


def _evaluate(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    if len(call.operands) > meter.limits.max_operands:
        raise OperatorBudgetError(
            f"operand count {len(call.operands)} exceeds {meter.limits.max_operands}",
            operator=call.operator,
            details={"operands": len(call.operands), "limit": meter.limits.max_operands},
        )
    operator = call.operator
    if operator in {"all", "and"}:
        return _combine(call, context, meter, fold_and, Truth.TRUE)
    if operator in {"any", "or"}:
        return _combine(call, context, meter, fold_or, Truth.FALSE)
    if operator == "not":
        return _op_not(call, context, meter)
    if operator == "equals":
        return _op_equals(call, context, meter)
    if operator == "in":
        return _op_in(call, context, meter)
    if operator == "matches":
        return _op_matches(call, context, meter)
    if operator == "exists":
        return _op_exists(call, context, meter)
    if operator == "count":
        return metric_result(op_count(call, context, meter), meter=meter)
    if operator == "sum":
        return metric_result(op_sum(call, context, meter), meter=meter)
    if operator == "min":
        return metric_result(op_min(call, context, meter), meter=meter)
    if operator == "max":
        return metric_result(op_max(call, context, meter), meter=meter)
    if operator == "ratio":
        return metric_result(op_ratio(call, context, meter), meter=meter)
    if operator == "distinct":
        return metric_result(op_distinct(call, context, meter), meter=meter)
    if operator == "percentile":
        return metric_result(op_percentile(call, context, meter), meter=meter)
    if operator == "neighbors":
        return op_neighbors(call, context, meter)
    if operator == "degree":
        return op_degree(call, context, meter)
    if operator == "exists_path":
        return op_exists_path(call, context, meter)
    if operator == "reachable":
        return op_reachable(call, context, meter)
    if operator == "cycle":
        return op_cycle(call, context, meter)
    if operator == "crosses_boundary":
        return op_crosses_boundary(call, context, meter)
    if operator == "changed":
        return _op_changed(call, context, meter)
    if operator == "introduced":
        return _op_introduced(call, context, meter)
    if operator == "removed":
        return _op_removed(call, context, meter)
    if operator == "increased_by":
        return _op_delta(call, context, meter, direction=1)
    if operator == "decreased_by":
        return _op_delta(call, context, meter, direction=-1)
    if operator == "compare":
        return _op_compare(call, context, meter)
    if operator == "threshold":
        return _op_threshold(call, context, meter)
    if operator == "metric_ref":
        return _op_metric_ref(call, context, meter)
    raise OperatorEvaluationError(
        f"unsupported operator {operator}",
        reason_code="unsupported_operator",
        operator=operator,
        details={"supported": sorted(BOUNDED_OPERATORS)},
    )


def _combine(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
    folder: Callable[[tuple[Truth, ...]], Truth],
    empty: Truth,
) -> OperatorResult:
    meter.charge(max(len(call.operands), 1), operator=call.operator)
    if not call.operands:
        return boolean_result(empty, meter=meter)
    truths: list[Truth] = []
    cutoff = False
    complete = True
    for operand in call.operands:
        result = _evaluate(operand, context, meter)
        if result.error:
            return result
        if result.truth is None:
            raise OperatorEvaluationError(
                "boolean combinators require boolean operands",
                reason_code="invalid_operands",
                operator=call.operator,
            )
        truths.append(result.truth)
        cutoff = cutoff or result.cutoff
        complete = complete and result.complete
    folded = folder(tuple(truths))
    return boolean_result(folded, meter=meter, cutoff=cutoff, complete=complete)


def _op_not(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if len(call.operands) != 1:
        raise OperatorEvaluationError(
            "not requires exactly one operand",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    inner = _evaluate(call.operands[0], context, meter)
    if inner.error:
        return inner
    if inner.truth is None:
        raise OperatorEvaluationError(
            "not requires a boolean operand",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    return boolean_result(
        kleene_not(inner.truth),
        meter=meter,
        cutoff=inner.cutoff,
        complete=inner.complete,
    )


def _op_equals(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    slot = _fact_slot(call, context)
    if slot is None or slot.status is not FactStatus.COMPLETE:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_fact")
    return boolean_result(
        Truth.TRUE if typed_equal(slot.value, call.value) else Truth.FALSE,
        meter=meter,
    )


def _op_in(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    haystack = call.values
    if not haystack and call.fact and call.fact in context.collections:
        haystack = context.collections[call.fact]
    if len(haystack) > meter.limits.max_collection_items:
        raise OperatorBudgetError(
            "membership set exceeds collection budget",
            operator=call.operator,
            details={"size": len(haystack), "limit": meter.limits.max_collection_items},
        )
    meter.charge(max(len(haystack), 1), operator=call.operator)
    slot = _fact_slot(call, context)
    needle: str | int | float | bool | None
    if slot is None:
        needle = call.value
        status = FactStatus.COMPLETE if needle is not None else FactStatus.MISSING
    else:
        needle = slot.value
        status = slot.status
    if status is not FactStatus.COMPLETE:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_fact")
    if any(typed_equal(needle, item) for item in haystack):
        return boolean_result(Truth.TRUE, meter=meter)
    return boolean_result(Truth.FALSE, meter=meter)


def _op_matches(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    pattern = call.value
    if not isinstance(pattern, str):
        raise OperatorEvaluationError(
            "matches requires a string pattern",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    if len(pattern) > meter.limits.max_pattern_length:
        raise OperatorBudgetError(
            "regex pattern exceeds max_pattern_length",
            operator=call.operator,
            details={"length": len(pattern), "limit": meter.limits.max_pattern_length},
        )
    slot = _fact_slot(call, context)
    if slot is None or slot.status is not FactStatus.COMPLETE or not isinstance(slot.value, str):
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_fact")
    subject = slot.value
    estimate = (len(pattern) + 1) * (len(subject) + 1)
    if estimate > meter.limits.regex_max_steps:
        raise OperatorBudgetError(
            "regex step budget exceeded",
            operator=call.operator,
            details={"estimate": estimate, "limit": meter.limits.regex_max_steps},
        )
    meter.charge(estimate, operator=call.operator)
    try:
        compiled = re.compile(pattern)
    except re.error as error:
        raise OperatorEvaluationError(
            "invalid regular expression",
            reason_code="invalid_pattern",
            operator=call.operator,
        ) from error
    matched = compiled.search(subject) is not None
    return boolean_result(Truth.TRUE if matched else Truth.FALSE, meter=meter)


def _op_exists(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if call.fact and call.fact in context.collections:
        items = context.collections[call.fact]
        if items:
            return boolean_result(Truth.TRUE, meter=meter)
        return boolean_result(Truth.FALSE, meter=meter)
    slot = _fact_slot(call, context)
    if slot is None or slot.status in {FactStatus.UNKNOWN, FactStatus.UNSUPPORTED}:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="unknown_fact")
    if slot.status is FactStatus.MISSING:
        return boolean_result(Truth.FALSE, meter=meter)
    if slot.value is None:
        return boolean_result(Truth.FALSE, meter=meter)
    return boolean_result(Truth.TRUE, meter=meter)


def _op_changed(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if not context.comparable:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="incomparable")
    key = _subject(call)
    if key not in context.baseline or key not in context.candidate:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_side")
    changed = not typed_equal(context.baseline[key], context.candidate[key])
    return boolean_result(Truth.TRUE if changed else Truth.FALSE, meter=meter)


def _op_introduced(
    call: OperatorCall, context: OperatorContext, meter: CostMeter
) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if not context.comparable:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="incomparable")
    key = _subject(call)
    present_candidate = key in context.candidate
    present_baseline = key in context.baseline
    if present_candidate and not present_baseline:
        return boolean_result(Truth.TRUE, meter=meter)
    if not present_candidate and not present_baseline:
        return boolean_result(Truth.FALSE, meter=meter)
    if not present_candidate:
        return boolean_result(Truth.FALSE, meter=meter)
    return boolean_result(Truth.FALSE, meter=meter)


def _op_removed(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if not context.comparable:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="incomparable")
    key = _subject(call)
    if key in context.baseline and key not in context.candidate:
        return boolean_result(Truth.TRUE, meter=meter)
    if key not in context.baseline:
        return boolean_result(Truth.FALSE, meter=meter)
    return boolean_result(Truth.FALSE, meter=meter)


def _op_delta(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
    *,
    direction: int,
) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if not context.comparable:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="incomparable")
    key = _subject(call)
    if key not in context.baseline or key not in context.candidate:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_side")
    before = as_number(context.baseline[key], operator=call.operator)
    after = as_number(context.candidate[key], operator=call.operator)
    threshold = Decimal(0) if call.value is None else as_number(call.value, operator=call.operator)
    delta = (after - before) if direction > 0 else (before - after)
    return boolean_result(Truth.TRUE if delta > threshold else Truth.FALSE, meter=meter)


def _op_compare(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    if not context.comparable:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="incomparable")
    key = _subject(call)
    if key not in context.baseline or key not in context.candidate:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason="missing_side")
    left = context.baseline[key]
    right = context.candidate[key]
    if typed_equal(left, right):
        return boolean_result(Truth.FALSE, meter=meter, reason="unchanged")
    try:
        delta = as_number(right, operator=call.operator) - as_number(left, operator=call.operator)
        if delta == delta.to_integral_value():
            serialized = str(int(delta))
        else:
            serialized = serialize_ratio(delta)
        metric = MetricComputation(
            status=MetricStatus.VALUE,
            value=delta,
            serialized=serialized,
        )
        return OperatorResult(
            truth=Truth.TRUE,
            metric=metric,
            cost_units=meter.units,
        )
    except OperatorEvaluationError:
        return boolean_result(Truth.TRUE, meter=meter)


def _op_threshold(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    bound = call.value
    if bound is None:
        raise OperatorEvaluationError(
            "threshold requires a bound in value",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    if call.operands:
        inner = _evaluate(call.operands[0], context, meter)
        if inner.error:
            return inner
        if inner.metric is None:
            raise OperatorEvaluationError(
                "threshold requires a numeric operand or metric_ref",
                reason_code="invalid_operands",
                operator=call.operator,
            )
        metric = inner.metric
    else:
        metric = _lookup_metric(call, context)
    if metric.status is MetricStatus.UNKNOWN:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason=metric.reason)
    if metric.status is MetricStatus.NOT_APPLICABLE:
        return OperatorResult(
            truth=None,
            metric=metric,
            reason=metric.reason,
            complete=True,
            cost_units=meter.units,
        )
    if metric.status is MetricStatus.ERROR or metric.value is None:
        return boolean_result(Truth.UNKNOWN, meter=meter, complete=False, reason=metric.reason)
    observed = metric.value
    limit = as_number(bound, operator=call.operator)
    passed = _compare(observed, limit, call.comparator)
    return boolean_result(Truth.TRUE if passed else Truth.FALSE, meter=meter)


def _op_metric_ref(
    call: OperatorCall, context: OperatorContext, meter: CostMeter
) -> OperatorResult:
    meter.charge(1, operator=call.operator)
    metric = _lookup_metric(call, context)
    if metric.status is MetricStatus.UNKNOWN:
        return metric_result(metric, meter=meter, complete=False)
    if metric.status is MetricStatus.NOT_APPLICABLE:
        return metric_result(metric, meter=meter)
    return metric_result(metric, meter=meter)


def _lookup_metric(call: OperatorCall, context: OperatorContext) -> MetricComputation:
    name = call.fact
    if not name:
        raise OperatorEvaluationError(
            "metric_ref requires a metric name in fact",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    if name not in context.metrics:
        return MetricComputation(status=MetricStatus.UNKNOWN, reason="missing_metric")
    return context.metrics[name]


def _compare(observed: Decimal, bound: Decimal, comparator: Comparator) -> bool:
    if comparator is Comparator.GT:
        return observed > bound
    if comparator is Comparator.GE:
        return observed >= bound
    if comparator is Comparator.LT:
        return observed < bound
    if comparator is Comparator.LE:
        return observed <= bound
    return observed == bound


def _fact_slot(call: OperatorCall, context: OperatorContext) -> FactSlot | None:
    if call.fact is None:
        return None
    return context.facts.get(call.fact)


def _subject(call: OperatorCall) -> str:
    if call.fact:
        return call.fact
    raise OperatorEvaluationError(
        "change operators require a subject id in fact",
        reason_code="invalid_operands",
        operator=call.operator,
    )


def typed_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, float) and not math.isfinite(left):
        return False
    if isinstance(right, float) and not math.isfinite(right):
        return False
    return left == right
