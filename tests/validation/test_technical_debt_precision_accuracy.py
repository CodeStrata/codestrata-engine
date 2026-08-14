"""Slice 4.6 — Technical Debt precision expectation model, metrics, and fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from codestrata.application.rules.technical_debt.helpers import is_production_complexity_subject
from codestrata.application.rules.technical_debt.rules import LargeCallableRule
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.complexity.enums import ComplexityCallableKind
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    CallableComplexityEvidence,
    IntMetric,
    SourceSpan,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus
from validation.actual import load_emitted_assessment, run_real_assessment
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary
from validation.technical_debt import (
    TechnicalDebtExpectation,
    TechnicalDebtFindingActual,
    TechnicalDebtFindingExpectation,
    TechnicalDebtScope,
    aggregate_technical_debt_results,
    extract_technical_debt_findings,
    validate_technical_debt_precision,
)


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="language.python.complexity",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="fixture",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path="demo.py",
    )


def _callable(
    *,
    name: str,
    path: str,
    lines: int,
    classification: SourceClassification = SourceClassification.SOURCE,
) -> CallableComplexityEvidence:
    return CallableComplexityEvidence(
        evidence_id=f"c:{path}:{name}",
        language="python",
        path=path,
        name=name,
        qualified_signature=f"{name}#0@1",
        callable_kind=ComplexityCallableKind.FUNCTION,
        owner_qualified_name=None,
        classification=classification,
        span=SourceSpan(path=path, line_start=1, line_end=max(1, lines)),
        physical_line_count=IntMetric.available(lines),
        parameter_count=IntMetric.available(0),
        branch_point_count=IntMetric.available(0),
        max_nesting_depth=IntMetric.available(0),
        provenance=_prov(),
    )


def test_contradictory_technical_debt_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        TechnicalDebtExpectation(
            expected_rule_ids=("technical_debt.large-callable",),
            forbidden_rule_ids=("technical_debt.large-callable",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            technical_debt=TechnicalDebtExpectation(
                required_findings=(
                    TechnicalDebtFindingExpectation(rule_id="technical_debt.deep-nesting"),
                ),
                forbidden_rule_ids=("technical_debt.deep-nesting",),
            )
        )


def test_classify_tp_fp_fn_and_metrics() -> None:
    expectation = TechnicalDebtExpectation(
        required_findings=(
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.large-callable",
                measured_value=60,
                threshold=50,
                threshold_operator="gt",
            ),
            TechnicalDebtFindingExpectation(rule_id="technical_debt.deep-nesting"),
        ),
        forbidden_rule_ids=("technical_debt.excessive-branching",),
        forbidden_conclusions=("rewrite required",),
    )
    actual = (
        TechnicalDebtFindingActual(
            rule_id="technical_debt.large-callable",
            path="src/production/above_threshold.py",
            symbol="large_above#0@1",
            measured_value=60,
            threshold=50,
            threshold_operator="gt",
            evidence_ids=("e1",),
        ),
        TechnicalDebtFindingActual(
            rule_id="technical_debt.excessive-branching",
            path="src/production/above_threshold.py",
            measured_value=12,
            threshold=10,
            threshold_operator="gt",
            evidence_ids=("e2",),
        ),
    )
    result = validate_technical_debt_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual,
        artifact_texts={"report.json": "safe disclaimer only"},
    )
    by_rule = {item.rule_id: item.classification for item in result.classifications}
    assert by_rule["technical_debt.large-callable"] is FactClassification.TRUE_POSITIVE
    assert by_rule["technical_debt.deep-nesting"] is FactClassification.FALSE_NEGATIVE
    assert by_rule["technical_debt.excessive-branching"] is FactClassification.FALSE_POSITIVE
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0, false_positives=0, false_negatives=0
    )
    assert precision is None and recall is None and reason is not None


def test_aggregate_deterministic_order() -> None:
    expectation = TechnicalDebtExpectation(
        required_findings=(
            TechnicalDebtFindingExpectation(rule_id="technical_debt.large-callable"),
        )
    )
    actual = (
        TechnicalDebtFindingActual(
            rule_id="technical_debt.large-callable",
            path="a.py",
            measured_value=60,
            threshold=50,
            threshold_operator="gt",
            evidence_ids=("e1",),
        ),
    )
    a = validate_technical_debt_precision(
        repository_id="repo-a", expectation=expectation, actual_findings=actual
    )
    b = validate_technical_debt_precision(
        repository_id="repo-b", expectation=expectation, actual_findings=actual
    )
    aggregate = aggregate_technical_debt_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == ["repo-b", "repo-a"]
    assert aggregate.precision == 1.0


def test_all_repositories_have_technical_debt_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.technical_debt is not None, definition.repository_id
        assert expected.technical_debt.evidence_notes, definition.repository_id


def test_production_filter_skips_test_callables() -> None:
    assert is_production_complexity_subject(SourceClassification.SOURCE)
    assert not is_production_complexity_subject(SourceClassification.TEST)
    evidence = AggregatedComplexityEvidence(
        repository_id="fixture",
        callables=(
            _callable(name="prod", path="src/app.py", lines=80),
            _callable(
                name="test_fn",
                path="tests/test_app.py",
                lines=80,
                classification=SourceClassification.TEST,
            ),
        ),
        types=(),
        contributing_provider_ids=("language.python.complexity",),
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        complexity_evidence=evidence,
    )
    result = LargeCallableRule(max_physical_lines=50).evaluate(context)
    assert result.status is RuleResultStatus.MATCHED
    assert len(result.matches) == 1
    assert "prod" in result.matches[0].summary


def test_threshold_boundaries_equal_does_not_match() -> None:
    evidence = AggregatedComplexityEvidence(
        repository_id="fixture",
        callables=(
            _callable(name="equal", path="src/a.py", lines=50),
            _callable(name="above", path="src/b.py", lines=51),
        ),
        types=(),
        contributing_provider_ids=("language.python.complexity",),
    )
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        complexity_evidence=evidence,
    )
    result = LargeCallableRule(max_physical_lines=50).evaluate(context)
    assert len(result.matches) == 1
    assert "above" in result.matches[0].summary


def test_controlled_complexity_fixture_precision(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "complexity-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-complexity-signals.toml"
    actual, _ = run_real_assessment(
        repository_path=fixture,
        output_directory=tmp_path / "out",
        config_path=config,
    )
    rule_ids = {item.rule_id for item in actual.technical_debt_findings}
    assert "technical_debt.large-callable" in rule_ids
    assert "technical_debt.excessive-branching" in rule_ids
    assert "technical_debt.deep-nesting" in rule_ids
    assert "technical_debt.excessive-parameters" in rule_ids
    assert "technical_debt.oversized-type" in rule_ids
    assert not any(
        item.path and "/tests/" in item.path.replace("\\", "/")
        for item in actual.technical_debt_findings
    )

    expectation = TechnicalDebtExpectation(
        required_findings=(
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.large-callable",
                path_pattern="above_threshold",
                symbol_pattern="large_above",
                measured_value=60,
                threshold=50,
                threshold_operator="gt",
                scope=TechnicalDebtScope.CALLABLE,
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.excessive-branching",
                path_pattern="above_threshold",
                symbol_pattern="branch_above",
                measured_value=12,
                threshold=10,
                threshold_operator="gt",
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.deep-nesting",
                path_pattern="above_threshold",
                symbol_pattern="nest_above",
                measured_value=6,
                threshold=4,
                threshold_operator="gt",
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.excessive-parameters",
                path_pattern="above_threshold",
                symbol_pattern="params_above",
                measured_value=8,
                threshold=5,
                threshold_operator="gt",
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.oversized-type",
                path_pattern="oversized_type",
                symbol_pattern="OversizedType",
                measured_value=350,
                threshold=300,
                threshold_operator="gt",
                scope=TechnicalDebtScope.TYPE,
            ),
        ),
        forbidden_findings=(
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.large-callable",
                path_pattern="below_threshold",
                rationale="below-threshold callable must not match",
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.large-callable",
                path_pattern="equal_threshold",
                rationale="equal-to-threshold must not match under GT",
            ),
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.large-callable",
                path_pattern="tests/",
                rationale="test-only complexity excluded",
            ),
        ),
        allowed_findings=(
            TechnicalDebtFindingExpectation(
                rule_id="technical_debt.oversized-type",
                symbol_pattern="production.oversized_type",
                rationale="Module-level oversized record may accompany the type finding",
            ),
        ),
        maximum_false_positive_count=0,
        evidence_notes="Controlled complexity-signals fixture",
    )
    result = validate_technical_debt_precision(
        repository_id="complexity-signals",
        expectation=expectation,
        actual_findings=actual.technical_debt_findings,
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.context_failures == ()
    assert result.passed

    for item in actual.technical_debt_findings:
        assert item.finding_id
        assert item.measured_value is not None
        assert item.threshold is not None
        assert item.evidence_ids
        assert item.path is None or not item.path.startswith("/")


def test_negative_control_repositories_technical_debt(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-cloud-signals",
            "local-security-hygiene",
            "local-ai-readiness",
        }
    ]
    output_root = tmp_path_factory.mktemp("td-neg")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0
    assert summary.errors == 0

    td_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS
        expected = resolve_expected_results(definition)
        assert expected.technical_debt is not None
        report, document = load_emitted_assessment(run.artifact_dir)
        findings = extract_technical_debt_findings(
            (document.get("assessment") or {}).get("findings") or []
        )
        for forbidden in expected.technical_debt.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        result = validate_technical_debt_precision(
            repository_id=definition.repository_id,
            expectation=expected.technical_debt,
            actual_findings=findings,
            artifact_texts={report.name: json.dumps(document)},
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed
        td_results.append(result)
    aggregate = aggregate_technical_debt_results(td_results)
    assert aggregate.false_positives == 0


def test_complexity_fixture_repeat_run_determinism(tmp_path: Path) -> None:
    fixture = (VALIDATION_ROOT / "fixtures" / "complexity-signals").resolve()
    config = VALIDATION_ROOT / "configs" / "local-complexity-signals.toml"
    first, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "a", config_path=config
    )
    second, _ = run_real_assessment(
        repository_path=fixture, output_directory=tmp_path / "b", config_path=config
    )
    assert sorted(item.finding_id or "" for item in first.technical_debt_findings) == sorted(
        item.finding_id or "" for item in second.technical_debt_findings
    )
