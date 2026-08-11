"""Thin coverage wrapper for limitations."""

from __future__ import annotations

def test_limitations_importable() -> None:
    from verification.assessment_consistency import limitations
    assert limitations
