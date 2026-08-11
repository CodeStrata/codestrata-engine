"""Thin coverage wrapper for confidence."""

from __future__ import annotations

def test_confidence_importable() -> None:
    from verification.assessment_consistency import confidence
    assert confidence
