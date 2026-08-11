"""SV.4 reporting privacy tests."""

from __future__ import annotations

from verification.repository_assessment.models import ScenarioResult, VerificationReport
from verification.repository_assessment.reporting import (
    report_contains_forbidden_leak,
    sanitize_text,
)


def test_sanitize_strips_abs_paths(tmp_path) -> None:
    text = f"failed at {tmp_path / 'repo'} with /Users/someone/secret"
    cleaned = sanitize_text(text, workspace=tmp_path)
    assert "/Users/" not in cleaned
    assert str(tmp_path) not in cleaned


def test_report_json_has_no_clone_paths() -> None:
    report = VerificationReport(
        ok=True,
        verdict="pass_with_catalog_qualification_gap",
        catalog_id="codestrata-smoke-regression-catalog",
        scenarios=(
            ScenarioResult(
                scenario_id="A_qualified_catalog_repository",
                ok=False,
                failures=("catalog_qualification_gap",),
            ),
        ),
    )
    payload = report.to_dict()
    assert payload["schema_name"] == "repository-assessment-verification"
    assert payload["schema_version"] == "1.0.0"
    assert report_contains_forbidden_leak(payload) == []
