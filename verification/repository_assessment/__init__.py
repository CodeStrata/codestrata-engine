"""SV.4 — Repository Assessment End-to-End Verification."""

from __future__ import annotations

from verification.repository_assessment.contract import (
    REPOSITORY_ASSESSMENT_VERIFICATION_ID,
    REPOSITORY_ASSESSMENT_VERIFICATION_VERSION,
    AssessmentVerificationContract,
    default_contract,
)
from verification.repository_assessment.models import VerificationReport
from verification.repository_assessment.runner import (
    run_repository_assessment_verification,
)

__all__ = [
    "AssessmentVerificationContract",
    "REPOSITORY_ASSESSMENT_VERIFICATION_ID",
    "REPOSITORY_ASSESSMENT_VERIFICATION_VERSION",
    "VerificationReport",
    "default_contract",
    "run_repository_assessment_verification",
]
