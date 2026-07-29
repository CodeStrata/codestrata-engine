"""Phase 4.1.1 compatibility: legacy RuleEngine vs adapter facade."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.legacy_adapter import LegacyRuleAdapter
from codestrata.domain.findings import Finding
from codestrata.domain.rules.identifiers import RuleId, validate_rule_id
from codestrata.models import Repository
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.recommendations import RecommendationEngine
from codestrata.services.rule_engine import RuleEngine, rule_context_from_pipeline
from codestrata.services.rule_engine.rules.builtin import (
    MissingLicenseRule,
    MissingReadmeRule,
    MissingTestsRule,
    NpmLockfileMissingRule,
    builtin_rules,
)


def _write_js(root: Path, *, readme: bool = False, license: bool = False) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "js-app",
                "version": "1.0.0",
                "engines": {"node": ">=18"},
                "dependencies": {"express": "^4.0.0"},
            }
        ),
        encoding="utf-8",
    )
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
    files = ["package.json", "src/index.js"]
    if readme:
        (root / "README.md").write_text("# app\n", encoding="utf-8")
        files.append("README.md")
    if license:
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        files.append("LICENSE")
    return Repository(name="js-app", path=root.resolve(), files=files, total_files=len(files))


def _assert_findings_equal(left: tuple[Finding, ...], right: tuple[Finding, ...]) -> None:
    assert len(left) == len(right)
    for a, b in zip(left, right, strict=True):
        assert a.id == b.id
        assert a.rule_id == b.rule_id
        assert a.severity == b.severity
        assert a.title == b.title
        assert a.description == b.description
        assert a.category == b.category
        assert a.evidence == b.evidence
        assert a.affected_assessment_node_ids == b.affected_assessment_node_ids
        assert a.metadata == b.metadata
        assert a == b


def test_legacy_rule_ids_accepted_for_adapters() -> None:
    assert str(RuleId("codestrata-rule-missing-readme")) == "codestrata-rule-missing-readme"
    validate_rule_id("architecture.layer-dependency")


def test_single_rule_engine_vs_adapter(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    rules = (MissingReadmeRule(), MissingLicenseRule(), MissingTestsRule())

    engine = RuleEngine(rules=rules)
    via_engine = engine.evaluate(context)

    facade = RuleExecutionFacade()
    via_adapter = facade.evaluate_adapted(context, rules=rules)

    _assert_findings_equal(via_engine.findings, via_adapter.findings)
    assert via_engine.rules_evaluated == via_adapter.rules_evaluated
    assert via_engine.rules_skipped == via_adapter.rules_skipped
    assert via_engine.finding_count == via_adapter.finding_count


def test_facade_evaluate_matches_rule_engine(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    rules = builtin_rules()
    engine = RuleEngine(rules=rules)
    facade = RuleExecutionFacade(legacy_engine=RuleEngine(rules=rules))

    left = engine.evaluate(context)
    right = facade.evaluate(context)
    _assert_findings_equal(left.findings, right.findings)


def test_adapted_full_builtin_set(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    rules = builtin_rules()

    via_engine = RuleEngine(rules=rules).evaluate(context)
    via_adapter = RuleExecutionFacade().evaluate_adapted(context, rules=rules)

    _assert_findings_equal(via_engine.findings, via_adapter.findings)
    assert [item.id for item in via_engine.findings] == [
        item.id for item in via_adapter.findings
    ]


def test_recommendations_unchanged_through_adapter(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    pipeline = GraphAssessmentPipeline().run(repository)
    context = rule_context_from_pipeline(pipeline)
    rules = (
        MissingReadmeRule(),
        MissingLicenseRule(),
        NpmLockfileMissingRule(),
    )

    engine_eval = RuleEngine(rules=rules).evaluate(context)
    adapted_eval = RuleExecutionFacade().evaluate_adapted(context, rules=rules)
    _assert_findings_equal(engine_eval.findings, adapted_eval.findings)

    recommendations = RecommendationEngine()
    from_engine = recommendations.evaluate_from_rule_result(
        rule_context=context,
        evaluation=engine_eval,
    )
    from_adapted = recommendations.evaluate_from_rule_result(
        rule_context=context,
        evaluation=adapted_eval,
    )
    assert [item.id for item in from_engine.recommendations] == [
        item.id for item in from_adapted.recommendations
    ]
    assert from_engine.recommendations == from_adapted.recommendations


def test_legacy_adapter_passthrough_findings(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app", readme=False)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    rule = MissingReadmeRule()
    direct = rule.evaluate(context)
    adapter = LegacyRuleAdapter(rule)
    adapted = adapter.evaluate_legacy(context)
    assert direct.findings == adapted.findings
    assert adapter.last_findings == direct.findings


def test_shared_context_carries_legacy_rule_context(tmp_path: Path) -> None:
    repository = _write_js(tmp_path / "app")
    legacy = rule_context_from_pipeline(GraphAssessmentPipeline().run(repository))
    shared = rule_execution_context_from_legacy(legacy)
    assert shared.legacy_rule_context is legacy
    adapter = LegacyRuleAdapter(MissingReadmeRule())
    result = adapter.evaluate(shared)
    assert result.status.value in {"matched", "not_matched"}
