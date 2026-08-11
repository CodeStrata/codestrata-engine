"""Architecture Intelligence pack tests (Phase 4.2.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.architecture.assessment import (
    architecture_pack_enabled,
    merge_rule_evaluations,
)
from codestrata.application.rules.architecture.helpers import enrich_finding_metadata
from codestrata.application.rules.architecture.pack import ArchitectureRulePack, architecture_rules
from codestrata.application.rules.architecture.registration import register_architecture_pack
from codestrata.application.rules.architecture.view_builder import (
    build_architecture_analysis_view,
    find_directed_cycles,
)
from codestrata.application.rules.facade import RuleExecutionFacade
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.suppression_service import RuleSuppressionService
from codestrata.config.settings import (
    CodestrataSettings,
    ComponentConcentrationRuleSettings,
    ExcessiveCouplingRuleSettings,
    RepositorySettings,
    load_settings,
)
from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.architecture.ids import (
    PACK_ID,
    PACK_VERSION,
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.enums import (
    RuleCategory,
    MatchEvidenceConfidence,
    RuleResultStatus,
    RuleSkipReason,
    RuleSuppressionSource,
)


def _view_from_texts(texts: dict[str, str]):
    return build_architecture_analysis_view(
        relative_paths=sorted(texts),
        file_texts=texts,
    )


def _context_with_view(view, *, enterprise_context=None) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo:demo"),
        languages=LanguageInventoryView(languages=("java", "python")),
        architecture_view=view,
        enterprise_context=enterprise_context,
        policy=RuleExecutionPolicy(),
        provenance={"source": "test"},
    )


def _cycle_fixture() -> dict[str, str]:
    return {
        "src/com/example/domain/A.java": (
            "package com.example.domain;\n"
            "import com.example.application.B;\n"
            "public class A {}\n"
        ),
        "src/com/example/application/B.java": (
            "package com.example.application;\n"
            "import com.example.domain.A;\n"
            "public class B {}\n"
        ),
    }


def test_pack_metadata_and_ids() -> None:
    pack = ArchitectureRulePack()
    assert pack.pack_id == PACK_ID == "architecture.core"
    assert pack.pack_version == PACK_VERSION == "1.0.0"
    assert pack.default_enabled is False
    assert RULE_DEPENDENCY_CYCLE in pack.included_rule_ids
    assert "architecture.service-dependency-cycle" in pack.deferred_rule_ids


def test_registry_registration_and_discovery() -> None:
    registry = RuleRegistry()
    register_architecture_pack(registry)
    views = registry.list_rules(category=RuleCategory.ARCHITECTURE)
    assert len(views) == 7
    service = create_rule_analysis_service()
    listed = service.list_rules(category=RuleCategory.ARCHITECTURE)
    assert {str(view.metadata.rule_id) for view in listed} >= {
        RULE_DEPENDENCY_CYCLE,
        RULE_FRAMEWORK_LEAKAGE,
        RULE_ENTERPRISE_STANDARD_MISMATCH,
    }


def test_rule_metadata_taxonomy_and_dimensions() -> None:
    rules = {str(rule.metadata.rule_id): rule for rule in architecture_rules()}
    meta = rules[RULE_DEPENDENCY_CYCLE].metadata
    assert meta.category is RuleCategory.ARCHITECTURE
    assert any(tag.startswith("taxonomy:") for tag in meta.tags)
    assert any(tag.startswith("dimension:") for tag in meta.tags)
    assert meta.version.major == 1
    enriched = enrich_finding_metadata(RULE_DEPENDENCY_CYCLE)
    assert enriched["taxonomy_id"] == "architecture.dependency-structure"
    assert enriched["business_impact"] == "unknown"
    assert "executive_concern" in enriched


def test_cycle_canonicalization_and_deterministic_ids() -> None:
    adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = find_directed_cycles(adjacency)
    assert len(cycles) == 1
    assert cycles[0][0] == "a"
    # Different start order yields same canonical cycle
    assert find_directed_cycles({"b": ["c"], "c": ["a"], "a": ["b"]}) == cycles

    view = _view_from_texts(_cycle_fixture())
    rule = {str(r.metadata.rule_id): r for r in architecture_rules()}[RULE_DEPENDENCY_CYCLE]
    context = _context_with_view(view)
    first = rule.evaluate(context)
    second = rule.evaluate(context)
    assert first.status is RuleResultStatus.MATCHED
    assert second.status is RuleResultStatus.MATCHED
    mapper = RuleFindingMapper()
    findings_a = mapper.map_matches(
        first.matches, category_by_rule={RULE_DEPENDENCY_CYCLE: RuleCategory.ARCHITECTURE}
    )
    findings_b = mapper.map_matches(
        second.matches, category_by_rule={RULE_DEPENDENCY_CYCLE: RuleCategory.ARCHITECTURE}
    )
    assert [item.id for item in findings_a] == [item.id for item in findings_b]


def test_cycle_self_loop_and_duplicate_edges() -> None:
    cycles = find_directed_cycles({"a": ["a", "a"], "b": []})
    assert cycles == (("a", "a"),)
    multi = find_directed_cycles(
        {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"]},
    )
    assert len(multi) == 2


def test_parent_child_package_cycles_are_ignored() -> None:
    cycles = find_directed_cycles(
        {
            "codestrata.application.rules": ["codestrata.application.rules.architecture"],
            "codestrata.application.rules.architecture": ["codestrata.application.rules"],
            "a": ["b"],
            "b": ["a"],
        }
    )
    assert cycles == (("a", "b", "a"),)


def test_invalid_direction_and_boundary() -> None:
    texts = {
        "src/main/java/com/example/domain/Core.java": (
            "package com.example.domain;\n"
            "import com.example.infrastructure.Adapter;\n"
            "public class Core {}\n"
        ),
        "src/main/java/com/example/infrastructure/Adapter.java": (
            "package com.example.infrastructure;\n"
            "public class Adapter {}\n"
        ),
        "src/main/java/com/example/controller/Ui.java": (
            "package com.example.controller;\n"
            "import com.example.persistence.Repo;\n"
            "public class Ui {}\n"
        ),
        "src/main/java/com/example/persistence/Repo.java": (
            "package com.example.persistence;\n"
            "public class Repo {}\n"
        ),
    }
    view = _view_from_texts(texts)
    context = _context_with_view(view)
    rules = {str(r.metadata.rule_id): r for r in architecture_rules()}
    direction = rules[RULE_INVALID_DEPENDENCY_DIRECTION].evaluate(context)
    boundary = rules[RULE_LAYER_BOUNDARY_VIOLATION].evaluate(context)
    assert direction.status is RuleResultStatus.MATCHED
    assert boundary.status is RuleResultStatus.MATCHED


def test_layer_rules_not_applicable_without_classification() -> None:
    texts = {
        "src/util/One.java": "package util;\nimport util.Two;\npublic class One {}\n",
        "src/util/Two.java": "package util;\npublic class Two {}\n",
    }
    view = _view_from_texts(texts)
    context = _context_with_view(view)
    rules = {str(r.metadata.rule_id): r for r in architecture_rules()}
    applicability = rules[RULE_INVALID_DEPENDENCY_DIRECTION].evaluate_applicability(context)
    assert not applicability.is_applicable


def test_coupling_thresholds() -> None:
    texts: dict[str, str] = {}
    imports = "\n".join(f"import com.example.leaf{i}.L{i};" for i in range(10))
    texts["src/main/java/com/example/hub/Hub.java"] = (
        f"package com.example.hub;\n{imports}\npublic class Hub {{}}\n"
    )
    for index in range(10):
        texts[f"src/main/java/com/example/leaf{index}/L{index}.java"] = (
            f"package com.example.leaf{index};\npublic class L{index} {{}}\n"
        )
    view = _view_from_texts(texts)
    context = _context_with_view(view)
    by_id = {str(rule.metadata.rule_id): rule for rule in architecture_rules(
        outgoing_module_threshold=20,
        minimum_module_count=5,
    )}
    assert by_id[RULE_EXCESSIVE_CROSS_MODULE_COUPLING].evaluate(context).status is (
        RuleResultStatus.NOT_MATCHED
    )
    equal = {
        str(rule.metadata.rule_id): rule
        for rule in architecture_rules(outgoing_module_threshold=10, minimum_module_count=5)
    }[RULE_EXCESSIVE_CROSS_MODULE_COUPLING]
    assert equal.evaluate(context).status is RuleResultStatus.MATCHED
    tiny = {
        str(rule.metadata.rule_id): rule
        for rule in architecture_rules(outgoing_module_threshold=2, minimum_module_count=50)
    }[RULE_EXCESSIVE_CROSS_MODULE_COUPLING]
    assert not tiny.evaluate_applicability(context).is_applicable


def test_component_concentration() -> None:
    texts = {
        "src/main/java/com/example/core/Core.java": (
            "package com.example.core;\n"
            "import com.example.a.A;\nimport com.example.b.B;\n"
            "public class Core {}\n"
        ),
        "src/main/java/com/example/a/A.java": (
            "package com.example.a;\nimport com.example.core.Core;\npublic class A {}\n"
        ),
        "src/main/java/com/example/b/B.java": (
            "package com.example.b;\nimport com.example.core.Core;\npublic class B {}\n"
        ),
        "src/main/java/com/example/c/C.java": "package com.example.c;\npublic class C {}\n",
        "src/main/java/com/example/d/D.java": "package com.example.d;\npublic class D {}\n",
    }
    view = _view_from_texts(texts)
    context = _context_with_view(view)
    rule = {
        str(item.metadata.rule_id): item
        for item in architecture_rules(
            incident_edge_share_threshold=0.30,
            minimum_component_count=5,
        )
    }[RULE_COMPONENT_CONCENTRATION]
    result = rule.evaluate(context)
    assert result.status is RuleResultStatus.MATCHED


def test_framework_leakage() -> None:
    texts = {
        "src/main/java/com/example/domain/Entity.java": (
            "package com.example.domain;\n"
            "import javax.persistence.Entity;\n"
            "@Entity\n"
            "public class Entity {}\n"
        ),
        "src/main/java/com/example/application/App.java": (
            "package com.example.application;\npublic class App {}\n"
        ),
    }
    view = _view_from_texts(texts)
    assert view.framework_hits
    context = _context_with_view(view)
    rule = {str(r.metadata.rule_id): r for r in architecture_rules()}[RULE_FRAMEWORK_LEAKAGE]
    result = rule.evaluate(context)
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].confidence is MatchEvidenceConfidence.HIGH


def test_enterprise_standard_mismatch() -> None:
    class _Std:
        entity_id = "std:frameworks"
        labels = {"prohibited_frameworks": "jpa,spring-web"}

    class _Enterprise:
        standards = (_Std(),)

    texts = {
        "src/main/java/com/example/domain/Entity.java": (
            "package com.example.domain;\n@Entity\npublic class Entity {}\n"
        ),
        "src/main/java/com/example/application/App.java": (
            "package com.example.application;\npublic class App {}\n"
        ),
    }
    view = _view_from_texts(texts)
    rule = {
        str(r.metadata.rule_id): r for r in architecture_rules()
    }[RULE_ENTERPRISE_STANDARD_MISMATCH]
    without = _context_with_view(view)
    assert rule.evaluate_applicability(without).reason_code is (
        RuleSkipReason.MISSING_ENTERPRISE_CONTEXT
    )
    with_ctx = _context_with_view(view, enterprise_context=_Enterprise())
    result = rule.evaluate(with_ctx)
    assert result.status is RuleResultStatus.MATCHED


def test_suppression_deterministic() -> None:
    view = _view_from_texts(_cycle_fixture())
    rule = {str(r.metadata.rule_id): r for r in architecture_rules()}[RULE_DEPENDENCY_CYCLE]
    result = rule.evaluate(_context_with_view(view))
    match = result.matches[0]
    active = RuleSuppression(
        suppression_id="sup-1",
        rule_id=RULE_DEPENDENCY_CYCLE,
        reason="accepted temporary cycle",
        subject_reference=match.subject_keys[0],
        source=RuleSuppressionSource.MANUAL,
    )
    expired = RuleSuppression(
        suppression_id="sup-2",
        rule_id=RULE_DEPENDENCY_CYCLE,
        reason="expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
        source=RuleSuppressionSource.MANUAL,
    )
    service = RuleSuppressionService((active, expired))
    decision = service.decide(match, repository_id="repo:demo")
    assert decision.suppressed is True
    expired_only = RuleSuppressionService((expired,))
    assert expired_only.decide(match, repository_id="repo:demo").suppressed is False


def test_configuration_validation(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.architecture]
        enabled = true

        [rules.architecture.excessive_cross_module_coupling]
        outgoing_module_threshold = 12
        minimum_module_count = 3

        [rules.architecture.component_concentration]
        incident_edge_share_threshold = 0.25
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.enabled is True
    assert settings.rules.architecture.enabled is True
    coupling = settings.rules.architecture.excessive_cross_module_coupling
    assert coupling.outgoing_module_threshold == 12
    with pytest.raises(ValidationError):
        ExcessiveCouplingRuleSettings(outgoing_module_threshold=0)
    with pytest.raises(ValidationError):
        ComponentConcentrationRuleSettings(incident_edge_share_threshold=1.5)


def test_pack_disabled_by_default() -> None:
    settings = CodestrataSettings(repository=RepositorySettings(path="."))
    assert architecture_pack_enabled(settings) is False
    settings.rules.enabled = True
    assert architecture_pack_enabled(settings) is False
    settings.rules.architecture.enabled = True
    assert architecture_pack_enabled(settings) is True


def test_merge_preserves_legacy_findings() -> None:
    legacy = RuleEvaluationResult.from_findings(
        findings=(
            Finding.create(
                rule_id="codestrata-rule-java-detected",
                title="Java",
                description="Java present",
                severity=FindingSeverity.INFORMATIONAL,
                category=FindingCategory.ARCHITECTURE,
                subject_keys=("java",),
            ),
        ),
        rules_evaluated=("codestrata-rule-java-detected",),
    )
    extra = RuleEvaluationResult.from_findings(
        findings=(
            Finding.create(
                rule_id=RULE_DEPENDENCY_CYCLE,
                title="Cycle",
                description="cycle",
                severity=FindingSeverity.MEDIUM,
                category=FindingCategory.ARCHITECTURE,
                subject_keys=("cycle", "a", "b"),
            ),
        ),
        rules_evaluated=(RULE_DEPENDENCY_CYCLE,),
    )
    merged = merge_rule_evaluations(legacy, extra)
    assert merged.finding_count == 2
    assert "codestrata-rule-java-detected" in merged.rules_evaluated


def test_facade_execute_shared_architecture() -> None:
    registry = RuleRegistry()
    register_architecture_pack(registry)
    facade = RuleExecutionFacade(shared_registry=registry)
    view = _view_from_texts(_cycle_fixture())
    context = _context_with_view(view)
    result = facade.execute_shared(
        context,
        include_rule_ids=(RULE_DEPENDENCY_CYCLE,),
    )
    assert result.telemetry.executed_rules >= 1
    assert result.matches


def test_deterministic_ordering_of_matches() -> None:
    texts = {
        "src/main/java/com/example/a/A.java": (
            "package com.example.a;\nimport com.example.b.B;\npublic class A {}\n"
        ),
        "src/main/java/com/example/b/B.java": (
            "package com.example.b;\nimport com.example.a.A;\npublic class B {}\n"
        ),
        "src/main/java/com/example/c/C.java": (
            "package com.example.c;\nimport com.example.d.D;\npublic class C {}\n"
        ),
        "src/main/java/com/example/d/D.java": (
            "package com.example.d;\nimport com.example.c.C;\npublic class D {}\n"
        ),
    }
    view = _view_from_texts(texts)
    rule = {str(r.metadata.rule_id): r for r in architecture_rules()}[RULE_DEPENDENCY_CYCLE]
    first = [m.summary for m in rule.evaluate(_context_with_view(view)).matches]
    second = [m.summary for m in rule.evaluate(_context_with_view(view)).matches]
    assert first == second
    assert first == sorted(first)


def test_incomplete_coverage_not_applicable() -> None:
    view = build_architecture_analysis_view(
        relative_paths=["src/a/A.java", "src/b/B.java"],
        file_texts={},  # no contents → coverage 0
    )
    context = _context_with_view(view)
    rule = {str(r.metadata.rule_id): r for r in architecture_rules()}[RULE_DEPENDENCY_CYCLE]
    assert not rule.evaluate_applicability(context).is_applicable


def test_serialization_of_pack_dict() -> None:
    payload = ArchitectureRulePack().to_dict()
    assert payload["pack_id"] == "architecture.core"
    assert isinstance(payload["included_rule_ids"], list)
