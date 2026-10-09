"""E03.2 bounded operator tests. Expected values are independent of the evaluator."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from codestrata.application.rules.compiler import compile_rule_yaml
from codestrata.application.rules.operators import (
    evaluate_call,
    evaluate_condition,
    operator_limits_from_ratification,
)
from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.contracts.rules import BOUNDED_OPERATORS, unsigned_rule_payload
from codestrata.domain.rules.compiler_models import condition_plan_from
from codestrata.domain.rules.operators.catalog import (
    declared_operators,
    default_limits,
    family_of,
    truth_tables,
)
from codestrata.domain.rules.operators.evaluate import evaluate_operator, typed_equal
from codestrata.domain.rules.operators.models import (
    Comparator,
    FactSlot,
    FactStatus,
    OperatorCall,
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorLimits,
    Truth,
)
from codestrata.domain.rules.operators.truth import AND_TABLE, NOT_TABLE, OR_TABLE

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e03.2"
CASES = json.loads((FIXTURE_DIR / "expected-outcomes.json").read_text(encoding="utf-8"))["cases"]


def _graph(payload: object) -> OperatorGraph | None:
    if not isinstance(payload, dict):
        return None
    raw_edges = payload.get("edges") or []
    edges = tuple(
        OperatorEdge(
            source=str(item["source"]),
            target=str(item["target"]),
            edge_type=str(item.get("edge_type", "imports")),
            unknown=bool(item.get("unknown", False)),
        )
        for item in raw_edges
        if isinstance(item, dict)
    )
    raw_nodes = payload.get("nodes") or ()
    nodes = tuple(str(item) for item in raw_nodes)
    return OperatorGraph(nodes=nodes, edges=edges, complete=bool(payload.get("complete", True)))


def _metric(payload: dict[str, object]) -> MetricComputation:
    raw_value = payload.get("value")
    numerator = payload.get("numerator")
    denominator = payload.get("denominator")
    return MetricComputation(
        status=MetricStatus(str(payload["status"])),
        value=None if raw_value is None else Decimal(str(raw_value)),
        serialized=None if payload.get("serialized") is None else str(payload["serialized"]),
        numerator=numerator if isinstance(numerator, int) else None,
        denominator=denominator if isinstance(denominator, int) else None,
        reason=None if payload.get("reason") is None else str(payload["reason"]),
    )


def _context(payload: object, limits: OperatorLimits) -> OperatorContext:
    data = payload if isinstance(payload, dict) else {}
    raw_facts = data.get("facts") or {}
    facts = {
        str(key): FactSlot(status=FactStatus(str(item["status"])), value=item.get("value"))
        for key, item in raw_facts.items()
        if isinstance(item, dict)
    }
    raw_collections = data.get("collections") or {}
    collections = {
        str(key): tuple(value) for key, value in raw_collections.items() if isinstance(value, list)
    }
    raw_metrics = data.get("metrics") or {}
    metrics = {
        str(key): _metric(value) for key, value in raw_metrics.items() if isinstance(value, dict)
    }
    raw_baseline = data.get("baseline") or {}
    raw_candidate = data.get("candidate") or {}
    return OperatorContext(
        facts=facts,
        collections=collections,
        metrics=metrics,
        declared_graph=_graph(data.get("declared_graph")),
        resolved_graph=_graph(data.get("resolved_graph")),
        baseline=dict(raw_baseline) if isinstance(raw_baseline, dict) else {},
        candidate=dict(raw_candidate) if isinstance(raw_candidate, dict) else {},
        comparable=bool(data.get("comparable", True)),
        limits=limits,
    )


def _call(payload: object) -> OperatorCall:
    data = payload if isinstance(payload, dict) else {}
    raw_operands = data.get("operands") or ()
    operands = tuple(_call(item) for item in raw_operands)
    raw_cmp = data.get("comparator")
    raw_values = data.get("values") or ()
    raw_edges = data.get("edge_types") or ()
    raw_depth = data.get("max_depth")
    return OperatorCall(
        operator=str(data["operator"]),
        fact=None if data.get("fact") is None else str(data["fact"]),
        value=data.get("value"),
        values=tuple(raw_values),
        edge_types=tuple(str(item) for item in raw_edges),
        traversal=None if data.get("traversal") is None else str(data["traversal"]),
        max_depth=raw_depth if isinstance(raw_depth, int) else None,
        dependency_view=(
            None if data.get("dependency_view") is None else str(data["dependency_view"])
        ),
        comparator=Comparator(str(raw_cmp)) if raw_cmp else Comparator.GT,
        operands=operands,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda item: str(item["id"]))
def test_operator_fixture_case(case: dict[str, object]) -> None:
    limits = OperatorLimits.model_validate(case.get("limits") or {})
    result = evaluate_call(
        _call(case["call"]),
        _context(case.get("context") or {}, limits),
        limits=limits,
    )
    expected = case["expected"]
    assert isinstance(expected, dict)
    if "error" in expected:
        assert result.error is bool(expected["error"])
    if expected.get("error"):
        assert result.reason == expected.get("reason", "budget_exceeded")
        return
    if "truth" in expected:
        truth = expected["truth"]
        if truth is None:
            assert result.truth is None
        else:
            assert result.truth == Truth(str(truth))
    if "metric_status" in expected:
        assert result.metric is not None
        assert result.metric.status == MetricStatus(str(expected["metric_status"]))
    if "metric_serialized" in expected:
        assert result.metric is not None
        assert result.metric.serialized == expected["metric_serialized"]
    if "members" in expected:
        assert list(result.members) == list(expected["members"])  # type: ignore[arg-type]
    if "cutoff" in expected:
        assert result.cutoff is bool(expected["cutoff"])
    if "complete" in expected:
        assert result.complete is bool(expected["complete"])
    if "reason" in expected and not expected.get("error"):
        assert result.reason == expected["reason"]


def test_every_bounded_operator_has_positive_negative_budget() -> None:
    kinds: dict[str, set[str]] = {name: set() for name in sorted(BOUNDED_OPERATORS)}
    for case in CASES:
        kinds[str(case["operator"])].add(str(case["kind"]))
    missing = {
        operator: sorted({"positive", "negative", "budget"} - present)
        for operator, present in kinds.items()
        if {"positive", "negative", "budget"} - present
    }
    assert missing == {}
    assert set(declared_operators()) == set(BOUNDED_OPERATORS)


def test_kleene_truth_tables_cover_unknown_propagation() -> None:
    assert AND_TABLE[(Truth.TRUE, Truth.UNKNOWN)] is Truth.UNKNOWN
    assert AND_TABLE[(Truth.FALSE, Truth.UNKNOWN)] is Truth.FALSE
    assert OR_TABLE[(Truth.FALSE, Truth.UNKNOWN)] is Truth.UNKNOWN
    assert OR_TABLE[(Truth.TRUE, Truth.UNKNOWN)] is Truth.TRUE
    assert NOT_TABLE[Truth.UNKNOWN] is Truth.UNKNOWN
    tables = truth_tables()
    assert tables["and:true,unknown"]["result"] == "unknown"
    assert tables["not:unknown"]["result"] == "unknown"


def test_direct_traversal_is_depth_one_cutoff_never_proves_absence() -> None:
    graph = OperatorGraph(
        nodes=("a", "b", "c"),
        edges=(
            OperatorEdge(source="a", target="b", edge_type="imports"),
            OperatorEdge(source="b", target="c", edge_type="imports"),
        ),
    )
    result = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="c",
            edge_types=("imports",),
            traversal="direct",
            max_depth=1,
            dependency_view="declared",
        ),
        OperatorContext(declared_graph=graph),
    )
    assert result.truth is Truth.UNKNOWN
    assert result.cutoff is True
    assert result.reason == "cutoff_never_proves_absence"


def test_transitive_requires_positive_bounded_max_depth() -> None:
    with pytest.raises(ValueError, match="positive bounded max_depth"):
        OperatorCall(operator="exists_path", fact="a", value="c", traversal="transitive")


def test_declared_and_resolved_views_are_independent() -> None:
    declared = OperatorGraph(
        nodes=("a", "b"),
        edges=(OperatorEdge(source="a", target="b", edge_type="depends_on"),),
    )
    resolved = OperatorGraph(
        nodes=("a", "c"),
        edges=(OperatorEdge(source="a", target="c", edge_type="depends_on"),),
    )
    context = OperatorContext(declared_graph=declared, resolved_graph=resolved)
    declared_hit = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="b",
            edge_types=("depends_on",),
            traversal="direct",
            dependency_view="declared",
        ),
        context,
    )
    resolved_miss = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="b",
            edge_types=("depends_on",),
            traversal="direct",
            dependency_view="resolved",
        ),
        context,
    )
    resolved_hit = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="c",
            edge_types=("depends_on",),
            traversal="direct",
            dependency_view="resolved",
        ),
        context,
    )
    assert declared_hit.truth is Truth.TRUE
    assert resolved_miss.truth is Truth.FALSE
    assert resolved_hit.truth is Truth.TRUE


def test_cycle_known_positive_despite_unrelated_unknown_edge() -> None:
    graph = OperatorGraph(
        nodes=("a", "b", "x", "y"),
        edges=(
            OperatorEdge(source="a", target="b", edge_type="imports"),
            OperatorEdge(source="b", target="a", edge_type="imports"),
            OperatorEdge(source="x", target="y", edge_type="imports", unknown=True),
        ),
        complete=False,
    )
    result = evaluate_operator(
        OperatorCall(
            operator="cycle",
            edge_types=("imports",),
            traversal="direct",
            dependency_view="declared",
        ),
        OperatorContext(declared_graph=graph),
    )
    assert result.truth is Truth.TRUE
    assert set(result.members) == {"a", "b"}


def test_cycle_absence_needs_complete_coverage() -> None:
    graph = OperatorGraph(
        nodes=("a", "b"),
        edges=(OperatorEdge(source="a", target="b", edge_type="imports", unknown=True),),
        complete=False,
    )
    result = evaluate_operator(
        OperatorCall(
            operator="cycle",
            edge_types=("imports",),
            traversal="direct",
            dependency_view="declared",
        ),
        OperatorContext(declared_graph=graph),
    )
    assert result.truth is Truth.UNKNOWN
    assert result.reason == "incomplete_negative_graph"


def test_cycle_detection_is_deterministic_under_reordered_edges() -> None:
    edges = (
        OperatorEdge(source="b", target="a", edge_type="imports"),
        OperatorEdge(source="a", target="b", edge_type="imports"),
        OperatorEdge(source="c", target="c", edge_type="imports"),
    )
    results = []
    for order in (edges, tuple(reversed(edges)), (edges[2], edges[0], edges[1])):
        result = evaluate_operator(
            OperatorCall(
                operator="cycle",
                edge_types=("imports",),
                dependency_view="declared",
            ),
            OperatorContext(declared_graph=OperatorGraph(nodes=("a", "b", "c"), edges=order)),
        )
        results.append((result.truth, result.members))
    assert results[0] == results[1] == results[2]
    assert results[0][0] is Truth.TRUE
    assert results[0][1] == ("a", "b", "c")


def test_ratio_empty_denominator_and_six_place_rounding() -> None:
    empty = evaluate_operator(OperatorCall(operator="ratio", values=(1, 0)), OperatorContext())
    half = evaluate_operator(OperatorCall(operator="ratio", values=(1, 2)), OperatorContext())
    assert empty.metric is not None
    assert empty.metric.status is MetricStatus.NOT_APPLICABLE
    assert half.metric is not None
    assert half.metric.serialized == "0.500000"


def test_unknown_denominator_never_becomes_zero() -> None:
    result = evaluate_operator(
        OperatorCall(operator="ratio", fact="unknown_denominator"),
        OperatorContext(),
    )
    assert result.metric is not None
    assert result.metric.status is MetricStatus.UNKNOWN
    assert result.metric.value is None


def test_percentile_nearest_rank_matches_measurement_contract() -> None:
    result = evaluate_operator(
        OperatorCall(
            operator="percentile",
            value=0.9,
            values=(10, 20, 30, 40, 50, 60, 70, 80, 90, 100),
        ),
        OperatorContext(),
    )
    assert result.metric is not None
    assert result.metric.value == Decimal(90)
    empty = evaluate_operator(
        OperatorCall(operator="percentile", value=0.5, values=()),
        OperatorContext(),
    )
    assert empty.metric is not None
    assert empty.metric.status is MetricStatus.NOT_APPLICABLE


def test_boolean_true_is_not_integer_one() -> None:
    assert not typed_equal(True, 1)
    result = evaluate_operator(
        OperatorCall(operator="equals", fact="flag", value=1),
        OperatorContext(facts={"flag": FactSlot(status=FactStatus.COMPLETE, value=True)}),
    )
    assert result.truth is Truth.FALSE


def test_condition_plan_preserves_traversal_and_evaluates() -> None:
    plan = condition_plan_from(example_rule().condition)
    assert plan.operator == "cycle"
    assert plan.traversal == "direct"
    assert plan.max_depth == 1
    graph = OperatorGraph(
        nodes=("a", "b"),
        edges=(
            OperatorEdge(source="a", target="b", edge_type="imports"),
            OperatorEdge(source="b", target="a", edge_type="imports"),
        ),
    )
    result = evaluate_condition(
        plan,
        OperatorContext(declared_graph=graph, limits=OperatorLimits()),
        limits=OperatorLimits(),
    )
    assert result.truth is Truth.TRUE


def test_compiled_yaml_plan_evaluates_cycle() -> None:
    raw = yaml.safe_dump(unsigned_rule_payload(example_rule()), sort_keys=True).encode("utf-8")
    compiled = compile_rule_yaml(raw)
    assert compiled.condition is not None
    assert compiled.condition.operator == "cycle"
    assert compiled.condition.traversal == "direct"
    assert compiled.condition.max_depth == 1
    graph = OperatorGraph(
        nodes=("a", "b"),
        edges=(
            OperatorEdge(source="a", target="b", edge_type="imports"),
            OperatorEdge(source="b", target="a", edge_type="imports"),
        ),
    )
    result = evaluate_condition(
        compiled.condition,
        OperatorContext(declared_graph=graph),
        limits=OperatorLimits(),
    )
    assert result.truth is Truth.TRUE


def test_ratified_limits_match_e01_1_graph_and_regex_budgets() -> None:
    limits = operator_limits_from_ratification()
    assert limits.graph_max_depth == 32
    assert limits.graph_max_visited_nodes == 100_000
    assert limits.graph_max_visited_edges == 500_000
    assert limits.regex_max_steps == 1_000_000
    assert limits.regex_timeout_milliseconds == 100


def test_family_catalog_covers_every_operator() -> None:
    families = {family_of(name) for name in BOUNDED_OPERATORS}
    assert families == {"selection", "numeric", "graph", "change", "threshold"}
    assert default_limits().graph_max_depth == 32


def test_unknown_fact_propagates_through_equals_and_and() -> None:
    unknown_equals = evaluate_operator(
        OperatorCall(operator="equals", fact="lang", value="java"),
        OperatorContext(facts={"lang": FactSlot(status=FactStatus.UNKNOWN)}),
    )
    assert unknown_equals.truth is Truth.UNKNOWN
    combined = evaluate_operator(
        OperatorCall(
            operator="and",
            operands=(
                OperatorCall(operator="equals", fact="ok", value="yes"),
                OperatorCall(operator="equals", fact="lang", value="java"),
            ),
        ),
        OperatorContext(
            facts={
                "ok": FactSlot(status=FactStatus.COMPLETE, value="yes"),
                "lang": FactSlot(status=FactStatus.UNKNOWN),
            }
        ),
    )
    assert combined.truth is Truth.UNKNOWN


def test_threshold_not_applicable_for_empty_ratio() -> None:
    result = evaluate_operator(
        OperatorCall(
            operator="threshold",
            value=0,
            operands=(OperatorCall(operator="ratio", values=(1, 0)),),
        ),
        OperatorContext(),
    )
    assert result.truth is None
    assert result.metric is not None
    assert result.metric.status is MetricStatus.NOT_APPLICABLE


def test_transitive_depth_above_ratified_cap_is_budget_error() -> None:
    graph = OperatorGraph(
        nodes=("a", "b"),
        edges=(OperatorEdge(source="a", target="b", edge_type="imports"),),
    )
    result = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="b",
            edge_types=("imports",),
            traversal="transitive",
            max_depth=33,
            dependency_view="declared",
        ),
        OperatorContext(declared_graph=graph, limits=OperatorLimits(graph_max_depth=32)),
    )
    assert result.error is True
    assert result.reason == "budget_exceeded"


def test_missing_declared_view_is_unknown_error() -> None:
    result = evaluate_operator(
        OperatorCall(
            operator="exists_path",
            fact="a",
            value="b",
            traversal="direct",
            dependency_view="declared",
        ),
        OperatorContext(resolved_graph=OperatorGraph(nodes=("a",))),
    )
    assert result.error is True
    assert result.reason == "missing_view"


def test_invalid_regex_is_operator_error() -> None:
    result = evaluate_operator(
        OperatorCall(operator="matches", fact="path", value="("),
        OperatorContext(facts={"path": FactSlot(status=FactStatus.COMPLETE, value="api")}),
    )
    assert result.error is True
    assert result.reason == "invalid_pattern"


def test_nan_is_rejected_by_numeric_operators() -> None:
    result = evaluate_operator(
        OperatorCall(operator="sum", values=(1, float("nan"))),
        OperatorContext(),
    )
    assert result.error is True
    assert result.reason == "non_finite"


def test_incomparable_change_is_unknown() -> None:
    result = evaluate_operator(
        OperatorCall(operator="changed", fact="loc"),
        OperatorContext(baseline={"loc": 1}, candidate={"loc": 2}, comparable=False),
    )
    assert result.truth is Truth.UNKNOWN
    assert result.reason == "incomparable"
