"""Thin coverage wrapper for activation."""

from __future__ import annotations

def test_activation_importable() -> None:
    from verification.assessment_consistency import activation
    assert activation
