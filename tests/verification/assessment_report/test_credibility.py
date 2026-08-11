"""Credibility tests."""

from __future__ import annotations

from verification.assessment_report.credibility import find_unsupported_claims


def test_roi_and_ready_claims() -> None:
    assert find_unsupported_claims("AI ready platform")
    assert not find_unsupported_claims("AI readiness is not claimed")
