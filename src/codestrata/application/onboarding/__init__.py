"""Application package for repository onboarding (Phase 5.11)."""

from codestrata.application.onboarding.service import (
    OnboardingApplicationService,
    run_onboarding,
)
from codestrata.application.onboarding.summary import (
    format_onboarding_result,
    format_onboarding_summary,
)

__all__ = [
    "OnboardingApplicationService",
    "format_onboarding_result",
    "format_onboarding_summary",
    "run_onboarding",
]
