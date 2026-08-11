"""Thin coverage wrapper for determinism."""

from __future__ import annotations

def test_determinism_importable() -> None:
    from verification.assessment_consistency import determinism
    assert determinism
