"""Cross-checks for ``execution_policy`` constants against ground truth."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution_policy import (
    ALLOWED_BACKOFF_STRATEGIES,
    ALLOWED_TIMEOUT_SCOPES,
    DEFAULT_MAXIMUM_ATTEMPTS,
    DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES,
    DEFAULT_RETRYABLE_ERROR_CATEGORIES,
    DEFAULT_TIMEOUT_SECONDS,
    HARD_CONSTRAINTS,
    MAX_MAXIMUM_ATTEMPTS,
    MAX_TIMEOUT_SECONDS,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SETTINGS_DEFAULT_MAX_RETRIES,
)
from verification.ai_provider_execution.models import CheckResult


def check_retryable_partition_covers_every_error_category_exactly_once() -> CheckResult:
    retryable = set(DEFAULT_RETRYABLE_ERROR_CATEGORIES)
    non_retryable = set(DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES)
    all_categories = {category.value for category in ErrorCategory}
    ok = (
        retryable | non_retryable == all_categories
        and retryable.isdisjoint(non_retryable)
    )
    return CheckResult(
        name="retryable_and_non_retryable_partition_covers_every_error_category_exactly_once",
        category="policy",
        ok=ok,
        detail=(
            f"retryable={sorted(retryable)} non_retryable={sorted(non_retryable)} "
            f"all={sorted(all_categories)}"
        ),
    )


def check_timeout_rate_limited_and_provider_unavailable_are_retryable() -> CheckResult:
    ok = {"timeout", "rate_limited", "provider_unavailable"} <= set(
        DEFAULT_RETRYABLE_ERROR_CATEGORIES
    )
    return CheckResult(
        name="timeout_rate_limited_and_provider_unavailable_are_retryable_by_default",
        category="policy",
        ok=ok,
        detail=f"retryable={sorted(DEFAULT_RETRYABLE_ERROR_CATEGORIES)}",
    )


def check_authentication_and_authorization_are_never_retryable() -> CheckResult:
    ok = {"authentication_failed", "authorization_failed"} <= set(
        DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES
    )
    return CheckResult(
        name="authentication_and_authorization_failures_are_never_retryable_by_default",
        category="policy",
        ok=ok,
        detail=f"non_retryable={sorted(DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES)}",
    )


def check_default_maximum_attempts_is_bounded() -> CheckResult:
    ok = 1 <= DEFAULT_MAXIMUM_ATTEMPTS <= MAX_MAXIMUM_ATTEMPTS
    return CheckResult(
        name="default_maximum_attempts_is_within_bounds",
        category="policy",
        ok=ok,
        detail=f"default={DEFAULT_MAXIMUM_ATTEMPTS} ceiling={MAX_MAXIMUM_ATTEMPTS}",
    )


def check_default_timeout_seconds_is_positive_and_bounded() -> CheckResult:
    ok = 0 < DEFAULT_TIMEOUT_SECONDS <= MAX_TIMEOUT_SECONDS
    return CheckResult(
        name="default_timeout_seconds_is_positive_and_within_max_timeout_seconds",
        category="policy",
        ok=ok,
        detail=f"default={DEFAULT_TIMEOUT_SECONDS} ceiling={MAX_TIMEOUT_SECONDS}",
    )


def check_settings_default_max_retries_is_non_negative() -> CheckResult:
    ok = SETTINGS_DEFAULT_MAX_RETRIES >= 0
    return CheckResult(
        name="settings_default_max_retries_is_non_negative",
        category="policy",
        ok=ok,
        detail=f"value={SETTINGS_DEFAULT_MAX_RETRIES}",
    )


def check_allowed_timeout_scopes_and_backoff_strategies_are_bounded_and_non_empty() -> CheckResult:
    ok = (
        len(ALLOWED_TIMEOUT_SCOPES) > 0
        and len(set(ALLOWED_TIMEOUT_SCOPES)) == len(ALLOWED_TIMEOUT_SCOPES)
        and len(ALLOWED_BACKOFF_STRATEGIES) > 0
        and len(set(ALLOWED_BACKOFF_STRATEGIES)) == len(ALLOWED_BACKOFF_STRATEGIES)
    )
    return CheckResult(
        name="allowed_timeout_scopes_and_backoff_strategies_are_bounded_and_deduplicated",
        category="policy",
        ok=ok,
        detail=f"scopes={ALLOWED_TIMEOUT_SCOPES} strategies={ALLOWED_BACKOFF_STRATEGIES}",
    )


def check_required_compatibility_requirement_ids_are_exactly_cr1_through_cr6() -> CheckResult:
    ok = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == ("CR-1", "CR-2", "CR-3", "CR-4", "CR-5", "CR-6")
    return CheckResult(
        name="required_compatibility_requirement_ids_are_exactly_cr1_through_cr6",
        category="policy",
        ok=ok,
        detail=f"ids={REQUIRED_COMPATIBILITY_REQUIREMENT_IDS}",
    )


def check_hard_constraints_are_recorded_and_non_empty() -> CheckResult:
    ok = len(HARD_CONSTRAINTS) > 0 and all(
        isinstance(item, str) and item for item in HARD_CONSTRAINTS
    )
    return CheckResult(
        name="hard_constraints_tuple_is_recorded_and_non_empty",
        category="policy",
        ok=ok,
        detail=f"count={len(HARD_CONSTRAINTS)}",
    )


def run_policy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_retryable_partition_covers_every_error_category_exactly_once(),
        check_timeout_rate_limited_and_provider_unavailable_are_retryable(),
        check_authentication_and_authorization_are_never_retryable(),
        check_default_maximum_attempts_is_bounded(),
        check_default_timeout_seconds_is_positive_and_bounded(),
        check_settings_default_max_retries_is_non_negative(),
        check_allowed_timeout_scopes_and_backoff_strategies_are_bounded_and_non_empty(),
        check_required_compatibility_requirement_ids_are_exactly_cr1_through_cr6(),
        check_hard_constraints_are_recorded_and_non_empty(),
    ]
    matrix = {
        "default_retryable_error_categories": list(DEFAULT_RETRYABLE_ERROR_CATEGORIES),
        "default_non_retryable_error_categories": list(DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES),
    }
    return checks, matrix


__all__ = [
    "check_allowed_timeout_scopes_and_backoff_strategies_are_bounded_and_non_empty",
    "check_authentication_and_authorization_are_never_retryable",
    "check_default_maximum_attempts_is_bounded",
    "check_default_timeout_seconds_is_positive_and_bounded",
    "check_hard_constraints_are_recorded_and_non_empty",
    "check_required_compatibility_requirement_ids_are_exactly_cr1_through_cr6",
    "check_retryable_partition_covers_every_error_category_exactly_once",
    "check_settings_default_max_retries_is_non_negative",
    "check_timeout_rate_limited_and_provider_unavailable_are_retryable",
    "run_policy_checks",
]
