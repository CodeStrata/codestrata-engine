"""Recommendations module tests (shared fixtures in test_report_json)."""

from __future__ import annotations

from verification.assessment_report.recommendations_json import check_recommendations_json


def test_module_importable() -> None:
    assert callable(check_recommendations_json)
