"""Numeric and set operators. Empty/zero denominators and percentile match E01.1."""

from __future__ import annotations

import math
from decimal import Decimal

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.formulas import nearest_rank_percentile, ratio
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError
from codestrata.domain.rules.operators.models import CostMeter, OperatorCall, OperatorContext

Scalar = str | int | float | bool


def collection_for(call: OperatorCall, context: OperatorContext) -> tuple[Scalar, ...]:
    if call.values:
        return call.values
    if call.fact and call.fact in context.collections:
        return context.collections[call.fact]
    return ()


def require_collection(
    call: OperatorCall,
    context: OperatorContext,
    *,
    meter: CostMeter,
) -> tuple[Scalar, ...]:
    items = collection_for(call, context)
    limit = meter.limits.max_collection_items
    if len(items) > limit:
        raise OperatorBudgetError(
            f"collection of {len(items)} exceeds {limit}",
            operator=call.operator,
            details={"size": len(items), "limit": limit},
        )
    meter.charge(max(len(items), 1), operator=call.operator)
    return items


def as_number(value: object, *, operator: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise OperatorEvaluationError(
            "numeric operators require declared numeric types",
            reason_code="invalid_type",
            operator=operator,
        )
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OperatorEvaluationError(
                "NaN/infinity are rejected",
                reason_code="non_finite",
                operator=operator,
            )
        return Decimal(str(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise OperatorEvaluationError(
                "NaN/infinity are rejected",
                reason_code="non_finite",
                operator=operator,
            )
        return value
    raise OperatorEvaluationError(
        "numeric operators require declared numeric types",
        reason_code="invalid_type",
        operator=operator,
    )


def as_nonnegative_int(value: object, *, operator: str) -> int:
    number = as_number(value, operator=operator)
    if number != number.to_integral_value() or number < 0:
        raise OperatorEvaluationError(
            "counts must be nonnegative integers",
            reason_code="invalid_type",
            operator=operator,
        )
    return int(number)


def op_count(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> MetricComputation:
    items = require_collection(call, context, meter=meter)
    return MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(len(items)),
        serialized=str(len(items)),
        numerator=len(items),
        denominator=len(items),
    )


def op_distinct(
    call: OperatorCall, context: OperatorContext, meter: CostMeter
) -> MetricComputation:
    items = require_collection(call, context, meter=meter)
    unique = dict.fromkeys(stable_key(item) for item in items)
    size = len(unique)
    return MetricComputation(
        status=MetricStatus.VALUE,
        value=Decimal(size),
        serialized=str(size),
        numerator=size,
        denominator=len(items),
        extra={"members": list(unique)},
    )


def op_sum(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> MetricComputation:
    items = require_collection(call, context, meter=meter)
    if not items:
        return MetricComputation(status=MetricStatus.NOT_APPLICABLE, reason="empty_input")
    total = Decimal(0)
    for item in items:
        total += as_number(item, operator=call.operator)
    return MetricComputation(status=MetricStatus.VALUE, value=total, serialized=format(total, "f"))


def op_min(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> MetricComputation:
    return _extrema(call, context, meter, sign=-1)


def op_max(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> MetricComputation:
    return _extrema(call, context, meter, sign=1)


def _extrema(
    call: OperatorCall,
    context: OperatorContext,
    meter: CostMeter,
    *,
    sign: int,
) -> MetricComputation:
    items = require_collection(call, context, meter=meter)
    if not items:
        return MetricComputation(status=MetricStatus.NOT_APPLICABLE, reason="empty_input")
    best = as_number(items[0], operator=call.operator)
    for item in items[1:]:
        current = as_number(item, operator=call.operator)
        if sign > 0 and current > best:
            best = current
        if sign < 0 and current < best:
            best = current
    return MetricComputation(status=MetricStatus.VALUE, value=best, serialized=format(best, "f"))


def op_ratio(call: OperatorCall, context: OperatorContext, meter: CostMeter) -> MetricComputation:
    meter.charge(1, operator=call.operator)
    if len(call.values) == 2:
        numerator = as_nonnegative_int(call.values[0], operator=call.operator)
        denominator = as_nonnegative_int(call.values[1], operator=call.operator)
        return ratio(numerator, denominator)
    if call.fact == "unknown_denominator":
        return MetricComputation(
            status=MetricStatus.UNKNOWN,
            reason="unknown_denominator",
        )
    raise OperatorEvaluationError(
        "ratio requires numerator and denominator values",
        reason_code="invalid_operands",
        operator=call.operator,
    )


def op_percentile(
    call: OperatorCall, context: OperatorContext, meter: CostMeter
) -> MetricComputation:
    items = require_collection(call, context, meter=meter)
    if call.value is None:
        raise OperatorEvaluationError(
            "percentile requires p in [0, 1]",
            reason_code="invalid_operands",
            operator=call.operator,
        )
    p = float(as_number(call.value, operator=call.operator))
    numbers: list[int] = []
    for item in items:
        number = as_number(item, operator=call.operator)
        if number != number.to_integral_value():
            raise OperatorEvaluationError(
                "percentile v1 operates on integers",
                reason_code="invalid_type",
                operator=call.operator,
            )
        numbers.append(int(number))
    return nearest_rank_percentile(numbers, p)


def stable_key(value: Scalar) -> str:
    if isinstance(value, bool):
        return f"b:{value}"
    if isinstance(value, int):
        return f"i:{value}"
    if isinstance(value, float):
        return f"f:{value}"
    return f"s:{value}"
