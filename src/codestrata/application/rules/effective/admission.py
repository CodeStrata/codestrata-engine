"""Admit an Effective RuleSet. Time is execution context; digest is not mutated."""

from __future__ import annotations

from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.models import AdmissionRecord, ExecutionContext
from codestrata.application.rules.effective.timestamps import parse_utc
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.rules import EffectiveRuleSet, SignedPackageManifest, admit_package


def admit_effective(
    effective: EffectiveRuleSet,
    context: ExecutionContext,
    *,
    exception_valid_not_after: tuple[str, ...] = (),
) -> AdmissionRecord:
    """Record observed time separately. Preview cannot silently become production."""

    try:
        _assert_purpose(effective.execution_purpose, context.requested_purpose)
        _assert_validity(effective, context)
        _assert_exception_windows(exception_valid_not_after, context)
    except EffectiveSealError as error:
        return AdmissionRecord(
            admitted=False,
            observed_at=context.observed_at(),
            requested_purpose=context.requested_purpose,
            package_purpose=effective.execution_purpose,
            validity_not_after=effective.validity_not_after,
            exception_valid_not_after=exception_valid_not_after,
            reason_code=error.code,
        )
    return AdmissionRecord(
        admitted=True,
        observed_at=context.observed_at(),
        requested_purpose=context.requested_purpose,
        package_purpose=effective.execution_purpose,
        validity_not_after=effective.validity_not_after,
        exception_valid_not_after=exception_valid_not_after,
        reason_code=None,
    )


def admit_signed_package(manifest: SignedPackageManifest, requested: ExecutionPurpose) -> None:
    try:
        admit_package(manifest, requested)
    except Exception as error:
        raise EffectiveSealError(
            "preview_cannot_authorize_production",
            str(error),
        ) from error


def _assert_purpose(package: ExecutionPurpose, requested: ExecutionPurpose) -> None:
    if requested is ExecutionPurpose.PRODUCTION and package is not ExecutionPurpose.PRODUCTION:
        raise EffectiveSealError(
            "preview_cannot_authorize_production",
            "preview never silently becomes production",
        )


def _assert_validity(effective: EffectiveRuleSet, context: ExecutionContext) -> None:
    now = context.now
    if effective.validity_not_before is not None:
        start = parse_utc(effective.validity_not_before, label="validity_not_before")
        if now < start:
            raise EffectiveSealError("not_yet_valid", "effective ruleset is not yet valid")
    if effective.validity_not_after is not None:
        end = parse_utc(effective.validity_not_after, label="validity_not_after")
        if now > end:
            raise EffectiveSealError("expired", "effective ruleset validity has elapsed")


def _assert_exception_windows(windows: tuple[str, ...], context: ExecutionContext) -> None:
    for value in windows:
        end = parse_utc(value, label="exception validity")
        if context.now > end:
            raise EffectiveSealError(
                "expired_exception",
                "included exception validity has elapsed",
            )
