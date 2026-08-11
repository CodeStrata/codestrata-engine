"""Error mapping: the full SDK matrix, bounded details, and the retry partition."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import diagnostics, error_mapping
from codestrata.ai.provider_contracts.errors import ErrorCategory
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.contract import (
    NON_RETRYABLE_ERROR_CATEGORIES,
    REQUIRED_ERROR_CATEGORIES,
    RETRYABLE_ERROR_CATEGORIES,
    SDK_EXCEPTION_CATEGORY_MATRIX,
)
from verification.openai_provider_migration.models import CheckResult

_MAX_DETAIL_LENGTH = 240

# A synthetic exception body containing everything a detail must never echo.
_LOUD_EXCEPTION_TEXT = (
    "sk-synthetic-leak-value at https://synthetic-gateway.invalid/v1 "
    "for model synthetic-model in /Users/synthetic/path/file.py request req_synthetic123"
)
_LEAK_TOKENS: tuple[str, ...] = (
    "sk-synthetic-leak-value",
    "synthetic-gateway",
    "synthetic-model",
    "/Users/synthetic",
    "req_synthetic123",
)


def check_every_sdk_exception_maps_to_the_expected_category() -> CheckResult:
    wrong: dict[str, str] = {}
    for class_name, expected in SDK_EXCEPTION_CATEGORY_MATRIX.items():
        mapped = error_mapping.classify_sdk_exception(fixtures.sdk_exception(class_name))
        if mapped.error.category.value != expected:
            wrong[class_name] = mapped.error.category.value
    return CheckResult(
        name="every_openai_sdk_exception_maps_to_its_expected_error_category",
        category="errors",
        ok=not wrong,
        detail=f"mismatches={sorted(wrong)}",
        evidence={"matrix_size": len(SDK_EXCEPTION_CATEGORY_MATRIX)},
    )


def check_an_unknown_exception_is_an_internal_failure() -> CheckResult:
    mapped = error_mapping.classify_sdk_exception(fixtures.sdk_exception("SomeFutureSDKError"))
    ok = (
        mapped.error.category is ErrorCategory.INTERNAL_FAILURE
        and mapped.error.code == error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE
    )
    return CheckResult(
        name="an_unrecognized_sdk_exception_falls_back_to_a_bounded_internal_failure",
        category="errors",
        ok=ok,
        detail=f"category={mapped.error.category.value}",
    )


def check_all_required_categories_are_reachable() -> CheckResult:
    reachable = {
        error_mapping.build_error(code).category.value for code in error_mapping.CATEGORY_BY_CODE
    }
    missing = sorted(set(REQUIRED_ERROR_CATEGORIES) - reachable)
    return CheckResult(
        name="every_required_error_category_is_reachable_from_the_adapter",
        category="errors",
        ok=not missing,
        detail=f"unreachable={missing}",
        evidence={"reachable_categories": sorted(reachable)},
    )


def check_the_retry_partition_matches_slice_11_4() -> CheckResult:
    retryable = sorted(
        category.value for category in ErrorCategory if error_mapping.is_retryable(category)
    )
    non_retryable = sorted(
        category.value
        for category in ErrorCategory
        if not error_mapping.is_retryable(category) and category.value in REQUIRED_ERROR_CATEGORIES
    )
    ok = retryable == sorted(RETRYABLE_ERROR_CATEGORIES) and non_retryable == sorted(
        NON_RETRYABLE_ERROR_CATEGORIES
    )
    return CheckResult(
        name="the_retryable_non_retryable_partition_matches_the_slice_11_4_default",
        category="errors",
        ok=ok,
        detail=f"retryable={retryable}",
    )


def check_authentication_and_invalid_request_are_never_retryable() -> CheckResult:
    never_retryable = (
        ErrorCategory.AUTHENTICATION_FAILED,
        ErrorCategory.AUTHORIZATION_FAILED,
        ErrorCategory.INVALID_MODEL,
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.INVALID_RESPONSE,
        ErrorCategory.PARSING_FAILED,
    )
    offenders = sorted(
        category.value for category in never_retryable if error_mapping.is_retryable(category)
    )
    return CheckResult(
        name="credential_request_and_parsing_failures_are_never_retryable",
        category="errors",
        ok=not offenders,
        detail=f"unexpectedly_retryable={offenders}",
    )


def check_error_details_are_bounded_safe_prose() -> CheckResult:
    offenders: list[str] = []
    for code in error_mapping.CATEGORY_BY_CODE:
        detail = error_mapping.build_error(code).detail
        if not detail or len(detail) > _MAX_DETAIL_LENGTH or not detail.endswith("."):
            offenders.append(code)
    return CheckResult(
        name="every_error_detail_is_bounded_single_sentence_safe_prose",
        category="errors",
        ok=not offenders,
        detail=f"offending_codes={sorted(offenders)}",
        evidence={"maximum_detail_length": _MAX_DETAIL_LENGTH},
    )


def check_error_details_never_echo_the_exception() -> CheckResult:
    offenders: list[str] = []
    for class_name in SDK_EXCEPTION_CATEGORY_MATRIX:
        mapped = error_mapping.classify_sdk_exception(
            fixtures.sdk_exception(class_name, _LOUD_EXCEPTION_TEXT)
        )
        rendered = f"{mapped.error.detail} {mapped.error.code} {mapped.error.category.value}"
        if any(token in rendered for token in _LEAK_TOKENS) or class_name in rendered:
            offenders.append(class_name)
    return CheckResult(
        name="a_bounded_error_never_echoes_exception_text_secrets_urls_models_or_paths",
        category="errors",
        ok=not offenders,
        detail=f"leaking_cases={sorted(offenders)}",
    )


def check_the_legacy_detail_is_sanitized_and_bridge_only() -> CheckResult:
    """``legacy_detail`` is sanitized, and is never attached to the error object."""

    mapped = error_mapping.classify_sdk_exception(
        fixtures.sdk_exception("BadRequestError", _LOUD_EXCEPTION_TEXT)
    )
    secret_removed = "sk-synthetic-leak-value" not in mapped.legacy_detail
    not_on_error = _LOUD_EXCEPTION_TEXT not in mapped.error.detail
    return CheckResult(
        name="the_bridge_only_legacy_detail_is_sanitized_and_absent_from_the_error_object",
        category="errors",
        ok=secret_removed and not_on_error,
        detail="api-key-shaped text is redacted before the bridge sees it",
    )


def check_classification_needs_no_sdk_import() -> CheckResult:
    """The adapter classifies by exception class name, so no SDK import is needed."""

    imports_sdk = "openai" in {
        name.split(".")[0]
        for name in getattr(error_mapping, "__dict__", {})
        if isinstance(name, str)
    }
    mapped = error_mapping.classify_sdk_exception(fixtures.sdk_exception("RateLimitError"))
    ok = not imports_sdk and mapped.error.category is ErrorCategory.RATE_LIMITED
    return CheckResult(
        name="sdk_failures_are_classified_by_class_name_without_importing_the_sdk",
        category="errors",
        ok=ok,
        detail="a synthetic exception class name classifies correctly",
    )


def check_client_construction_failures_are_configuration_errors() -> CheckResult:
    mapped = error_mapping.classify_client_construction_failure(
        fixtures.sdk_exception("ValueError", _LOUD_EXCEPTION_TEXT)
    )
    ok = (
        mapped.error.category is ErrorCategory.MISSING_CONFIGURATION
        and mapped.error.code == error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED
    )
    return CheckResult(
        name="a_client_construction_failure_maps_to_missing_configuration",
        category="errors",
        ok=ok,
        detail=f"category={mapped.error.category.value}",
    )


def check_the_published_matrices_agree_with_classification() -> CheckResult:
    """``diagnostics`` publishes the same matrix the adapter actually applies."""

    category_matrix = diagnostics.error_category_matrix()
    retry_matrix = diagnostics.retryability_matrix()
    category_disagreements = sorted(
        code
        for code, category in category_matrix.items()
        if error_mapping.build_error(code).category.value != category
    )
    retry_disagreements = sorted(
        code
        for code, retryable in retry_matrix.items()
        if error_mapping.is_retryable(error_mapping.build_error(code).category) is not retryable
    )
    return CheckResult(
        name="the_published_error_and_retry_matrices_agree_with_actual_classification",
        category="errors",
        ok=not category_disagreements and not retry_disagreements,
        detail=f"category_disagreements={category_disagreements} "
        f"retry_disagreements={retry_disagreements}",
    )


def run_error_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_every_sdk_exception_maps_to_the_expected_category(),
        check_an_unknown_exception_is_an_internal_failure(),
        check_all_required_categories_are_reachable(),
        check_the_retry_partition_matches_slice_11_4(),
        check_authentication_and_invalid_request_are_never_retryable(),
        check_error_details_are_bounded_safe_prose(),
        check_error_details_never_echo_the_exception(),
        check_the_legacy_detail_is_sanitized_and_bridge_only(),
        check_classification_needs_no_sdk_import(),
        check_client_construction_failures_are_configuration_errors(),
        check_the_published_matrices_agree_with_classification(),
    ]
    matrix: dict[str, Any] = {
        "error_category_by_code": diagnostics.error_category_matrix(),
        "non_retryable_categories": list(NON_RETRYABLE_ERROR_CATEGORIES),
        "retryable_categories": list(RETRYABLE_ERROR_CATEGORIES),
        "sdk_exception_category_matrix": dict(SDK_EXCEPTION_CATEGORY_MATRIX),
    }
    return checks, matrix


__all__ = [
    "check_all_required_categories_are_reachable",
    "check_an_unknown_exception_is_an_internal_failure",
    "check_authentication_and_invalid_request_are_never_retryable",
    "check_classification_needs_no_sdk_import",
    "check_client_construction_failures_are_configuration_errors",
    "check_error_details_are_bounded_safe_prose",
    "check_error_details_never_echo_the_exception",
    "check_every_sdk_exception_maps_to_the_expected_category",
    "check_the_legacy_detail_is_sanitized_and_bridge_only",
    "check_the_published_matrices_agree_with_classification",
    "check_the_retry_partition_matches_slice_11_4",
    "run_error_checks",
]
