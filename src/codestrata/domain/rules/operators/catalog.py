"""Operator catalog: families, Kleene tables and cost limits (E03.2)."""

from __future__ import annotations

from codestrata.domain.contracts.rules import BOUNDED_OPERATORS
from codestrata.domain.rules.operators.evaluate import (
    CHANGE,
    COMPOSITION,
    GRAPH,
    NUMERIC,
    SELECTION,
)
from codestrata.domain.rules.operators.models import OperatorLimits, Truth
from codestrata.domain.rules.operators.truth import AND_TABLE, NOT_TABLE, OR_TABLE

OPERATOR_FAMILIES = {
    "selection": SELECTION,
    "numeric": NUMERIC,
    "graph": GRAPH,
    "change": CHANGE,
    "threshold": COMPOSITION,
}


def declared_operators() -> frozenset[str]:
    return BOUNDED_OPERATORS


def family_of(operator: str) -> str:
    for name, members in OPERATOR_FAMILIES.items():
        if operator in members:
            return name
    raise KeyError(operator)


def truth_tables() -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {}
    for (left, right), result in AND_TABLE.items():
        tables[f"and:{left.value},{right.value}"] = {"result": result.value}
    for (left, right), result in OR_TABLE.items():
        tables[f"or:{left.value},{right.value}"] = {"result": result.value}
    for value, result in NOT_TABLE.items():
        tables[f"not:{value.value}"] = {"result": result.value}
    tables["unknown_propagates"] = {"result": Truth.UNKNOWN.value}
    return tables


def default_limits() -> OperatorLimits:
    return OperatorLimits()
