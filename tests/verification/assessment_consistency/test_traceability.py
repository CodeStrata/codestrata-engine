"""Thin coverage wrapper for traceability."""

from __future__ import annotations

def test_traceability_importable() -> None:
    from verification.assessment_consistency import traceability
    assert traceability
