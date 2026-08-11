"""Timeout helpers for SV.10."""

from __future__ import annotations

from verification.curated_repository_validation.contract import (
    ASSESSMENT_TIMEOUT_S,
    CLONE_TIMEOUT_S,
)


def assessment_timeout_for_tier(tier: str) -> float:
    return float(ASSESSMENT_TIMEOUT_S.get(tier, ASSESSMENT_TIMEOUT_S["tier3"]))


def clone_timeout_for_tier(tier: str) -> float:
    return float(CLONE_TIMEOUT_S.get(tier, CLONE_TIMEOUT_S["tier3"]))


def is_timeout_exit(exit_code: int | None) -> bool:
    return exit_code == 124
