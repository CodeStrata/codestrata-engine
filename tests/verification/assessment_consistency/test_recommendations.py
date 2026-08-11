"""Thin coverage wrapper for recommendations."""

from __future__ import annotations

def test_recommendations_importable() -> None:
    from verification.assessment_consistency import recommendations
    assert recommendations
