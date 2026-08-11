"""Thin coverage wrapper for outliers."""

from __future__ import annotations

def test_outliers_importable() -> None:
    from verification.assessment_consistency import outliers
    assert outliers
