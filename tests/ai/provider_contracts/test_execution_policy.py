"""Tests for ``execution_policy`` constants and their internal consistency."""

from __future__ import annotations

from codestrata.ai.provider_contracts import execution_policy
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.policy import ALLOWED_ERROR_CATEGORIES, ALLOWED_PROVIDER_IDS


def test_execution_allowed_provider_ids_matches_policy() -> None:
    assert execution_policy.EXECUTION_ALLOWED_PROVIDER_IDS == ALLOWED_PROVIDER_IDS


def test_default_retryable_and_non_retryable_partition_covers_every_category_exactly_once() -> None:
    retryable = set(execution_policy.DEFAULT_RETRYABLE_ERROR_CATEGORIES)
    non_retryable = set(execution_policy.DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES)
    assert retryable.isdisjoint(non_retryable)
    assert retryable | non_retryable == set(ALLOWED_ERROR_CATEGORIES)


def test_default_retryable_categories_are_exactly_transient_categories() -> None:
    assert set(execution_policy.DEFAULT_RETRYABLE_ERROR_CATEGORIES) == {
        ErrorCategory.TIMEOUT.value,
        ErrorCategory.RATE_LIMITED.value,
        ErrorCategory.PROVIDER_UNAVAILABLE.value,
    }


def test_default_timeout_seconds_matches_real_provider_default() -> None:
    from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS as REAL_DEFAULT

    assert execution_policy.DEFAULT_TIMEOUT_SECONDS == REAL_DEFAULT


def test_settings_default_max_retries_matches_real_settings_defaults() -> None:
    from codestrata.config.settings import BedrockSettings, OpenAISettings

    assert execution_policy.SETTINGS_DEFAULT_MAX_RETRIES == BedrockSettings().max_retries
    assert execution_policy.SETTINGS_DEFAULT_MAX_RETRIES == OpenAISettings().max_retries


def test_default_maximum_attempts_is_exactly_one() -> None:
    assert execution_policy.DEFAULT_MAXIMUM_ATTEMPTS == 1


def test_required_compatibility_requirement_ids_are_cr1_through_cr6() -> None:
    assert execution_policy.REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == (
        "CR-1",
        "CR-2",
        "CR-3",
        "CR-4",
        "CR-5",
        "CR-6",
    )


def test_hard_constraints_do_not_mention_openrouter() -> None:
    for constraint in execution_policy.HARD_CONSTRAINTS:
        assert "openrouter" not in constraint.lower()


def test_allowed_timeout_scopes_and_backoff_strategies_are_bounded() -> None:
    assert execution_policy.ALLOWED_TIMEOUT_SCOPES == ("provider_request", "total_execution")
    assert execution_policy.ALLOWED_BACKOFF_STRATEGIES == ("none", "fixed", "exponential")
