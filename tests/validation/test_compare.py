"""Unit tests for validation comparison helpers."""

from __future__ import annotations

from pathlib import Path

from validation.compare import (
    compare_actual_to_expected,
    exact_set_match,
    forbidden_present,
    normalize_repo_relative_path,
    ordered_equal,
    required_subset,
    safe_artifact_path,
)
from validation.models import ActualAssessmentResult, CountRange, ExpectedResults


def test_exact_subset_forbidden_and_ranges() -> None:
    assert exact_set_match({"a", "b"}, {"b", "a"})
    assert required_subset({"a", "b"}, {"a", "b", "c"}) == set()
    assert required_subset({"a", "b"}, {"a"}) == {"b"}
    assert forbidden_present({"x"}, {"a", "x"}) == {"x"}
    assert CountRange(minimum=1, maximum=3).contains(2)
    assert not CountRange(exact=2).contains(3)


def test_path_normalization_and_safe_artifact_path(tmp_path: Path) -> None:
    assert normalize_repo_relative_path("./src\\\\index.js") == "src/index.js"
    nested = tmp_path / "out" / "report.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("{}", encoding="utf-8")
    assert safe_artifact_path(nested, base=tmp_path) == "out/report.json"
    assert safe_artifact_path("/Users/someone/secret/report.json") == "report.json"


def test_compare_reports_area_specific_mismatches() -> None:
    expected = ExpectedResults(
        schema_version="1.2",
        technology_facts_expected=("JavaScript",),
        technology_facts_forbidden=("COBOL",),
        expected_finding_rule_ids=("rule-required",),
        forbidden_finding_rule_ids=("rule-forbidden",),
        finding_count=CountRange(minimum=2, maximum=5),
        expected_evidence_paths=("src/index.js",),
    )
    actual = ActualAssessmentResult(
        schema_version="1.2",
        technologies=("Python",),
        finding_rule_ids=("rule-forbidden",),
        findings_count=1,
        evidence_paths=("./src/other.js",),
        artifact_paths={"report.json": "report.json"},
    )
    outcome = compare_actual_to_expected(
        repository_id="demo-repo",
        expected=expected,
        actual=actual,
    )
    mismatches, evaluated, matched = outcome.as_tuple()
    assert evaluated > matched
    areas = {item.assessment_area for item in mismatches}
    assert "technology_inventory" in areas
    assert "findings" in areas
    assert "evidence" in areas
    for item in mismatches:
        assert item.repository_id == "demo-repo"
        assert item.diagnostic
        assert item.expectation
        assert item.actual


def test_compare_pass_and_ordered_equality() -> None:
    expected = ExpectedResults(
        schema_version="1.2",
        technology_facts_expected=("JavaScript",),
        expected_finding_rule_ids=("rule-a",),
        finding_count=CountRange(exact=1),
    )
    actual = ActualAssessmentResult(
        schema_version="1.2",
        technologies=("JavaScript", "npm"),
        finding_rule_ids=("rule-a",),
        findings_count=1,
    )
    outcome = compare_actual_to_expected(
        repository_id="demo-repo",
        expected=expected,
        actual=actual,
    )
    mismatches, evaluated, matched = outcome.as_tuple()
    assert mismatches == ()
    assert evaluated == matched
    assert ordered_equal(["a", "b"], ["a", "b"])
    assert not ordered_equal(["a", "b"], ["b", "a"])


def test_deterministic_mismatch_ordering() -> None:
    expected = ExpectedResults(
        technology_facts_expected=("Z", "A"),
        forbidden_finding_rule_ids=("b", "a"),
    )
    actual = ActualAssessmentResult(
        technologies=("X",),
        finding_rule_ids=("a", "b"),
    )
    first = compare_actual_to_expected(
        repository_id="demo",
        expected=expected,
        actual=actual,
    ).mismatches
    second = compare_actual_to_expected(
        repository_id="demo",
        expected=expected,
        actual=actual,
    ).mismatches
    assert [m.diagnostic for m in first] == [m.diagnostic for m in second]
