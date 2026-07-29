"""Actionable onboarding validation errors (Phase 5.11)."""

from __future__ import annotations


class OnboardingError(Exception):
    """Raised when onboarding cannot proceed; message includes a Fix hint."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
