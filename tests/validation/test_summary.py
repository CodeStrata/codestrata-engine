"""Summary and verdict aggregation tests."""

from __future__ import annotations

from validation.models import ComparisonMismatch, ValidationRunResult, ValidationVerdict
from validation.summary import build_validation_summary, summary_to_safe_dict


def test_summary_totals_and_area_grouping() -> None:
    results = [
        ValidationRunResult(
            repository_id="a",
            verdict=ValidationVerdict.PASS,
            expectations_evaluated=3,
            expectations_matched=3,
            duration_ms=12.5,
            artifact_dir="/Users/someone/validation/results/a",
        ),
        ValidationRunResult(
            repository_id="b",
            verdict=ValidationVerdict.FAIL,
            expectations_evaluated=4,
            expectations_matched=2,
            mismatches=(
                ComparisonMismatch(
                    repository_id="b",
                    assessment_area="findings",
                    expectation="required",
                    actual="missing",
                    artifact_path="/Users/someone/validation/results/b/report.json",
                    diagnostic="missing rule",
                ),
                ComparisonMismatch(
                    repository_id="b",
                    assessment_area="findings",
                    expectation="count",
                    actual="0",
                    diagnostic="too low",
                ),
            ),
            duration_ms=20.0,
            artifact_dir="/Users/someone/validation/results/b",
        ),
        ValidationRunResult(
            repository_id="c",
            verdict=ValidationVerdict.ERROR,
            error_message="boom",
        ),
        ValidationRunResult(
            repository_id="d",
            verdict=ValidationVerdict.SKIPPED,
            skip_reason="remote excluded",
        ),
    ]
    summary = build_validation_summary(results)
    assert summary.total_repositories == 4
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.errors == 1
    assert summary.skipped == 1
    assert summary.total_expectations == 7
    assert summary.matched_expectations == 5
    assert summary.mismatches_by_area == {"findings": 2}
    assert summary.repository_durations_ms["a"] == 12.5

    safe = summary_to_safe_dict(summary)
    assert "duration_ms" not in safe["results"][0]
    assert not str(safe["results"][1]["mismatches"][0]["artifact_path"]).startswith("/Users/")
