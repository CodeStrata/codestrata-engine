"""SV.5 traceability / credibility / determinism unit tests."""

from __future__ import annotations

from verification.assessment_report.credibility import find_unsupported_claims
from verification.assessment_report.determinism import normalize_html
from verification.assessment_report.scenarios import check_negative_scenarios
from verification.assessment_report.traceability import check_traceability


def test_negative_scenarios_pass() -> None:
    assert all(c.ok for c in check_negative_scenarios())


def test_normalize_html_strips_timestamps() -> None:
    html = "<p>generated 2026-01-02T03:04:05Z run 20260102-030405</p>"
    assert "<timestamp>" in normalize_html(html)
    assert "<run-id>" in normalize_html(html)


def test_unsupported_claims_library() -> None:
    assert "cloud ready" in find_unsupported_claims("service is cloud ready")
    assert not find_unsupported_claims("cloud readiness remains unsupported")
