"""Thin coverage wrapper for terminology."""

from __future__ import annotations

def test_terminology_importable() -> None:
    from verification.assessment_consistency import terminology
    assert terminology
