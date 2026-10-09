"""E07.3 parity map, remaining YAML rules, and language-tier projections."""

from __future__ import annotations

from decimal import Decimal

import pytest

from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.application.evidence.structure.consumer import (
    FOUR_OUTCOMES,
    ConsumerContractError,
    consume_architecture_projection,
)
from codestrata.application.evidence.structure.language_paths import (
    declared_language_tiers,
    structural_request_from_language,
)
from codestrata.application.evidence.structure.normalize import (
    StructuralNormalizationRequest,
    normalize_structural_edges,
)
from codestrata.application.evidence.structure.projection import project_architecture_comparison
from codestrata.application.rules.architecture.parity import (
    ARCHITECTURE_PARITY,
    NOT_RETAINED_ARCHITECTURE_RULES,
)
from codestrata.application.rules.architecture.yaml_catalog import (
    ARCHITECTURE_LAUNCH_RULE_IDS,
    load_architecture_launch_plans,
)
from codestrata.application.rules.architecture.yaml_rules import evaluate_architecture_launch
from codestrata.application.rules.operators import evaluate_condition
from codestrata.domain.contracts.catalog import build_launch_ratification
from codestrata.domain.contracts.enums import ResultStatus
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.metrics import (
    DirectionConstraint,
    FrameworkLeakageHit,
    FrameworkSubject,
    ModuleLayer,
)
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralEdgeObservation,
    StructuralView,
)
from codestrata.domain.rules.architecture.ids import RULE_ENTERPRISE_STANDARD_MISMATCH
from codestrata.domain.rules.assessment import interpret_operator_result
from codestrata.domain.rules.operators.models import OperatorLimits


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


def _record(body, rule_id: str):
    return next(item for item in body.records if item.rule_id == rule_id)


def test_parity_covers_retained_rules_without_score_equivalence() -> None:
    ratification = build_launch_ratification()
    retained = {
        rule_id
        for rule_id in ratification.retained_existing_rule_ids
        if rule_id.startswith("architecture.")
    }
    mapped = {item.python_rule_id for item in ARCHITECTURE_PARITY}
    assert mapped == retained
    assert all(item.score_equivalent is False for item in ARCHITECTURE_PARITY)
    assert {item.yaml_rule_id for item in ARCHITECTURE_PARITY} == set(ARCHITECTURE_LAUNCH_RULE_IDS)
    withheld = {item.python_rule_id for item in NOT_RETAINED_ARCHITECTURE_RULES}
    assert RULE_ENTERPRISE_STANDARD_MISMATCH in withheld
    assert "architecture.service-dependency-cycle" in withheld
    plans = load_architecture_launch_plans()
    for item in ARCHITECTURE_PARITY:
        plan = plans[item.yaml_rule_id]
        assert plan.rule is not None
        assert plan.rule.finding.default_severity.value == item.default_severity
        defaults = {field.name: field.default for field in plan.rule.parameter_schema}
        for name, expected in item.default_parameters.items():
            if name not in defaults:
                continue
            actual = defaults[name]
            if isinstance(actual, int | float):
                assert Decimal(str(actual)) == Decimal(expected)
            else:
                assert str(actual) == expected


