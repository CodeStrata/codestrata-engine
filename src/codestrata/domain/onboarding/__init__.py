"""Domain package for repository onboarding (Phase 5.11)."""

from codestrata.domain.onboarding.enums import OnboardingStatus
from codestrata.domain.onboarding.errors import OnboardingError
from codestrata.domain.onboarding.identifiers import (
    ONBOARDING_MANIFEST_FILENAME,
    ONBOARDING_SCHEMA_NAME,
    ONBOARDING_SCHEMA_VERSION,
)
from codestrata.domain.onboarding.models import (
    OnboardingResult,
    OnboardingSummary,
    RepositoryOnboardingManifest,
)

__all__ = [
    "ONBOARDING_MANIFEST_FILENAME",
    "ONBOARDING_SCHEMA_NAME",
    "ONBOARDING_SCHEMA_VERSION",
    "OnboardingError",
    "OnboardingResult",
    "OnboardingStatus",
    "OnboardingSummary",
    "RepositoryOnboardingManifest",
]
