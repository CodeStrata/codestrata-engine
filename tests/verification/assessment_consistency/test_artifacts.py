"""Thin coverage wrapper for artifacts."""

from __future__ import annotations

def test_artifacts_importable() -> None:
    from verification.assessment_consistency import artifacts
    assert artifacts
