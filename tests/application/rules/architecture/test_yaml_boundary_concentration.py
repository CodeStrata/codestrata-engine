"""YAML architecture.boundary and architecture.concentration (E07.2)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from codestrata.application.evidence.structure import (
    StructuralNormalizationRequest,
    normalize_structural_edges,
)
from codestrata.application.rules.architecture.yaml_catalog import (
    BOUNDARY_RULE_ID,
    CONCENTRATION_RULE_ID,
    load_architecture_launch_plans,
)
from codestrata.application.rules.architecture.yaml_rules import (
    bundled_boundary_pattern,
    evaluate_architecture_launch,
)
from codestrata.application.rules.compiler import compile_rule_yaml
from codestrata.application.rules.operators import evaluate_condition
from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.metrics import (
    BoundaryPattern,
    ReachQuery,
    SourceLineFile,
)
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralEdgeObservation,
    StructuralView,
)
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.operators.models import OperatorLimits

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "domain"
    / "repository_graph"
    / "fixtures"
    / "e07.2"
    / "expected-outcomes.json"
)
EXPECTED = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _import(source: str, target: str, **overrides: object) -> StructuralEdgeObservation:
    payload: dict[str, object] = {
        "edge_type": "imports",
        "source_id": source,
        "target_id": target,
        "source_type": RepositoryNodeType.MODULE,
        "target_type": RepositoryNodeType.MODULE,
        "confidence": StructuralConfidence.HIGH,
        "view": StructuralView.RESOLVED,
        "unknown": False,
        "resolved": True,
        "evidence_path": "src/api/mod.py",
    }
    payload.update(overrides)
    return StructuralEdgeObservation.model_validate(payload)


def _status(body, rule_id: str) -> str:
    record = next(item for item in body.records if item.rule_id == rule_id)
    assert record.status is not None
    return record.status.value


def _record(body, rule_id: str):
    return next(item for item in body.records if item.rule_id == rule_id)


def _files(left: int, right: int, **extra: object) -> tuple[SourceLineFile, ...]:
    generated = bool(extra.get("generated"))
    unmapped = bool(extra.get("unmapped"))
    unreadable = bool(extra.get("unreadable"))
    files = [
        SourceLineFile(
            relative_path="src/component-a.py",
            component_id="component.a",
            source_text="\n".join(["value"] * left + ["", "# note"]),
        ),
        SourceLineFile(
            relative_path="src/component-b.py",
            component_id="component.b",
            source_text="\n".join(["value"] * right),
        ),
    ]
    if generated:
        files.append(
            SourceLineFile(
                relative_path="gen/out.py",
                component_id="component.a",
                source_text="\n".join(["value"] * 1000),
                generated=True,
            )
        )
    if unmapped:
        files.append(
            SourceLineFile(
                relative_path="src/loose.py",
                component_id="",
                source_text="\n".join(["value"] * 40),
            )
        )
    if unreadable:
        files.append(
            SourceLineFile(
                relative_path="src/locked.py",
                component_id="component.c",
                source_text="\n".join(["value"] * 500),
                readable=False,
            )
        )
    return tuple(files)


def test_boundary_yaml_pins_direct_depth_and_resolved_view() -> None:
    plan = load_architecture_launch_plans()[BOUNDARY_RULE_ID]
    condition = plan.condition
    assert condition is not None
    assert condition.operator == "crosses_boundary"
    assert condition.fact == "api"
    assert condition.value == "internal"
    assert condition.traversal == "direct"
    assert condition.max_depth == 1
    assert condition.dependency_view == "resolved"
    assert "api" not in plan.capabilities.facts
    assert plan.rule is not None
    defaults = {item.name: item.default for item in plan.rule.parameter_schema}
    assert defaults["source_pattern"] == "api"
    assert defaults["target_pattern"] == "internal"
    assert defaults["constraint_id"] == "forbid:api->internal"


def test_api_internal_fails_with_concrete_path_and_api_public_passes() -> None:
    expected = EXPECTED["m07"]
    pattern = bundled_boundary_pattern()
    violating = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal"),),
            module_ids=("api", "internal", "public"),
            boundary_pattern=pattern,
        )
    )
    compliant = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "public", evidence_path="src/api/public.py"),),
            module_ids=("api", "public"),
            boundary_pattern=pattern,
        )
    )
    persistence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "persistence"),),
            module_ids=("api", "persistence"),
            boundary_pattern=pattern,
        )
    )
    fail_body = evaluate_architecture_launch(violating)
    pass_body = evaluate_architecture_launch(compliant)
    other_body = evaluate_architecture_launch(persistence)
    assert _status(fail_body, BOUNDARY_RULE_ID) == expected["api_internal"]["yaml"]
    evidence = _record(fail_body, BOUNDARY_RULE_ID).evidence
    assert evidence
    assert evidence[0].subject_id == expected["api_internal"]["identity"]
    assert evidence[0].relative_path == expected["api_internal"]["path"]
    assert evidence[0].attributes["dependency_path"] == expected["api_internal"]["identity"]
    assert _status(pass_body, BOUNDARY_RULE_ID) == expected["api_public"]["yaml"]
    assert _status(other_body, BOUNDARY_RULE_ID) == expected["persistence"]["yaml"]


def test_unresolved_import_is_unknown_and_missing_pattern_is_not_applicable() -> None:
    expected = EXPECTED["m07"]
    unresolved = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal", unknown=True, resolved=False),),
            module_ids=("api", "internal"),
            boundary_pattern=bundled_boundary_pattern(),
        )
    )
    undeclared = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal"),),
            module_ids=("api", "internal"),
        )
    )
    assert (
        _status(evaluate_architecture_launch(unresolved), BOUNDARY_RULE_ID)
        == expected["unresolved"]["yaml"]
    )
    assert (
        _status(evaluate_architecture_launch(undeclared), BOUNDARY_RULE_ID)
        == expected["no_pattern"]["yaml"]
    )


def test_every_glob_violation_keeps_its_own_path() -> None:
    expected = EXPECTED["m07"]["two_paths"]
    pattern = BoundaryPattern(
        constraint_id="forbid:api/**->internal/**",
        source_pattern="api/**",
        target_pattern="internal/**",
        allowed_directions=("api/**>public/**",),
    )
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("api/a", "internal/x", evidence_path="src/api/a.py"),
                _import("api/b", "internal/y", evidence_path="src/api/b.py"),
            ),
            module_ids=("api/a", "api/b", "internal/x", "internal/y"),
            boundary_pattern=pattern,
        )
    )
    body = evaluate_architecture_launch(evidence)
    found = {
        item.subject_id: item.relative_path for item in _record(body, BOUNDARY_RULE_ID).evidence
    }
    assert found == expected["paths"]
    assert list(found) == expected["members"]


def test_local_pattern_changes_run_digest_and_selector_rebind_errors() -> None:
    expected = EXPECTED["m07"]["selector_rebinding"]
    internal = bundled_boundary_pattern()
    public_forbid = BoundaryPattern(
        constraint_id="forbid:api->public",
        source_pattern="api",
        target_pattern="public",
        allowed_directions=("api>internal",),
    )
    request = StructuralNormalizationRequest(
        observations=(_import("api", "internal"), _import("api", "public")),
        module_ids=("api", "internal", "public"),
    )
    first = normalize_structural_edges(request.model_copy(update={"boundary_pattern": internal}))
    second = normalize_structural_edges(
        request.model_copy(update={"boundary_pattern": public_forbid})
    )
    assert first.facts_digest != second.facts_digest
    bodies = [evaluate_architecture_launch(first).facts_digest for _ in range(3)]
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0] != evaluate_architecture_launch(second).facts_digest
    plan = load_architecture_launch_plans()[BOUNDARY_RULE_ID]
    assert plan.rule is not None
    raw = plan.rule.model_dump(mode="json")
    select = dict(raw["select"])
    select["nodes"] = {"all": [{"type": "module"}, {"path": "public"}]}
    raw["select"] = select
    raw.pop("digest", None)
    rebound = compile_rule_yaml(_yaml_bytes(raw))
    assert rebound.selector_digest != plan.selector_digest
    rebound_pattern = bundled_boundary_pattern(selector_digest=rebound.selector_digest)
    rebound_evidence = normalize_structural_edges(
        request.model_copy(update={"boundary_pattern": rebound_pattern})
    )
    record = _record(evaluate_architecture_launch(rebound_evidence), BOUNDARY_RULE_ID)
    assert record.status is not None
    assert record.status.value == expected["status"]
    assert record.reason == expected["reason"]
    matched = bundled_boundary_pattern(selector_digest=plan.selector_digest)
    matched_evidence = normalize_structural_edges(
        request.model_copy(update={"boundary_pattern": matched})
    )
    assert _status(evaluate_architecture_launch(matched_evidence), BOUNDARY_RULE_ID) == "fail"


def test_declared_edge_does_not_fail_resolved_boundary() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal", view=StructuralView.DECLARED),),
            module_ids=("api", "internal"),
            boundary_pattern=bundled_boundary_pattern(),
        )
    )
    assert _status(evaluate_architecture_launch(evidence), BOUNDARY_RULE_ID) == "pass"
    declared = ReachQuery(
        seed="api",
        universe=("api", "internal"),
        dependency_view="declared",
        traversal="direct",
        max_depth=1,
    )
    reached = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal", view=StructuralView.DECLARED),),
            module_ids=("api", "internal"),
            reach_query=declared,
        )
    )
    assert reached.reach is not None
    assert reached.reach.dependency_view == "declared"
    assert reached.reach.traversal == "direct"
    assert list(reached.reach.reached) == ["internal"]
    assert reached.reach.cutoff is False


def test_bounded_reach_on_resolved_graph_discloses_truncation() -> None:
    query = ReachQuery(
        seed="api",
        universe=("api", "public", "internal"),
        dependency_view="resolved",
        traversal="direct",
        max_depth=1,
    )
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("api", "public"),
                _import("public", "internal"),
            ),
            module_ids=("api", "public", "internal"),
            reach_query=query,
        )
    )
    assert evidence.reach is not None
    assert list(evidence.reach.reached) == ["public"]
    assert evidence.reach.cutoff is True
    assert evidence.reach.computation.status.value == "unknown"
    assert evidence.reach.computation.extra["truncated"] is True
    assert "internal" not in evidence.reach.reached


def test_concentration_thresholds_and_partial_files() -> None:
    expected = EXPECTED["m08"]
    cases = (
        ("share_60", _files(60, 40)),
        ("share_61", _files(61, 39)),
        ("generated", _files(61, 39, generated=True)),
        ("unmapped", _files(30, 30, unmapped=True)),
        ("unreadable", _files(60, 40, unreadable=True)),
    )
    for name, files in cases:
        evidence = normalize_structural_edges(
            StructuralNormalizationRequest(source_files=files, module_ids=("component.a",))
        )
        body = evaluate_architecture_launch(evidence)
        assert _status(body, CONCENTRATION_RULE_ID) == expected[name]["yaml"]
        assert evidence.concentration.max_share.serialized == expected[name]["serialized"]
    single = normalize_structural_edges(
        StructuralNormalizationRequest(
            source_files=(
                SourceLineFile(
                    relative_path="src/only.py",
                    component_id="component.a",
                    source_text="\n".join(["value"] * 100),
                ),
            )
        )
    )
    assert (
        _status(evaluate_architecture_launch(single), CONCENTRATION_RULE_ID)
        == expected["single"]["yaml"]
    )
    over = normalize_structural_edges(StructuralNormalizationRequest(source_files=_files(61, 39)))
    record = _record(evaluate_architecture_launch(over), CONCENTRATION_RULE_ID)
    assert record.evidence
    assert record.evidence[0].relative_path == expected["share_61"]["witness_path"]
    assert record.evidence[0].attributes["denominator"] == "100"
    assert record.evidence[0].attributes["derivation"] == "nonblank_noncomment_full_line.v1"


def test_boundary_budget_is_error() -> None:
    plan = load_architecture_launch_plans()[BOUNDARY_RULE_ID]
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("api", "internal"),),
            module_ids=("api", "internal"),
            boundary_pattern=bundled_boundary_pattern(),
        )
    )
    result = evaluate_condition(
        plan.condition,
        evidence.operator_context(limits=OperatorLimits(max_cost_units=0)),
    )
    assert interpret_operator_result(result) is ResultStatus.ERROR
    assert result.error is True


def _yaml_bytes(payload: dict[str, object]) -> bytes:
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")
