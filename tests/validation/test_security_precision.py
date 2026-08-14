"""Slice 4.4 — Security precision expectation model, metrics, and fixture accuracy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from validation.actual import load_emitted_assessment, run_real_assessment
from validation.inventory import FactClassification, compute_precision_recall
from validation.models import ExpectedResults, ValidationVerdict
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.security import (
    SecurityExpectation,
    SecurityFindingActual,
    SecurityFindingExpectation,
    aggregate_security_results,
    extract_security_findings,
    validate_security_precision,
)
from validation.summary import build_validation_summary


def test_contradictory_security_expectations_rejected() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        SecurityExpectation(
            expected_rule_ids=("security.credential-literal",),
            forbidden_rule_ids=("security.credential-literal",),
        )
    with pytest.raises(ValidationError, match="contradictory"):
        ExpectedResults(
            security=SecurityExpectation(
                required_findings=(
                    SecurityFindingExpectation(rule_id="security.debug-enabled"),
                ),
                forbidden_rule_ids=("security.debug-enabled",),
            )
        )


def test_classify_tp_fp_fn_ambiguous_and_metrics() -> None:
    expectation = SecurityExpectation(
        required_findings=(
            SecurityFindingExpectation(
                rule_id="security.private-key-material",
                path="secrets/test-only.pem",
            ),
            SecurityFindingExpectation(
                rule_id="security.credential-literal",
                path="config/app.properties",
            ),
        ),
        forbidden_rule_ids=("security.authentication-disabled",),
        allowed_findings=(
            SecurityFindingExpectation(rule_id="SEC002", path="secrets/test-only.pem"),
        ),
        not_applicable_rule_ids=("security.tls-verification-disabled",),
        forbidden_raw_values=("RAW_SECRET_VALUE",),
    )
    actual = (
        SecurityFindingActual(
            rule_id="security.private-key-material",
            path="secrets/test-only.pem",
            severity="high",
            evidence_ids=("e1",),
        ),
        SecurityFindingActual(
            rule_id="security.authentication-disabled",
            path="config/bad.properties",
            severity="high",
            evidence_ids=("e2",),
        ),
        SecurityFindingActual(
            rule_id="SEC002",
            path="secrets/test-only.pem",
            severity="critical",
            evidence_ids=("e3",),
        ),
    )
    result = validate_security_precision(
        repository_id="fixture",
        expectation=expectation,
        actual_findings=actual,
        artifact_texts={"report.json": "safe output only"},
    )
    by_rule = {item.rule_id: item.classification for item in result.classifications}
    assert by_rule["security.private-key-material"] is FactClassification.TRUE_POSITIVE
    assert by_rule["security.credential-literal"] is FactClassification.FALSE_NEGATIVE
    assert by_rule["security.authentication-disabled"] is FactClassification.FALSE_POSITIVE
    assert by_rule["SEC002"] is FactClassification.AMBIGUOUS
    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.false_negatives == 1
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.passed is False


def test_precision_recall_zero_denominator_unavailable() -> None:
    precision, recall, reason = compute_precision_recall(
        true_positives=0,
        false_positives=0,
        false_negatives=0,
    )
    assert precision is None
    assert recall is None
    assert reason is not None
    assert "unavailable" in reason


def test_aggregate_security_metrics_deterministic_order() -> None:
    expectation = SecurityExpectation(
        required_findings=(
            SecurityFindingExpectation(rule_id="security.debug-enabled"),
        ),
        maximum_false_positive_count=0,
    )
    actual = (
        SecurityFindingActual(
            rule_id="security.debug-enabled",
            path="config/app.properties",
            evidence_ids=("e1",),
        ),
    )
    a = validate_security_precision(
        repository_id="repo-a",
        expectation=expectation,
        actual_findings=actual,
    )
    b = validate_security_precision(
        repository_id="repo-b",
        expectation=expectation,
        actual_findings=actual,
    )
    aggregate = aggregate_security_results((b, a))
    assert [item.repository_id for item in aggregate.per_repository] == ["repo-b", "repo-a"]
    assert [item.rule_id for item in aggregate.per_rule] == ["security.debug-enabled"]
    assert aggregate.precision == 1.0
    assert aggregate.recall == 1.0


def test_all_repositories_have_security_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        assert expected.security is not None, definition.repository_id
        assert expected.security.evidence_notes, definition.repository_id


def test_controlled_security_fixture_precision(tmp_path: Path) -> None:
    definition = next(
        item
        for item in load_all_repositories()
        if item.repository_id == "local-security-hygiene"
    )
    expected = resolve_expected_results(definition)
    assert expected.security is not None
    actual, report = run_real_assessment(
        repository_path=Path("validation/fixtures/security-hygiene").resolve(),
        output_directory=tmp_path / "out",
    )
    artifact_texts = {
        name: Path(path).read_text(encoding="utf-8", errors="replace")
        for name, path in actual.artifact_paths.items()
        if path and Path(path).is_file()
    }
    result = validate_security_precision(
        repository_id=definition.repository_id,
        expectation=expected.security,
        actual_findings=actual.security_findings,
        artifact_texts=artifact_texts,
    )
    assert result.false_positives == 0, result.diagnostics
    assert result.false_negatives == 0, result.diagnostics
    assert result.redaction_failures == ()
    assert result.production_context_errors == ()
    assert result.passed
    assert result.precision == 1.0
    assert result.recall == 1.0

    rule_ids = {item.rule_id for item in actual.security_findings}
    assert "security.private-key-material" in rule_ids
    assert "security.credential-literal" in rule_ids
    assert "security.placeholder-credential" in rule_ids
    assert "security.debug-enabled" in rule_ids
    assert not any(
        item.rule_id == "security.credential-literal"
        and item.path
        and ".github/workflows/" in item.path
        for item in actual.security_findings
    )

    for raw in expected.security.forbidden_raw_values:
        report_text = report.read_text(encoding="utf-8")
        assert raw not in report_text
        for text in artifact_texts.values():
            assert raw not in text

    for item in actual.security_findings:
        if item.rule_id.startswith("security."):
            assert item.finding_id
            assert item.path and not item.path.startswith("/")
            if item.rule_id != "SEC002":
                assert item.evidence_ids


def test_negative_control_repositories_security_precision(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-cloud-signals",
            "local-ai-readiness",
        }
    ]
    output_root = tmp_path_factory.mktemp("security-neg")
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
    assert summary.passed == len(definitions)

    security_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS
        expected = resolve_expected_results(definition)
        assert expected.security is not None
        report, document = load_emitted_assessment(run.artifact_dir)
        findings = extract_security_findings(
            (document.get("assessment") or {}).get("findings") or []
        )
        for forbidden in expected.security.forbidden_rule_ids:
            assert forbidden not in {item.rule_id for item in findings}
        # No unsupported CVE / vulnerability finding families.
        for item in findings:
            assert "cve" not in item.rule_id.lower()
            assert "vuln" not in item.rule_id.lower()
        result = validate_security_precision(
            repository_id=definition.repository_id,
            expectation=expected.security,
            actual_findings=findings,
            artifact_texts={report.name: json.dumps(document)},
        )
        assert result.false_positives == 0, result.diagnostics
        assert result.passed
        security_results.append(result)

    aggregate = aggregate_security_results(security_results)
    assert aggregate.false_positives == 0


def test_security_fixture_repeat_run_determinism(tmp_path: Path) -> None:
    repo = Path("validation/fixtures/security-hygiene").resolve()
    first, _ = run_real_assessment(repository_path=repo, output_directory=tmp_path / "a")
    second, _ = run_real_assessment(repository_path=repo, output_directory=tmp_path / "b")
    assert {item.rule_id for item in first.security_findings} == {
        item.rule_id for item in second.security_findings
    }
    assert sorted(item.finding_id or "" for item in first.security_findings) == sorted(
        item.finding_id or "" for item in second.security_findings
    )
