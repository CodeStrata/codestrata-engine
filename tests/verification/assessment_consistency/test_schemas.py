"""Thin coverage wrapper for schemas."""

from __future__ import annotations

def test_schemas_importable() -> None:
    from verification.assessment_consistency import schemas
    assert schemas
