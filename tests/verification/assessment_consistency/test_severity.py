"""Thin coverage wrapper for severity."""

from __future__ import annotations

def test_severity_importable() -> None:
    from verification.assessment_consistency import severity
    assert severity
