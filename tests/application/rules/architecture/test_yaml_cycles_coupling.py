"""YAML architecture.cycles and architecture.fan-out launch catalog (E07.1)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.evidence.structure import (
    StructuralNormalizationRequest,
    normalize_structural_edges,
)
from codestrata.application.rules.architecture.yaml_catalog import (
    ARCHITECTURE_LAUNCH_RULE_IDS,
    architecture_catalog_digests,
    architecture_catalog_entries,
    load_architecture_launch_plans,
)
from codestrata.application.rules.architecture.yaml_rules import (
    architecture_operator_context,
    evaluate_architecture_launch,
)
from codestrata.application.rules.operators import evaluate_condition
from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralEdgeObservation,
    StructuralView,
)
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.operators.models import OperatorLimits

FIXTURE_DIR = (
    Path(__file__).resolve().parents[3]
    / "domain"
    / "repository_graph"
    / "fixtures"
    / "e07.1"
)
EXPECTED = json.loads((FIXTURE_DIR / "expected-outcomes.json").read_text(encoding="utf-8"))


def _import(source: str, target: str, **overrides: object) -> StructuralEdgeObservation:
    payload: dict[str, object] = {
        "edge_type": "imports",
        "source_id": source,
        "target_id": target,
        "source_type": RepositoryNodeType.MODULE,
        "target_type": RepositoryNodeType.MODULE,
        "confidence": StructuralConfidence.HIGH,
        "view": StructuralView.BOTH,
        "unknown": False,
        "resolved": True,
        "evidence_path": "src/mod.py",
    }
    payload.update(overrides)
    return StructuralEdgeObservation.model_validate(payload)


def _status(body, rule_id: str) -> str:
    record = next(item for item in body.records if item.rule_id == rule_id)
    assert record.status is not None
    return record.status.value


def test_yaml_catalog_compiles_cycles_and_fan_out() -> None:
    plans = load_architecture_launch_plans()
    assert tuple(plans) == ARCHITECTURE_LAUNCH_RULE_IDS
    assert plans["architecture.cycles"].condition is not None
    assert plans["architecture.cycles"].condition.operator == "cycle"
    assert plans["architecture.cycles"].condition.dependency_view == "resolved"
    assert plans["architecture.fan-out"].condition is not None
    assert plans["architecture.fan-out"].condition.operator == "threshold"
    assert plans["architecture.fan-out"].condition.value == 10
    assert architecture_catalog_entries()[0].rule_id == "architecture.cycles"
    digests = architecture_catalog_digests()
    assert "architecture.cycles" in digests
    assert "architecture.fan-out.plan" in digests


def test_yaml_cycle_a_b_a_fails_and_acyclic_passes() -> None:
    cyclic = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.b"), _import("mod.b", "mod.a")),
            module_ids=("mod.a", "mod.b"),
        )
    )
    acyclic = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.b"),),
            module_ids=("mod.a", "mod.b"),
        )
    )
    cyclic_body = evaluate_architecture_launch(cyclic)
    acyclic_body = evaluate_architecture_launch(acyclic)
    assert _status(cyclic_body, "architecture.cycles") == EXPECTED["m05"]["cycle_ab"]["yaml_cycles"]
    assert (
        _status(acyclic_body, "architecture.cycles") == EXPECTED["m05"]["acyclic_ab"]["yaml_cycles"]
    )


def test_yaml_self_loop_fails() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.a"),),
            module_ids=("mod.a",),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert _status(body, "architecture.cycles") == EXPECTED["m05"]["self_loop"]["yaml_cycles"]


def test_yaml_unresolved_and_partial_roots_cannot_pass_negative_cycle() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.missing", unknown=True, resolved=False),),
            module_ids=("mod.a",),
            missing_source_roots=("src/missing",),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert (
        _status(body, "architecture.cycles") == EXPECTED["m05"]["unresolved_import"]["yaml_cycles"]
    )


def test_yaml_known_cycle_fails_with_unrelated_unknown() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.b"),
                _import("mod.b", "mod.a"),
                _import("mod.c", "mod.missing", unknown=True, resolved=False),
            ),
            module_ids=("mod.a", "mod.b", "mod.c"),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert (
        _status(body, "architecture.cycles")
        == EXPECTED["m05"]["known_cycle_unrelated_unknown"]["yaml_cycles"]
    )


def test_yaml_fan_out_10_passes_11_fails() -> None:
    ten_obs = tuple(_import("mod.hub", f"mod.{index}") for index in range(10))
    eleven_obs = ten_obs + (_import("mod.hub", "mod.10"),)
    ten = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=ten_obs,
            module_ids=("mod.hub",) + tuple(f"mod.{index}" for index in range(10)),
        )
    )
    eleven = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=eleven_obs,
            module_ids=("mod.hub",) + tuple(f"mod.{index}" for index in range(11)),
        )
    )
    assert _status(evaluate_architecture_launch(ten), "architecture.fan-out") == EXPECTED["m06"][
        "fan_out_10"
    ]["yaml_fan_out"]
    assert _status(evaluate_architecture_launch(eleven), "architecture.fan-out") == EXPECTED["m06"][
        "fan_out_11"
    ]["yaml_fan_out"]


def test_yaml_unknown_imports_do_not_confidently_pass_fan_out() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("mod.a", "mod.b"),
                _import("mod.a", "mod.missing", unknown=True, resolved=False),
            ),
            module_ids=("mod.a", "mod.b"),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert (
        _status(body, "architecture.fan-out")
        == EXPECTED["m06"]["unknown_imports"]["yaml_fan_out"]
    )


def test_yaml_cycle_budget_is_error_not_pass() -> None:
    plans = load_architecture_launch_plans()
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.b"),),
            module_ids=("mod.a", "mod.b"),
        )
    )
    result = evaluate_condition(
        plans["architecture.cycles"].condition,
        evidence.operator_context(limits=OperatorLimits(graph_max_visited_nodes=0)),
    )
    assert interpret_operator_result(result) is ResultStatus.ERROR
    assert result.error is True


def test_same_structural_inputs_are_digest_identical() -> None:
    request = StructuralNormalizationRequest(
        observations=(_import("mod.a", "mod.b"), _import("mod.b", "mod.a")),
        module_ids=("mod.a", "mod.b"),
    )
    digests = [normalize_structural_edges(request).facts_digest for _ in range(3)]
    assert digests[0] == digests[1] == digests[2]
    context = architecture_operator_context(normalize_structural_edges(request))
    assert context.resolved_graph is not None
    bodies = [
        evaluate_architecture_launch(normalize_structural_edges(request)).content_digest()
        for _ in range(3)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
