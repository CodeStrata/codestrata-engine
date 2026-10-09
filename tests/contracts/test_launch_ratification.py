"""E01.1 contract tests: completeness, formulas, identity, budgets, YAML."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from codestrata.domain.contracts.catalog import (
    PACKAGE_REVISION,
    build_launch_ratification,
    docs_yaml_path,
    dump_yaml_bytes,
    packaged_yaml_path,
    sha256_bytes,
)
from codestrata.domain.contracts.enums import (
    ConfidenceContractLevel,
    ContributorRole,
    DepthTier,
    MetricStatus,
)
from codestrata.domain.contracts.evaluate import evaluate_formula_fixture
from codestrata.domain.contracts.identity import LAUNCH_RULE_IDS
from codestrata.domain.contracts.models import MeasurementEntry
from codestrata.domain.rules.architecture.ids import RULE_ENTERPRISE_STANDARD_MISMATCH
from codestrata.domain.rules.identifiers import validate_rule_id

ENGINE_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    ENGINE_ROOT / "schemas" / "contracts" / "codestrata.io" / "v1.2" / "LaunchRatification.json"
)


@pytest.fixture(scope="module")
def ratification():
    return build_launch_ratification()


def test_package_revision_and_no_opaque_score(ratification) -> None:
    assert ratification.package_revision == PACKAGE_REVISION
    assert ratification.no_opaque_score.canonical_health_score is False
    assert all(item.opaque_score is False for item in ratification.measurements)


def test_every_measurement_has_required_fields(ratification) -> None:
    ids = [item.id for item in ratification.measurements]
    assert ids == [f"M{i:02d}" for i in range(1, 34)]
    for item in ratification.measurements:
        assert item.inputs
        assert item.formula
        assert item.subject
        assert item.evidence
        assert item.missing_data
        assert item.fixtures
        assert item.owning_stories


def test_schema_requires_thirty_three_measurements() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["measurements"]["minItems"] == 33
    assert schema["properties"]["measurements"]["maxItems"] == 33
    dumped = json.loads(json.dumps(build_launch_ratification().model_dump(mode="json")))
    for key in schema["required"]:
        assert key in dumped


def test_formula_fixtures_match_independent_expected(ratification) -> None:
    fixtures = {item.id: item for item in ratification.formula_fixtures}
    assert set(fixtures) >= {
        "M06-external-ratio-mixed",
        "M06-duplicate-edges",
        "M06-zero-edges",
        "M09-diamond",
        "M09-self-loop",
        "M12-unknown-denom",
        "M22-tie-break",
        "M25-zero",
        "M29-churn-only",
        "M30-empty-drivers",
        "M33-budget-failure",
    }
    for fixture in ratification.formula_fixtures:
        actual = evaluate_formula_fixture(fixture.id)
        assert actual.status == fixture.expected_status
        if fixture.expected_numerator is not None:
            assert actual.numerator == fixture.expected_numerator
        if fixture.expected_denominator is not None:
            assert actual.denominator == fixture.expected_denominator
        if fixture.expected_serialized is not None:
            assert actual.serialized == fixture.expected_serialized
        if fixture.expected_reason is not None:
            assert actual.reason == fixture.expected_reason
        for key, value in fixture.expected_extra.items():
            assert actual.extra[key] == value


def test_m06_m09_m12_denominators(ratification) -> None:
    text = " ".join(
        item.formula for item in ratification.measurements if item.id in {"M06", "M09", "M12"}
    ).lower()
    assert "same-component edges stay in the denominator" in text
    assert "max(1, |v|-1)" in text
    assert "unknown denominator = unknown" in text


def test_depth_matrix_java_js_deepest_others_retained(ratification) -> None:
    by_lang = {pin.language: pin for pin in ratification.depth_matrix}
    assert by_lang["java"].launch_tier is DepthTier.DEEPEST_TARGET
    assert by_lang["javascript"].launch_tier is DepthTier.DEEPEST_TARGET
    assert by_lang["typescript"].launch_tier is DepthTier.DEEPEST_TARGET
    for language in ("python", "php", "csharp"):
        assert by_lang[language].launch_tier is DepthTier.VERIFIED_RETAINED
    assert "no extractor" in by_lang["javascript"].complexity.lower()


def test_feed_history_budgets(ratification) -> None:
    feed = ratification.feed
    assert feed.provider_id == "osv.dev"
    assert feed.freshness_max_age_days == 7
    assert feed.silent_online_fallback is False
    history = ratification.history
    assert history.window_days == 180
    assert history.max_commits == 1000
    assert history.bugfix_markers_are_proven_defects is False
    budgets = ratification.budgets
    assert budgets.yaml_aliases_enabled is False
    assert budgets.yaml_document_bytes == 1_048_576
    assert budgets.rule_soft_budget_seconds == 5
    assert budgets.rule_hard_deadline_seconds == 15
    assert budgets.cancellation_grace_seconds == 2
    assert budgets.process_enforced_hard_cap is True
    assert budgets.cooperative_callback_only_forbidden is True
    assert budgets.graph_default_impact_depth == 4


def test_m22_m25_m27_m29_roles(ratification) -> None:
    assert ratification.m22_roles.no_hidden_weights is True
    assert ratification.m22_roles.ranking_contributors == ("complexity", "churn")
    assert "ownership" in ratification.m22_roles.context_only_contributors
    m25 = next(item for item in ratification.measurements if item.id == "M25")
    assert "scoped_denominators" in m25.notes
    m27 = next(item for item in ratification.measurements if item.id == "M27")
    assert "supplied_context_untrusted" in m27.notes
    assert ratification.m29_predicate.no_composite_score is True
    assert ratification.m29_predicate.default_role == "context_only"
    assert ratification.m29_predicate.verdict_requires_yaml is True


def test_outcome_driver_manifest_covers_launch_rules(ratification) -> None:
    driver_ids = {item.id for item in ratification.outcome_drivers}
    for rule_id in LAUNCH_RULE_IDS:
        assert rule_id in driver_ids
    empty_behaviors = {item.empty_scope for item in ratification.outcome_drivers}
    assert any("never healthy" in item for item in empty_behaviors)
    hotspot = next(item for item in ratification.outcome_drivers if item.id == "M22.hotspot")
    assert hotspot.contributor_role is ContributorRole.RANKING
    concern = next(item for item in ratification.outcome_drivers if item.id == "M29.change_concern")
    assert concern.contributor_role is ContributorRole.CONTEXT_ONLY


def test_confidence_and_severity_mapping(ratification) -> None:
    mapped = {item.existing_token: item.contract_level for item in ratification.confidence_map}
    assert mapped["high"] is ConfidenceContractLevel.HIGH
    assert mapped["certain"] is ConfidenceContractLevel.HIGH
    assert mapped["moderate"] is ConfidenceContractLevel.MEDIUM
    assert mapped["medium"] is ConfidenceContractLevel.MEDIUM
    assert mapped["limited"] is ConfidenceContractLevel.LOW
    assert mapped["low"] is ConfidenceContractLevel.LOW
    assert mapped["unavailable"] is ConfidenceContractLevel.UNSUPPORTED
    severity = ratification.severity
    assert severity.hidden_rewrite_after_override_forbidden is True
    assert severity.default_and_effective_preserved is True
    assert severity.context_derived_default_must_be_versioned is True


def test_existing_rule_ids_remain_valid(ratification) -> None:
    grammar = ratification.rule_id_grammar
    assert grammar.incompatible_restriction_invented is False
    for rule_id in ratification.retained_existing_rule_ids:
        assert validate_rule_id(rule_id) == rule_id
    assert validate_rule_id(RULE_ENTERPRISE_STANDARD_MISMATCH) == RULE_ENTERPRISE_STANDARD_MISMATCH
    assert validate_rule_id("codestrata-rule-layer-violation") == "codestrata-rule-layer-violation"
    with pytest.raises(ValueError):
        validate_rule_id("Not A Valid Id")


def test_coverage_freshness_reasons(ratification) -> None:
    codes = {item.code for item in ratification.coverage_freshness_reasons}
    assert {
        "feed_missing",
        "feed_stale",
        "git_history_missing",
        "git_history_shallow",
        "unknown_denominator",
        "no_baseline",
    } <= codes
    unknown = next(
        item
        for item in ratification.coverage_freshness_reasons
        if item.code == "unknown_denominator"
    )
    assert unknown.cannot_prove_clean is True


def test_yaml_copies_are_byte_identical(ratification) -> None:
    expected = dump_yaml_bytes(ratification)
    packaged = packaged_yaml_path().read_bytes()
    documented = docs_yaml_path(ENGINE_ROOT).read_bytes()
    assert b"\r" not in packaged
    assert b"\r" not in documented
    assert packaged == expected
    assert documented == expected
    assert sha256_bytes(packaged) == sha256_bytes(documented)
    parsed = yaml.safe_load(packaged)
    assert parsed["feed"]["silent_online_fallback"] is False
    assert parsed["budgets"]["yaml_aliases_enabled"] is False


def test_ratification_yaml_has_no_credentials(ratification) -> None:
    text = dump_yaml_bytes(ratification).decode("utf-8").lower()
    for forbidden in ("password", "secret-key", "begin rsa", "aws_secret"):
        assert forbidden not in text
    assert "tenant" not in text
    assert "workspace_id" not in text


def test_opaque_score_and_incomplete_catalog_rejected() -> None:
    with pytest.raises(ValidationError):
        MeasurementEntry(
            id="M01",
            name="x",
            family="inventory",
            outcome_role="context",
            subject="file",
            inputs=("tree",),
            formula="count",
            formula_version="v1",
            evidence=("path",),
            missing_data="unknown",
            fixtures=("empty",),
            owning_stories=("E05.1",),
            opaque_score=True,
        )
    payload = build_launch_ratification().model_dump()
    payload["measurements"] = payload["measurements"][:-1]
    with pytest.raises(ValidationError):
        type(build_launch_ratification()).model_validate(payload)


def test_unknown_formula_fixture_is_error() -> None:
    with pytest.raises(KeyError):
        evaluate_formula_fixture("M00-does-not-exist")


def test_percentile_and_m29_rank_order() -> None:
    from decimal import Decimal

    from codestrata.domain.contracts.formulas import (
        m29_rank_key,
        nearest_rank_percentile,
    )

    empty = nearest_rank_percentile((), 0.9)
    assert empty.status is MetricStatus.NOT_APPLICABLE
    p90 = nearest_rank_percentile((10, 20, 30, 40, 50, 60, 70, 80, 90, 100), 0.9)
    assert p90.serialized == "90"
    both = m29_rank_key(
        "b",
        high_churn=True,
        high_centrality=True,
        changed_lines=10,
        centrality=Decimal("0.1"),
    )
    ordinary = m29_rank_key(
        "a",
        high_churn=False,
        high_centrality=False,
        changed_lines=999,
        centrality=Decimal("0.9"),
    )
    assert both < ordinary


def test_ratio_never_exceeds_one() -> None:
    from codestrata.domain.contracts.formulas import m12_resolution_coverage

    result = m12_resolution_coverage(("d1",), ("d1", "extra-not-eligible"))
    assert result.serialized == "1.000000"
    assert result.numerator == 1
    assert result.denominator == 1
    assert result.status is MetricStatus.VALUE