def test_direction_and_leakage_have_four_outcomes() -> None:
    allowed = DirectionConstraint(
        constraint_id="allow:presentation>application",
        allowed_directions=("presentation>application",),
    )
    compliant = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("presentation.web", "application.service"),),
            module_ids=("presentation.web", "application.service"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="application.service", layer="application"),
            ),
            direction_constraint=allowed,
            framework_subjects=(
                FrameworkSubject(
                    unit_id="domain.order",
                    layer="domain",
                    layer_confidence="medium",
                    language="java",
                    framework_structural=True,
                ),
            ),
        )
    )
    violating = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import(
                    "presentation.web",
                    "persistence.store",
                    evidence_path="src/main/java/com/example/web/Home.java",
                ),
                _import(
                    "presentation.web",
                    "persistence.store",
                    evidence_path="src/main/java/com/example/web/Home.java",
                ),
            ),
            module_ids=("presentation.web", "persistence.store"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="persistence.store", layer="persistence"),
            ),
            direction_constraint=allowed,
            framework_subjects=(
                FrameworkSubject(
                    unit_id="domain.order",
                    layer="domain",
                    layer_confidence="medium",
                    language="java",
                    framework_structural=True,
                ),
            ),
            framework_hits=(
                FrameworkLeakageHit(
                    unit_id="domain.order",
                    framework="jpa",
                    symbol="@Entity",
                    path="src/main/java/com/example/domain/Order.java",
                    language="java",
                ),
            ),
        )
    )
    incomplete = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import(
                    "presentation.web",
                    "persistence.store",
                    unknown=True,
                    resolved=False,
                ),
            ),
            module_ids=("presentation.web", "persistence.store"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="persistence.store", layer="persistence"),
            ),
            direction_constraint=allowed,
            framework_subjects=(
                FrameworkSubject(
                    unit_id="src/domain",
                    layer="domain",
                    layer_confidence="medium",
                    language="javascript",
                    framework_structural=False,
                ),
            ),
        )
    )
    absent = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.b"),),
            module_ids=("mod.a", "mod.b"),
        )
    )
    compliant_body = evaluate_architecture_launch(compliant)
    violating_body = evaluate_architecture_launch(violating)
    incomplete_body = evaluate_architecture_launch(incomplete)
    absent_body = evaluate_architecture_launch(absent)
    assert _status(compliant_body, "architecture.invalid-dependency-direction") == "pass"
    assert _status(compliant_body, "architecture.framework-leakage") == "pass"
    assert _status(violating_body, "architecture.invalid-dependency-direction") == "fail"
    assert violating.direction.count == 1
    direction = _record(violating_body, "architecture.invalid-dependency-direction")
    assert direction.evidence[0].relative_path == "src/main/java/com/example/web/Home.java"
    assert _status(violating_body, "architecture.framework-leakage") == "fail"
    leakage = _record(violating_body, "architecture.framework-leakage")
    assert leakage.evidence[0].attributes["symbol"] == "@Entity"
    assert _status(incomplete_body, "architecture.invalid-dependency-direction") == "unknown"
    assert _status(incomplete_body, "architecture.framework-leakage") == "unknown"
    assert _status(absent_body, "architecture.invalid-dependency-direction") == "not_applicable"
    assert _status(absent_body, "architecture.framework-leakage") == "not_applicable"


def test_known_direction_violation_fails_with_an_unrelated_unknown_edge() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(
                _import("presentation.web", "persistence.store"),
                _import("mod.a", "mod.missing", unknown=True, resolved=False),
            ),
            module_ids=("presentation.web", "persistence.store", "mod.a"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="persistence.store", layer="persistence"),
            ),
            direction_constraint=DirectionConstraint(
                constraint_id="allow:presentation>application",
                allowed_directions=("presentation>application",),
            ),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert _status(body, "architecture.invalid-dependency-direction") == "fail"


def test_direction_selector_rebind_is_error() -> None:
    plan = load_architecture_launch_plans()["architecture.invalid-dependency-direction"]
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("presentation.web", "persistence.store"),),
            module_ids=("presentation.web", "persistence.store"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="persistence.store", layer="persistence"),
            ),
            direction_constraint=DirectionConstraint(
                constraint_id="allow:presentation>application",
                allowed_directions=("presentation>application",),
                selector_digest="not-the-compiled-selector",
            ),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert _status(body, "architecture.invalid-dependency-direction") == "error"
    assert _record(body, "architecture.invalid-dependency-direction").reason == "selector_rebinding"
    assert plan.selector_digest != "not-the-compiled-selector"


def test_direction_budget_is_error() -> None:
    plan = load_architecture_launch_plans()["architecture.invalid-dependency-direction"]
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("mod.a", "mod.b"),),
            module_ids=("mod.a", "mod.b"),
            direction_constraint=DirectionConstraint(
                constraint_id="allow:a>b",
                allowed_directions=("api>public",),
            ),
            module_layers=(
                ModuleLayer(module_id="mod.a", layer="api"),
                ModuleLayer(module_id="mod.b", layer="public"),
            ),
        )
    )
    result = evaluate_condition(
        plan.condition,
        evidence.operator_context(limits=OperatorLimits(max_cost_units=0)),
    )
    assert interpret_operator_result(result) is ResultStatus.ERROR


def test_structural_hit_fails_when_another_domain_unit_is_unscanned() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            framework_subjects=(
                FrameworkSubject(
                    unit_id="domain.order",
                    layer="domain",
                    layer_confidence="medium",
                    language="java",
                    framework_structural=True,
                ),
                FrameworkSubject(
                    unit_id="src/domain",
                    layer="domain",
                    layer_confidence="medium",
                    language="javascript",
                    framework_structural=False,
                ),
            ),
            framework_hits=(
                FrameworkLeakageHit(
                    unit_id="domain.order",
                    framework="jpa",
                    symbol="@Entity",
                    path="src/Order.java",
                    language="java",
                ),
            ),
        )
    )
    body = evaluate_architecture_launch(evidence)
    assert _status(body, "architecture.framework-leakage") == "fail"


