"""Evaluate compiled condition plans with the bounded operator set."""

from __future__ import annotations

from codestrata.application.rules.operators.limits import operator_limits_from_ratification
from codestrata.domain.rules.compiler_models import ConditionPlan
from codestrata.domain.rules.operators.evaluate import (
    evaluate_operator,
    evaluate_plan,
)
from codestrata.domain.rules.operators.models import (
    OperatorCall,
    OperatorContext,
    OperatorLimits,
    OperatorResult,
)


def evaluate_condition(
    plan: ConditionPlan,
    context: OperatorContext | None = None,
    *,
    limits: OperatorLimits | None = None,
) -> OperatorResult:
    """Evaluate a compiled E03.1 condition against supplied evidence.

    Planner/executor budgets and emission projections remain E03.3.
    """

    bound_limits = limits or operator_limits_from_ratification()
    operating = context or OperatorContext(limits=bound_limits)
    if context is None or limits is not None:
        operating = operating.model_copy(update={"limits": bound_limits})
    return evaluate_plan(plan, operating)


def evaluate_call(
    call: OperatorCall,
    context: OperatorContext | None = None,
    *,
    limits: OperatorLimits | None = None,
) -> OperatorResult:
    bound_limits = limits or operator_limits_from_ratification()
    operating = context or OperatorContext(limits=bound_limits)
    if context is None or limits is not None:
        operating = operating.model_copy(update={"limits": bound_limits})
    return evaluate_operator(call, operating)
