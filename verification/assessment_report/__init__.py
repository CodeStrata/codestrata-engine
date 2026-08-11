"""SV.5 — Assessment Report Verification."""

from __future__ import annotations

from verification.assessment_report.contract import (
    ASSESSMENT_REPORT_VERIFICATION_ID,
    ASSESSMENT_REPORT_VERIFICATION_VERSION,
    ReportVerificationContract,
    default_contract,
)
from verification.assessment_report.models import VerificationReport
from verification.assessment_report.runner import run_assessment_report_verification

__all__ = [
    "ASSESSMENT_REPORT_VERIFICATION_ID",
    "ASSESSMENT_REPORT_VERIFICATION_VERSION",
    "ReportVerificationContract",
    "VerificationReport",
    "default_contract",
    "run_assessment_report_verification",
]
