"""Error classification: bounded categories, stable codes, unchanged ladder."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import error_mapping
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import (
    NON_RETRYABLE_ERROR_CATEGORIES,
    REQUIRED_ERROR_CATEGORIES,
    RETRYABLE_ERROR_CATEGORIES,
    SDK_ERROR_CODE_CATEGORY_MATRIX,
    SDK_EXCEPTION_CATEGORY_MATRIX,
)
from verification.bedrock_provider_migration.models import CheckResult

_MAX_DETAIL_LENGTH = 240


def check_every_required_category_is_reachable() -> CheckResult:
    produced = {category.value for category in error_mapping.CATEGORY_BY_CODE.values()}
    missing = sorted(set(REQUIRED_ERROR_CATEGORIES) - produced)
    return CheckResult(
        name="every_required_error_category_is_reachable_from_a_diagnostic_code",
        category="errors",
        ok=not missing,
        detail=f"missing_categories={missing}",
        evidence={"reachable_category_count": len(produced)},
    )


def check_sdk_exception_names_classify_as_expected() -> CheckResult:
    mismatches: list[str] = []
    for class_name, expected in sorted(SDK_EXCEPTION_CATEGORY_MATRIX.items()):
        mapped = error_mapping.classify_sdk_exception(fixtures.sdk_exception(class_name))
        actual = mapped.error.category.value
        if actual != expected:
            mismatches.append(f"{class_name}:{actual}!={expected}")
    return CheckResult(
        name="every_credential_and_timeout_exception_name_classifies_as_expected",
        category="errors",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
        evidence={"exception_names_checked": len(SDK_EXCEPTION_CATEGORY_MATRIX)},
    )


def check_aws_error_codes_classify_as_expected() -> CheckResult:
    mismatches: list[str] = []
    for aws_code, expected in sorted(SDK_ERROR_CODE_CATEGORY_MATRIX.items()):
        mapped = error_mapping.classify_sdk_exception(fixtures.client_error(aws_code))
        actual = mapped.error.category.value
        if actual != expected:
            mismatches.append(f"{aws_code}:{actual}!={expected}")
    return CheckResult(
        name="every_aws_error_code_classifies_as_expected",
        category="errors",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
        evidence={"aws_error_codes_checked": len(SDK_ERROR_CODE_CATEGORY_MATRIX)},
    )


def check_an_unknown_client_error_becomes_a_service_error() -> CheckResult:
    mapped = error_mapping.classify_sdk_exception(fixtures.client_error("SomeBrandNewCode"))
    return CheckResult(
        name="an_unrecognized_aws_error_code_falls_back_to_a_bounded_service_error",
        category="errors",
        ok=(
            mapped.error.code == error_mapping.CODE_SERVICE_ERROR
            and mapped.legacy_label == "SomeBrandNewCode"
        ),
        detail=f"code={mapped.error.code}",
    )


def check_an_unknown_exception_becomes_an_unexpected_failure() -> CheckResult:
    mapped = error_mapping.classify_sdk_exception(ValueError("synthetic"))
    return CheckResult(
        name="an_unrecognized_exception_falls_back_to_a_bounded_unexpected_failure",
        category="errors",
        ok=mapped.error.category is ErrorCategory.INTERNAL_FAILURE,
        detail=f"category={mapped.error.category.value}",
    )


def check_the_aws_authentication_error_is_recognized_by_name() -> CheckResult:
    """Recognized without importing ``aws_config`` into ``error_mapping``."""

    mapped = error_mapping.classify_sdk_exception(fixtures.aws_authentication_error())
    return CheckResult(
        name="an_aws_authentication_error_is_recognized_by_class_name_alone",
        category="errors",
        ok=mapped.error.code == error_mapping.CODE_AWS_AUTHENTICATION_ERROR,
        detail=f"code={mapped.error.code}",
    )


def check_the_classification_ladder_order_is_preserved() -> CheckResult:
    """An exception name match must win over an AWS error code on the same object."""

    error = fixtures.sdk_exception("ReadTimeoutError", "synthetic")
    error.response = {  # type: ignore[attr-defined]
        "Error": {"Code": "ValidationException", "Message": "synthetic"}
    }
    mapped = error_mapping.classify_sdk_exception(error)
    return CheckResult(
        name="the_exception_name_partition_is_still_evaluated_before_the_aws_error_code",
        category="errors",
        ok=mapped.error.category is ErrorCategory.TIMEOUT,
        detail=f"category={mapped.error.category.value}",
    )


def check_every_detail_is_bounded_and_fixed() -> CheckResult:
    offenders: list[str] = []
    for code in sorted(error_mapping.CATEGORY_BY_CODE):
        detail = error_mapping.build_error(code).detail
        if not detail or len(detail) > _MAX_DETAIL_LENGTH:
            offenders.append(code)
    return CheckResult(
        name="every_bounded_error_detail_is_fixed_prose_within_the_length_ceiling",
        category="errors",
        ok=not offenders,
        detail=f"offenders={offenders}",
        evidence={"maximum_detail_length": _MAX_DETAIL_LENGTH},
    )


def check_the_detail_never_carries_the_exception_text() -> CheckResult:
    secret = "synthetic-exception-body-0123456789"
    offenders: list[str] = []
    for class_name in sorted(error_mapping.SDK_EXCEPTION_NAME_TO_CODE):
        mapped = error_mapping.classify_sdk_exception(
            fixtures.sdk_exception(class_name, secret)
        )
        if secret in mapped.error.detail or secret in mapped.error.code:
            offenders.append(class_name)
    return CheckResult(
        name="no_bounded_error_detail_or_code_carries_the_raw_exception_text",
        category="errors",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_the_retryability_partition_is_unchanged() -> CheckResult:
    retryable = {category.value for category in error_mapping.RETRYABLE_CATEGORIES}
    non_retryable = {category.value for category in error_mapping.NON_RETRYABLE_CATEGORIES}
    return CheckResult(
        name="the_default_retryable_and_non_retryable_category_partition_is_unchanged",
        category="errors",
        ok=(
            retryable == set(RETRYABLE_ERROR_CATEGORIES)
            and non_retryable == set(NON_RETRYABLE_ERROR_CATEGORIES)
        ),
        detail=f"retryable={sorted(retryable)}",
    )


def check_a_sdk_failure_never_escapes_execute() -> CheckResult:
    result = build_bedrock_provider(
        client=fixtures.Client(fixtures.client_error("ThrottlingException"))
    ).execute(fixtures.provider_request())
    return CheckResult(
        name="an_sdk_exception_during_converse_becomes_a_failed_result_not_a_raise",
        category="errors",
        ok=(
            result.status is ProviderExecutionStatus.FAILED
            and result.error is not None
            and result.error.category is ErrorCategory.RATE_LIMITED
        ),
        detail=f"status={result.status.value}",
    )


def check_keyboard_interrupt_still_propagates() -> CheckResult:
    adapter = build_bedrock_provider(client=fixtures.Client(KeyboardInterrupt()))
    try:
        adapter.execute(fixtures.provider_request())
    except KeyboardInterrupt:
        propagated = True
    else:
        propagated = False
    return CheckResult(
        name="a_keyboard_interrupt_still_propagates_through_execute",
        category="errors",
        ok=propagated,
        detail="only Exception subclasses are absorbed into bounded results",
    )


def run_error_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_every_required_category_is_reachable(),
        check_sdk_exception_names_classify_as_expected(),
        check_aws_error_codes_classify_as_expected(),
        check_an_unknown_client_error_becomes_a_service_error(),
        check_an_unknown_exception_becomes_an_unexpected_failure(),
        check_the_aws_authentication_error_is_recognized_by_name(),
        check_the_classification_ladder_order_is_preserved(),
        check_every_detail_is_bounded_and_fixed(),
        check_the_detail_never_carries_the_exception_text(),
        check_the_retryability_partition_is_unchanged(),
        check_a_sdk_failure_never_escapes_execute(),
        check_keyboard_interrupt_still_propagates(),
    ]
    matrix: dict[str, Any] = {
        "aws_error_code_categories": dict(sorted(SDK_ERROR_CODE_CATEGORY_MATRIX.items())),
        "diagnostic_code_categories": {
            code: category.value
            for code, category in sorted(error_mapping.CATEGORY_BY_CODE.items())
        },
        "exception_name_categories": dict(sorted(SDK_EXCEPTION_CATEGORY_MATRIX.items())),
        "non_retryable_categories": list(NON_RETRYABLE_ERROR_CATEGORIES),
        "retryable_categories": list(RETRYABLE_ERROR_CATEGORIES),
    }
    return checks, matrix


__all__ = [
    "check_a_sdk_failure_never_escapes_execute",
    "check_an_unknown_client_error_becomes_a_service_error",
    "check_an_unknown_exception_becomes_an_unexpected_failure",
    "check_aws_error_codes_classify_as_expected",
    "check_every_detail_is_bounded_and_fixed",
    "check_every_required_category_is_reachable",
    "check_keyboard_interrupt_still_propagates",
    "check_sdk_exception_names_classify_as_expected",
    "check_the_aws_authentication_error_is_recognized_by_name",
    "check_the_classification_ladder_order_is_preserved",
    "check_the_detail_never_carries_the_exception_text",
    "check_the_retryability_partition_is_unchanged",
    "run_error_checks",
]