def test_every_retained_yaml_rule_has_compliant_violating_and_incomplete_cases() -> None:
    cycle_fail = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("mod.a", "mod.b"), _import("mod.b", "mod.a")),
                module_ids=("mod.a", "mod.b"),
            )
        )
    )
    cycle_pass = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("mod.a", "mod.b"),),
                module_ids=("mod.a", "mod.b"),
            )
        )
    )
    cycle_unknown = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("mod.a", "mod.b"),),
                module_ids=("mod.a", "mod.b"),
                missing_source_roots=("src",),
            )
        )
    )
    fan_fail = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=tuple(_import("hub", f"mod.{index}") for index in range(11)),
                module_ids=tuple(["hub", *[f"mod.{index}" for index in range(11)]]),
            )
        )
    )
    fan_pass = cycle_pass
    fan_unknown = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("mod.a", "mod.missing", unknown=True, resolved=False),),
                module_ids=("mod.a",),
            )
        )
    )
    from codestrata.application.rules.architecture.yaml_rules import bundled_boundary_pattern

    boundary_fail = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("api", "internal"),),
                module_ids=("api", "internal"),
                boundary_pattern=bundled_boundary_pattern(),
            )
        )
    )
    boundary_pass = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("api", "public"),),
                module_ids=("api", "public"),
                boundary_pattern=bundled_boundary_pattern(),
            )
        )
    )
    boundary_unknown = evaluate_architecture_launch(
        normalize_structural_edges(
            StructuralNormalizationRequest(
                observations=(_import("api", "internal", unknown=True, resolved=False),),
                module_ids=("api", "internal"),
                boundary_pattern=bundled_boundary_pattern(),
            )
        )
    )
    share_pass = _concentration(("a", 60), ("b", 40))
    share_fail = _concentration(("a", 61), ("b", 39))
    share_unknown = _concentration(("a", 10), ("b", 10), unmapped=True)
    assert _status(cycle_fail, "architecture.cycles") == "fail"
    assert _status(cycle_pass, "architecture.cycles") == "pass"
    assert _status(cycle_unknown, "architecture.cycles") == "unknown"
    assert _status(fan_fail, "architecture.fan-out") == "fail"
    assert _status(fan_pass, "architecture.fan-out") == "pass"
    assert _status(fan_unknown, "architecture.fan-out") == "unknown"
    assert _status(boundary_fail, "architecture.boundary") == "fail"
    assert _status(boundary_pass, "architecture.boundary") == "pass"
    assert _status(boundary_unknown, "architecture.boundary") == "unknown"
    assert _status(share_pass, "architecture.concentration") == "pass"
    assert _status(share_fail, "architecture.concentration") == "fail"
    assert _status(share_unknown, "architecture.concentration") == "unknown"


def test_projection_is_comparison_ready_without_a_score() -> None:
    evidence = normalize_structural_edges(
        StructuralNormalizationRequest(
            observations=(_import("presentation.web", "persistence.store"),),
            module_ids=("presentation.web", "persistence.store"),
            module_layers=(
                ModuleLayer(module_id="presentation.web", layer="presentation"),
                ModuleLayer(module_id="persistence.store", layer="persistence"),
            ),
            direction_constraint=DirectionConstraint(
                constraint_id="allow:presentation>application",
                allowed_directions=("presentation>application",),
            ),
            framework_subjects=(
                FrameworkSubject(
                    unit_id="src/domain",
                    layer="domain",
                    layer_confidence="medium",
                    language="javascript",
                    framework_structural=False,
                ),
            ),
        )
    )
    bodies = [evaluate_architecture_launch(evidence) for _ in range(3)]
    assert len({item.content_digest() for item in bodies}) == 1
    projection = project_architecture_comparison(evidence, bodies[0])
    payload = projection.model_dump(mode="json")
    consumed = consume_architecture_projection(payload)
    statuses = {item.status for item in consumed.records}
    assert FOUR_OUTCOMES <= statuses
    assert consumed.graph.centrality_status == "descriptive"
    assert consumed.old_score is None
    rejected = dict(payload)
    rejected["score_equivalent"] = True
    with pytest.raises(ConsumerContractError):
        consume_architecture_projection(rejected)
    scored = dict(payload)
    scored["health_score"] = 80
    with pytest.raises(ConsumerContractError):
        consume_architecture_projection(scored)


