"""Typed operator call, context, limits and result (E03.2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.contracts.rules import BOUNDED_OPERATORS
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.rules.operators.errors import OperatorBudgetError, OperatorEvaluationError


class Truth(StrEnum):
    """Kleene three-valued boolean. UNKNOWN is not FALSE."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class FactStatus(StrEnum):
    COMPLETE = "complete"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class Comparator(StrEnum):
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    EQ = "eq"


class OperatorLimits(BaseModel):
    """Per-operator cost caps. Defaults match E01.1 launch ratification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_max_depth: int = 32
    graph_max_visited_nodes: int = 100_000
    graph_max_visited_edges: int = 500_000
    regex_max_steps: int = 1_000_000
    regex_timeout_milliseconds: int = 100
    max_collection_items: int = 100_000
    max_operands: int = 1_024
    max_cost_units: int = 1_000_000
    max_pattern_length: int = 256


class CostMeter:
    """Mutable evaluation cost. Domain evaluation never talks to a clock or network."""

    def __init__(self, limits: OperatorLimits) -> None:
        self.limits = limits
        self.units = 0
        self.visited_nodes = 0
        self.visited_edges = 0

    def charge(self, amount: int, *, operator: str) -> None:
        if amount < 0:
            raise OperatorEvaluationError(
                "cost charge must be nonnegative",
                reason_code="invalid_cost",
                operator=operator,
            )
        self.units += amount
        if self.units > self.limits.max_cost_units:
            raise OperatorBudgetError(
                f"operator {operator} exceeded {self.limits.max_cost_units} cost units",
                operator=operator,
                details={"units": self.units, "limit": self.limits.max_cost_units},
            )


class FactSlot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: FactStatus
    value: str | int | float | bool | None = None


class OperatorEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    edge_type: str
    unknown: bool = False

    @field_validator("source", "target", "edge_type", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="graph edge")


class OperatorGraph(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: tuple[str, ...] = ()
    edges: tuple[OperatorEdge, ...] = ()
    complete: bool = True


class OperatorCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: str
    fact: str | None = None
    value: str | int | float | bool | None = None
    values: tuple[str | int | float | bool, ...] = ()
    edge_types: tuple[str, ...] = ()
    traversal: str | None = None
    max_depth: int | None = Field(default=None, ge=1)
    dependency_view: str | None = None
    comparator: Comparator = Comparator.GT
    operands: tuple[OperatorCall, ...] = ()

    @field_validator("operator", mode="before")
    @classmethod
    def normalize_operator(cls, value: object) -> str:
        token = require_nonblank(str(value), label="operator").lower()
        if token not in BOUNDED_OPERATORS:
            raise ValueError(f"unknown operator {token}")
        return token

    @model_validator(mode="after")
    def bound_traversal_and_view(self) -> OperatorCall:
        if self.traversal is not None and self.traversal not in {"direct", "transitive"}:
            raise ValueError("traversal must be direct or transitive")
        if self.traversal == "direct" and self.max_depth not in (None, 1):
            raise ValueError("direct traversal has max_depth 1")
        if self.traversal == "transitive" and (self.max_depth is None or self.max_depth < 1):
            raise ValueError("transitive traversal requires a positive bounded max_depth")
        if self.dependency_view is not None and self.dependency_view not in {
            "declared",
            "resolved",
        }:
            raise ValueError("dependency_view must be declared or resolved")
        return self


class OperatorContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    facts: dict[str, FactSlot] = Field(default_factory=dict)
    collections: dict[str, tuple[str | int | float | bool, ...]] = Field(default_factory=dict)
    metrics: dict[str, MetricComputation] = Field(default_factory=dict)
    declared_graph: OperatorGraph | None = None
    resolved_graph: OperatorGraph | None = None
    baseline: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    candidate: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    comparable: bool = True
    limits: OperatorLimits = Field(default_factory=OperatorLimits)


class OperatorResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    truth: Truth | None = None
    metric: MetricComputation | None = None
    members: tuple[str, ...] = ()
    cutoff: bool = False
    complete: bool = True
    reason: str | None = None
    cost_units: int = 0
    error: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "truth": None if self.truth is None else self.truth.value,
            "cutoff": self.cutoff,
            "complete": self.complete,
            "error": self.error,
            "cost_units": self.cost_units,
            "members": list(self.members),
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.metric is not None:
            payload["metric_status"] = self.metric.status.value
            payload["metric_serialized"] = self.metric.serialized
            payload["numerator"] = self.metric.numerator
            payload["denominator"] = self.metric.denominator
            payload["metric_reason"] = self.metric.reason
        if self.details:
            payload["details"] = dict(self.details)
        return payload


def boolean_result(
    truth: Truth,
    *,
    meter: CostMeter,
    cutoff: bool = False,
    complete: bool = True,
    reason: str | None = None,
    members: tuple[str, ...] = (),
    details: dict[str, Any] | None = None,
) -> OperatorResult:
    return OperatorResult(
        truth=truth,
        cutoff=cutoff,
        complete=complete,
        reason=reason,
        members=members,
        cost_units=meter.units,
        details=dict(details or {}),
    )


def metric_result(
    metric: MetricComputation,
    *,
    meter: CostMeter,
    reason: str | None = None,
    members: tuple[str, ...] = (),
    cutoff: bool = False,
    complete: bool = True,
) -> OperatorResult:
    return OperatorResult(
        metric=metric,
        reason=reason or metric.reason,
        members=members,
        cutoff=cutoff,
        complete=complete,
        cost_units=meter.units,
    )


def error_result(
    error: OperatorEvaluationError,
    *,
    meter: CostMeter,
) -> OperatorResult:
    return OperatorResult(
        error=True,
        reason=error.reason_code,
        cost_units=meter.units,
        complete=False,
        details=error.to_payload(),
    )
