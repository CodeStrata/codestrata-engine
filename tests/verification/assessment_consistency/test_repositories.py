"""Thin coverage wrapper for repositories."""

from __future__ import annotations

def test_repositories_importable() -> None:
    from verification.assessment_consistency import repositories
    assert repositories
