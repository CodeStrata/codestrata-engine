"""Error mapping: bounded categories, safe details, and SDK-name classification."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_contracts.errors import ErrorCategory

# The exception-name -> category mapping the pre-migration provider applied,
# restated here so a silent reclassification fails a test.
_EXPECTED_SDK_CATEGORIES: dict[str, ErrorCategory] = {
    "AuthenticationError": ErrorCategory.AUTHENTICATION_FAILED,
    "PermissionDeniedError": ErrorCategory.AUTHORIZATION_FAILED,
    "NotFoundError": ErrorCategory.INVALID_MODEL,
    "BadRequestError": ErrorCategory.INVALID_REQUEST,
    "UnprocessableEntityError": ErrorCategory.INVALID_REQUEST,
    "APITimeoutError": ErrorCategory.TIMEOUT,
    "RateLimitError": ErrorCategory.RATE_LIMITED,
    "APIConnectionError": ErrorCategory.PROVIDER_UNAVAILABLE,
    "InternalServerError": ErrorCategory.PROVIDER_UNAVAILABLE,
}

_REQUIRED_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    {
        ErrorCategory.MISSING_CONFIGURATION,
        ErrorCategory.DEPENDENCY_UNAVAILABLE,
        ErrorCategory.AUTHENTICATION_FAILED,
        ErrorCategory.AUTHORIZATION_FAILED,
        ErrorCategory.INVALID_MODEL,
        ErrorCategory.TIMEOUT,
        ErrorCategory.RATE_LIMITED,
        ErrorCategory.PROVIDER_UNAVAILABLE,
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.INVALID_RESPONSE,
        ErrorCategory.PARSING_FAILED,
        ErrorCategory.INTERNAL_FAILURE,
    }
)


@pytest.mark.parametrize("name", sorted(_EXPECTED_SDK_CATEGORIES))
def test_sdk_exception_names_map_to_expected_categories(name: str) -> None:
    from tests.ai.provider_adapters.openai.fakes import named_exception

    failure = error_mapping.classify_sdk_exception(named_exception(name))

    assert failure.error.category is _EXPECTED_SDK_CATEGORIES[name]


def test_unknown_exception_becomes_internal_failure() -> None:
    failure = error_mapping.classify_sdk_exception(RuntimeError("something odd"))

    assert failure.error.category is ErrorCategory.INTERNAL_FAILURE
    assert failure.error.code == error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE


def test_every_required_category_is_reachable() -> None:
    reachable = set(error_mapping.CATEGORY_BY_CODE.values())

    assert _REQUIRED_CATEGORIES <= reachable


def test_every_code_has_a_bounded_safe_detail() -> None:
    for code in error_mapping.CATEGORY_BY_CODE:
        error = error_mapping.build_error(code)
        assert error.code == code
        assert error.detail
        assert len(error.detail) <= 240


def test_details_never_echo_sdk_text_or_a_class_name() -> None:
    from tests.ai.provider_adapters.openai.fakes import named_exception

    failure = error_mapping.classify_sdk_exception(
        named_exception("AuthenticationError", "Incorrect API key provided: sk-secret")
    )

    assert "sk-secret" not in failure.error.detail
    assert "AuthenticationError" not in failure.error.detail
    assert failure.error.detail == "The provider rejected the supplied credentials."


def test_legacy_detail_is_sanitized_but_retained_for_the_bridge() -> None:
    failure = error_mapping.classify_sdk_exception(RuntimeError("rate limit reached for gpt-4o"))

    assert failure.legacy_detail
    assert "rate limit reached" in failure.legacy_detail


def test_unknown_code_degrades_to_internal_failure() -> None:
    error = error_mapping.build_error("not_a_real_code")

    assert error.category is ErrorCategory.INTERNAL_FAILURE
    assert error.code == error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE


@pytest.mark.parametrize(
    "category",
    [ErrorCategory.TIMEOUT, ErrorCategory.RATE_LIMITED, ErrorCategory.PROVIDER_UNAVAILABLE],
)
def test_transient_categories_are_retryable(category: ErrorCategory) -> None:
    assert error_mapping.is_retryable(category) is True


@pytest.mark.parametrize(
    "category",
    [
        ErrorCategory.AUTHENTICATION_FAILED,
        ErrorCategory.AUTHORIZATION_FAILED,
        ErrorCategory.INVALID_MODEL,
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.INVALID_RESPONSE,
        ErrorCategory.PARSING_FAILED,
        ErrorCategory.MISSING_CONFIGURATION,
        ErrorCategory.DEPENDENCY_UNAVAILABLE,
    ],
)
def test_permanent_categories_are_not_retryable(category: ErrorCategory) -> None:
    assert error_mapping.is_retryable(category) is False


def test_retryable_and_non_retryable_partitions_do_not_overlap() -> None:
    assert not (error_mapping.RETRYABLE_CATEGORIES & error_mapping.NON_RETRYABLE_CATEGORIES)


def test_client_construction_failure_is_missing_configuration() -> None:
    failure = error_mapping.classify_client_construction_failure(ValueError("bad base_url"))

    assert failure.error.category is ErrorCategory.MISSING_CONFIGURATION
    assert failure.error.code == error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED


def test_unreadable_response_is_invalid_response() -> None:
    failure = error_mapping.classify_unreadable_response(AttributeError("no choices"))

    assert failure.error.category is ErrorCategory.INVALID_RESPONSE
    assert failure.error.code == error_mapping.CODE_UNREADABLE_RESPONSE


def test_classification_does_not_import_the_openai_sdk() -> None:
    """Classification is by class name, so it must work with no SDK installed."""

    import sys

    from tests.ai.provider_adapters.openai.fakes import named_exception

    before = "openai" in sys.modules
    error_mapping.classify_sdk_exception(named_exception("RateLimitError"))
    assert ("openai" in sys.modules) == before
