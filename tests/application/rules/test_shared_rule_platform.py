"""Shared Rule Platform core tests (Phase 4.1)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codestrata.application.rules.errors import RuleRegistryError
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.fixtures import fixture_rules
from codestrata.application.rules.harness import RuleTestHarness
from codestrata.application.rules.incremental import rule_invalidation_fingerprint
from codestrata.application.rules.registry import RuleRegistry
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.context import IncrementalChangeView, RuleExecutionPolicy
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleResultStatus,
    RuleSeverity,
    RuleSuppressionSource,
)
from codestrata.domain.rules.identifiers import RuleId, validate_rule_id
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion

ROOT = Path(__file__).resolve().parents[4]  # monorepo root
DOMAIN_RULES = ROOT / "src" / "codestrata" / "domain" / "rules"
APP_RULES = ROOT / "src" / "codestrata" / "application" / "rules"


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_domain_rules_import_boundaries() -> None:
    forbidden = {"typer", "yaml", "sqlite3", "mcp", "fastmcp"}
    for path in DOMAIN_RULES.rglob("*.py"):
        if path.name == "models.py":
            # Legacy assessment RuleContext imports graph packages only.
            continue
        imports = _imports_of(path)
        assert not forbidden.intersection(imports), path


def test_application_rules_import_boundaries() -> None:
    forbidden = {"typer", "mcp", "fastmcp"}
    for path in APP_RULES.rglob("*.py"):
        imports = _imports_of(path)
        assert not forbidden.intersection(imports), path


def test_rule_id_validation() -> None:
    assert str(RuleId("architecture.layer-dependency")) == "architecture.layer-dependency"
    assert str(RuleId("codestrata-rule-missing-readme")) == "codestrata-rule-missing-readme"
    with pytest.raises(ValueError):
        validate_rule_id("Bad_ID")
    with pytest.raises(ValueError):
        validate_rule_id("noscope")


def test_registry_duplicate_and_list() -> None:
    registry = RuleRegistry()
    rules = fixture_rules()
    registry.register_collection(rules, production=False)
    with pytest.raises(RuleRegistryError):
        registry.register(rules[0], production=False)
    views = registry.list_rules(include_non_production=False)
    assert views == ()
    internal = registry.list_rules(include_non_production=True)
    assert len(internal) == 5
    assert [str(item.metadata.rule_id) for item in internal] == sorted(
        str(item.metadata.rule_id) for item in internal
    )


def test_end_to_end_fixture_execution() -> None:
    harness = RuleTestHarness(fixture_rules())  # type: ignore[arg-type]
    context = harness.build_context(repository_id="repo:demo", languages=("java",))
    result = harness.service.execute_rules(context, include_non_production=True)
    statuses = {record.rule_id: record.status for record in result.records}
    assert statuses["fixture.always-match"] is RuleResultStatus.MATCHED
    assert statuses["fixture.never-match"] is RuleResultStatus.NOT_MATCHED
    assert statuses["fixture.not-applicable"] is RuleResultStatus.NOT_APPLICABLE
    assert statuses["fixture.multiple-match"] is RuleResultStatus.MATCHED
    assert statuses["fixture.failure"] is RuleResultStatus.FAILED
    assert result.telemetry.actual_reuse_count == 0
    assert result.telemetry.matches_produced >= 3
    findings = harness.map_findings(result)
    assert all(item.id.startswith("finding:") for item in findings)
    # Deterministic IDs across reruns
    again = harness.service.execute_rules(context, include_non_production=True)
    findings2 = harness.map_findings(again)
    assert [item.id for item in findings] == [item.id for item in findings2]


def test_suppression_preserves_inspectability() -> None:
    suppression = RuleSuppression(
        suppression_id="sup-1",
        rule_id="fixture.always-match",
        repository_id="repo:demo",
        reason="accepted risk",
        source=RuleSuppressionSource.ACCEPTED_RISK,
    )
    harness = RuleTestHarness(fixture_rules(), suppressions=(suppression,))  # type: ignore[arg-type]
    context = harness.build_context(repository_id="repo:demo")
    result = harness.service.execute_rules(
        context,
        include_rule_ids=("fixture.always-match",),
        include_non_production=True,
    )
    assert result.records[0].status is RuleResultStatus.SUPPRESSED
    assert result.suppressed_matches
    assert harness.map_findings(result) == ()


def test_expired_suppression_ignored() -> None:
    suppression = RuleSuppression(
        suppression_id="sup-expired",
        rule_id="fixture.always-match",
        reason="old",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    harness = RuleTestHarness(fixture_rules(), suppressions=(suppression,))  # type: ignore[arg-type]
    result = harness.service.execute_rules(
        harness.build_context(repository_id="repo:demo"),
        include_rule_ids=("fixture.always-match",),
        include_non_production=True,
    )
    assert result.records[0].status is RuleResultStatus.MATCHED


def test_planner_exclude_and_language() -> None:
    harness = RuleTestHarness(fixture_rules())  # type: ignore[arg-type]
    plan = harness.service.plan_rules(
        harness.build_context(repository_id="repo:demo", languages=("python",)),
        exclude_rule_ids=("fixture.failure",),
        include_non_production=True,
    )
    assert "fixture.failure" not in plan.execution_order
    assert plan.reuse_claimed is False


def test_version_change_invalidates_fingerprint() -> None:
    harness = RuleTestHarness()
    context = harness.build_context(repository_id="repo:demo")
    meta = RuleMetadata(
        rule_id="fixture.always-match",
        version=RuleVersion.parse("1.0.0"),
        title="t",
        description="d",
        category=RuleCategory.PLATFORM,
        default_severity=RuleSeverity.LOW,
        confidence=fixture_rules()[0].metadata.confidence,
    )
    fp1 = rule_invalidation_fingerprint(meta, context)
    meta2 = meta.model_copy(update={"version": RuleVersion.parse("1.0.1")})
    fp2 = rule_invalidation_fingerprint(meta2, context)
    assert fp1 != fp2


def test_enterprise_context_optional() -> None:
    harness = RuleTestHarness(fixture_rules())  # type: ignore[arg-type]
    without = harness.service.execute_rules(
        harness.build_context(repository_id="repo:demo"),
        include_rule_ids=("fixture.not-applicable",),
        include_non_production=True,
    )
    assert without.records[0].status is RuleResultStatus.NOT_APPLICABLE
    with_ctx = harness.service.execute_rules(
        harness.build_context(repository_id="repo:demo", enterprise_context={"ok": True}),
        include_rule_ids=("fixture.not-applicable",),
        include_non_production=True,
    )
    assert with_ctx.records[0].status is RuleResultStatus.NOT_MATCHED


def test_production_service_hides_fixtures() -> None:
    service = create_rule_analysis_service(include_fixture_rules=True)
    production = service.list_rules(include_non_production=False)
    assert production
    assert all(not str(view.metadata.rule_id).startswith("fixture.") for view in production)
    all_rules = service.list_rules(include_non_production=True)
    assert any(str(view.metadata.rule_id).startswith("fixture.") for view in all_rules)


def test_fail_on_rule_error_policy() -> None:
    from codestrata.application.rules.errors import RuleExecutionError

    harness = RuleTestHarness(
        fixture_rules(),  # type: ignore[arg-type]
        policy=RuleExecutionPolicy(fail_on_rule_error=True),
    )
    with pytest.raises(RuleExecutionError):
        harness.service.execute_rules(
            harness.build_context(repository_id="repo:demo"),
            include_rule_ids=("fixture.failure",),
            include_non_production=True,
        )


def test_incremental_view_conservative() -> None:
    harness = RuleTestHarness(fixture_rules())  # type: ignore[arg-type]
    context = harness.build_context(
        repository_id="repo:demo",
        incremental=IncrementalChangeView(force_full_execution=False, changed_paths=("a.py",)),
    )
    plan = harness.service.plan_rules(context, include_non_production=True)
    assert plan.full_execution_fallback_reason is not None
