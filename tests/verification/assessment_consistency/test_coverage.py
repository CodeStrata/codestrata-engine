"""Thin coverage wrapper for coverage."""

from __future__ import annotations

def test_coverage_importable() -> None:
    from verification.assessment_consistency import coverage
    assert coverage
