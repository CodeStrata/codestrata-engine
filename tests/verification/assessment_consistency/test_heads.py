"""Thin coverage wrapper for heads."""

from __future__ import annotations

def test_heads_importable() -> None:
    from verification.assessment_consistency import heads
    assert heads