def test_java_and_js_structural_paths_keep_declared_lower_tiers() -> None:
    tiers = {item.language: item for item in declared_language_tiers()}
    for language in ("java", "javascript", "typescript"):
        assert tiers[language].launch_tier == "deepest_target"
    for language in ("python", "php", "csharp"):
        assert tiers[language].launch_tier == "verified_retained"
        assert tiers[language].structural_maturity == "partial"
    assert tiers["javascript"].framework_structural is True
    assert tiers["typescript"].framework_structural is True
    assert tiers["java"].framework_structural is True

    service = create_language_evidence_service()
    java = service.collect(
        repository_id="fixture",
        relative_paths=(
            "src/main/java/com/example/domain/Order.java",
            "src/main/java/com/example/web/Home.java",
            "src/main/java/com/example/persistence/Store.java",
        ),
        file_texts={
            "src/main/java/com/example/domain/Order.java": (
                "package com.example.domain;\nimport javax.persistence.Entity;\n"
                "@Entity\npublic class Order {}\n"
            ),
            "src/main/java/com/example/web/Home.java": (
                "package com.example.web;\nimport com.example.persistence.Store;\n"
                "public class Home {}\n"
            ),
            "src/main/java/com/example/persistence/Store.java": (
                "package com.example.persistence;\npublic class Store {}\n"
            ),
        },
    )
    java_projection = structural_request_from_language(
        java.aggregated,
        direction_constraint=DirectionConstraint(
            constraint_id="allow:presentation>application",
            allowed_directions=("presentation>application",),
        ),
    )
    java_evidence = normalize_structural_edges(java_projection.request)
    assert java_evidence.admitted
    java_body = evaluate_architecture_launch(java_evidence)
    assert _status(java_body, "architecture.invalid-dependency-direction") == "fail"
    assert _status(java_body, "architecture.framework-leakage") == "fail"
    java_compare = project_architecture_comparison(
        java_evidence,
        java_body,
        language_tiers=java_projection.tiers,
    )
    consume_architecture_projection(java_compare.model_dump(mode="json"))

    script = service.collect(
        repository_id="fixture",
        relative_paths=("src/domain/order.ts", "src/api/client.ts"),
        file_texts={
            "src/domain/order.ts": (
                'import { client } from "src/api";\nimport { local } from "./local";\n'
                "export const order = client;\n"
            ),
            "src/api/client.ts": "export const client = 1;\n",
        },
    )
    script_projection = structural_request_from_language(script.aggregated)
    assert "javascript_relative_imports_are_not_structural_edges" in script_projection.limitations
    assert all("./local" not in item.target_id for item in script_projection.request.observations)
    script_evidence = normalize_structural_edges(script_projection.request)
    assert script_evidence.admitted
    script_body = evaluate_architecture_launch(script_evidence)
    assert _status(script_body, "architecture.framework-leakage") == "pass"

    python = service.collect(
        repository_id="fixture",
        relative_paths=(
            "src/demo/domain/model.py",
            "src/demo/application/service.py",
        ),
        file_texts={
            "src/demo/domain/model.py": "class Entity:\n    pass\n",
            "src/demo/application/service.py": "from demo.domain.model import Entity\n",
        },
    )
    python_projection = structural_request_from_language(python.aggregated)
    python_evidence = normalize_structural_edges(python_projection.request)
    assert python_evidence.admitted
    assert "lower_tier:python" in python_projection.limitations
    python_body = evaluate_architecture_launch(python_evidence)
    assert _status(python_body, "architecture.framework-leakage") == "unknown"

    php = service.collect(
        repository_id="fixture",
        relative_paths=("app/domain/Model.php", "app/persistence/Store.php"),
        file_texts={
            "app/domain/Model.php": (
                "<?php\nnamespace App\\Domain;\nuse App\\Persistence\\Store;\nclass Model {}\n"
            ),
            "app/persistence/Store.php": "<?php\nnamespace App\\Persistence;\nclass Store {}\n",
        },
    )
    php_projection = structural_request_from_language(php.aggregated)
    php_evidence = normalize_structural_edges(php_projection.request)
    assert php_evidence.admitted
    assert "lower_tier:php" in php_projection.limitations

    csharp = service.collect(
        repository_id="fixture",
        relative_paths=("src/Domain/Order.cs", "src/Persistence/Store.cs"),
        file_texts={
            "src/Domain/Order.cs": (
                "namespace App.Domain;\nusing App.Persistence.Store;\npublic class Order {}\n"
            ),
            "src/Persistence/Store.cs": "namespace App.Persistence;\npublic class Store {}\n",
        },
    )
    csharp_projection = structural_request_from_language(csharp.aggregated)
    csharp_evidence = normalize_structural_edges(csharp_projection.request)
    assert csharp_evidence.admitted
    assert "lower_tier:csharp" in csharp_projection.limitations


def _concentration(*components: tuple[str, int], unmapped: bool = False):
    from codestrata.domain.repository_graph.metrics import SourceLineFile

    files = [
        SourceLineFile(
            relative_path=f"src/{name}.py",
            component_id=name,
            source_text="\n".join("code" for _ in range(lines)),
        )
        for name, lines in components
    ]
    if unmapped:
        files.append(
            SourceLineFile(
                relative_path="src/loose.py",
                component_id="",
                source_text="code\n",
            )
        )
    return evaluate_architecture_launch(
        normalize_structural_edges(StructuralNormalizationRequest(source_files=tuple(files)))
    )
