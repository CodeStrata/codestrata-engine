"""Bounded YAML operator evaluation (E03.2)."""

from __future__ import annotations

from codestrata.domain.rules.operators.catalog import (
    declared_operators,
    default_limits,
    family_of,
    truth_tables,
)
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError
from codestrata.domain.rules.operators.evaluate import (
    evaluate_operator,
    evaluate_plan,
    operator_call_from_plan,
)
from codestrata.domain.rules.operators.models import (
    Comparator,
    CostMeter,
    FactSlot,
    FactStatus,
    OperatorCall,
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorLimits,
    OperatorResult,
    Truth,
)
from codestrata.domain.rules.operators.truth import AND_TABLE, NOT_TABLE, OR_TABLE

__all__ = [
    "AND_TABLE",
    "NOT_TABLE",
    "OR_TABLE",
    "Comparator",
    "CostMeter",
    "FactSlot",
    "FactStatus",
    "OperatorBudgetError",
    "OperatorCall",
    "OperatorContext",
    "OperatorEdge",
    "OperatorEvaluationError",
    "OperatorGraph",
    "OperatorLimits",
    "OperatorResult",
    "Truth",
    "declared_operators",
    "default_limits",
    "evaluate_operator",
    "evaluate_plan",
    "family_of",
    "operator_call_from_plan",
    "truth_tables",
]
