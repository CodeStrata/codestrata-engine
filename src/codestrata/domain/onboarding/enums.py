"""Onboarding status enumerations (Phase 5.11)."""

from __future__ import annotations

from enum import StrEnum


class OnboardingStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
