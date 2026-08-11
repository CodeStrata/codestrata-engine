"""Thin coverage wrapper for findings."""

from __future__ import annotations

def test_findings_importable() -> None:
    from verification.assessment_consistency import findings
    assert findings
