"""Preview vs production purpose checks (E14 admission is reused here)."""

from __future__ import annotations

from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.rules.errors import RuleDomainError


class PurposeAdmissionError(RuleDomainError):
    """Requested purpose is not admitted for this package/catalog."""


def admit_execution_purpose(
    *,
    package_purpose: ExecutionPurpose,
    requested_purpose: ExecutionPurpose,
) -> None:
    """Preview/candidate packages cannot authorize production. E14 owns signing."""

    if requested_purpose is ExecutionPurpose.PRODUCTION:
        if package_purpose is ExecutionPurpose.PREVIEW:
            raise PurposeAdmissionError(
                "preview package cannot authorize production",
                reason_code="preview_cannot_authorize_production",
            )
        if package_purpose is ExecutionPurpose.CANDIDATE_VALIDATION:
            raise PurposeAdmissionError(
                "candidate validation cannot authorize production",
                reason_code="preview_cannot_authorize_production",
            )
    if (
        package_purpose is ExecutionPurpose.PRODUCTION
        and requested_purpose is ExecutionPurpose.PREVIEW
    ):
        return
