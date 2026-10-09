"""Independent M05/M06 expected fixtures for structural cycles and coupling."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.domain.contracts.enums import MetricStatus
from codestrata.domain.repository_graph.metrics import (
    ModuleEdge,
    m05_module_cycles,
    m06_module_coupling,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e07.1"
EXPECTED = json.loads((FIXTURE_DIR / "expected-outcomes.json").read_text(encoding="utf-8"))


def _edge(
    source: str,
    target: str,
    *,
    unknown: bool = False,
    edge_type: str = "imports",
) -> ModuleEdge:
    return ModuleEdge(
        source=source,
        target=target,
        edge_type=edge_type,
        unknown=unknown,
        relationship_id=f"rel:{edge_type}:{source}=>{target}",
    )


def test_m05_cycle_a_b_a_counts_one_scc() -> None:
    expected = EXPECTED["m05"]["cycle_ab"]
    metric = m05_module_cycles(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b"), _edge("mod.b", "mod.a")),
        complete=True,
    )
    assert metric.count == expected["count"]
    assert list(metric.member_ids) == expected["members"]
    assert metric.components[0].witness_edge_ids
    assert metric.computation.status is MetricStatus.VALUE


def test_m05_acyclic_a_b_is_zero() -> None:
    expected = EXPECTED["m05"]["acyclic_ab"]
    metric = m05_module_cycles(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b"),),
        complete=True,
    )
    assert metric.count == expected["count"]
    assert list(metric.member_ids) == expected["members"]
    assert metric.computation.status is MetricStatus.VALUE
    assert metric.computation.serialized == "0"


def test_m05_self_loop_counts_once() -> None:
    expected = EXPECTED["m05"]["self_loop"]
    metric = m05_module_cycles(
        ("mod.a",),
        (_edge("mod.a", "mod.a"),),
        complete=True,
    )
    assert metric.count == expected["count"]
    assert list(metric.member_ids) == expected["members"]
    assert metric.components[0].self_loop is True


def test_m05_unresolved_import_cannot_pass_absence() -> None:
    expected = EXPECTED["m05"]["unresolved_import"]
    metric = m05_module_cycles(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b", unknown=True),),
        complete=True,
    )
    assert metric.count == expected["count"]
    assert metric.computation.status.value == expected["metric_status"]
    assert metric.unresolved_edges == 1


def test_m05_known_cycle_fails_despite_unrelated_unknown() -> None:
    expected = EXPECTED["m05"]["known_cycle_unrelated_unknown"]
    metric = m05_module_cycles(
        ("mod.a", "mod.b", "mod.c"),
        (
            _edge("mod.a", "mod.b"),
            _edge("mod.b", "mod.a"),
            _edge("mod.c", "mod.missing", unknown=True),
        ),
        complete=False,
    )
    assert metric.count == expected["count"]
    assert list(metric.member_ids) == expected["members"]
    assert metric.computation.status is MetricStatus.VALUE


def test_m05_reordered_traversal_same_members_and_count() -> None:
    first = m05_module_cycles(
        ("mod.b", "mod.a"),
        (_edge("mod.b", "mod.a"), _edge("mod.a", "mod.b")),
        complete=True,
    )
    second = m05_module_cycles(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b"), _edge("mod.b", "mod.a")),
        complete=True,
    )
    assert first.count == second.count == EXPECTED["m05"]["cycle_ab"]["count"]
    assert first.member_ids == second.member_ids
    assert first.components[0].witness_edge_ids == second.components[0].witness_edge_ids


def test_m06_fan_out_boundary_10_and_11() -> None:
    ten_edges = tuple(_edge("mod.hub", f"mod.{index}") for index in range(10))
    eleven_edges = ten_edges + (_edge("mod.hub", "mod.10"),)
    modules_ten = ("mod.hub",) + tuple(f"mod.{index}" for index in range(10))
    modules_eleven = modules_ten + ("mod.10",)
    ten = m06_module_coupling(modules_ten, ten_edges, complete=True)
    eleven = m06_module_coupling(modules_eleven, eleven_edges, complete=True)
    assert ten.max_fan_out.value == EXPECTED["m06"]["fan_out_10"]["max_fan_out"]
    assert eleven.max_fan_out.value == EXPECTED["m06"]["fan_out_11"]["max_fan_out"]
    hub = next(item for item in ten.modules if item.module_id == "mod.hub")
    assert hub.fan_out == 10
    leaf = next(item for item in ten.modules if item.module_id == "mod.0")
    assert leaf.fan_in == 1
    assert leaf.fan_out == 0


def test_m06_duplicate_edges_count_once() -> None:
    metric = m06_module_coupling(
        ("mod.a", "mod.b"),
        (
            _edge("mod.a", "mod.b"),
            _edge("mod.a", "mod.b"),
            _edge("mod.a", "mod.b", edge_type="depends_on"),
        ),
        complete=True,
    )
    assert metric.max_fan_out.value == EXPECTED["m06"]["duplicate_edges"]["max_fan_out"]
    hub = next(item for item in metric.modules if item.module_id == "mod.a")
    assert hub.fan_out == 1


def test_m06_zero_file_edges_ratio_not_applicable() -> None:
    metric = m06_module_coupling(("mod.a",), (), complete=True)
    assert (
        metric.external_edge_ratio.status.value
        == EXPECTED["m06"]["zero_file_edges"]["ratio_status"]
    )
    assert metric.max_fan_out.status is MetricStatus.VALUE
    assert metric.max_fan_out.serialized == "0"


def test_m06_unknown_imports_are_lower_bound_not_pass() -> None:
    metric = m06_module_coupling(
        ("mod.a", "mod.b"),
        (_edge("mod.a", "mod.b"), _edge("mod.a", "mod.missing", unknown=True)),
        complete=True,
    )
    assert metric.max_fan_out.status.value == EXPECTED["m06"]["unknown_imports"]["metric_status"]
    assert metric.unresolved_excluded == 1
    assert metric.max_fan_out.extra["lower_bound"] is True


def test_m06_known_over_threshold_can_fail_with_unknowns() -> None:
    edges = tuple(_edge("mod.hub", f"mod.{index}") for index in range(11))
    edges = edges + (_edge("mod.hub", "mod.missing", unknown=True),)
    modules = ("mod.hub",) + tuple(f"mod.{index}" for index in range(11))
    metric = m06_module_coupling(modules, edges, complete=False)
    assert metric.max_fan_out.status is MetricStatus.VALUE
    assert metric.max_fan_out.value == 11
