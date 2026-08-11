"""Privacy-safe reporting helpers for SV.10."""

from __future__ import annotations

from verification.repository_assessment.reporting import sanitize_text


def sanitize(value: str, *, workspace=None) -> str:
    return sanitize_text(value, workspace=workspace)
