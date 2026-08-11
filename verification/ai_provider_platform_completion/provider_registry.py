"""Thin alias for the Slice 11.13 brief layout — see checks.py."""

from __future__ import annotations

from verification.ai_provider_platform_completion.checks import (
    run_provider_registry_checks, run_registry_decision_checks,
)

__all__ = [
    "run_provider_registry_checks",
    "run_registry_decision_checks",
]
