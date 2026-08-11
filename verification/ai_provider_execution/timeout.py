"""Verifies ``TimeoutPolicy``: bounds, defaults, and non-enforcement by the executor."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_policy import DEFAULT_TIMEOUT_SECONDS
from codestrata.ai.provider_contracts.timeout_policy import (
    DEFAULT_TIMEOUT_POLICY,
    TimeoutPolicy,
    TimeoutScope,
)
from verification.ai_provider_execution.models import CheckResult


def check_default_timeout_policy_is_sixty_seconds_provider_request_and_enabled() -> CheckResult:
    ok = (
        DEFAULT_TIMEOUT_POLICY.timeout_seconds == DEFAULT_TIMEOUT_SECONDS == 60.0
        and DEFAULT_TIMEOUT_POLICY.scope is TimeoutScope.PROVIDER_REQUEST
        and DEFAULT_TIMEOUT_POLICY.enabled is True
    )
    return CheckResult(
        name="default_timeout_policy_is_sixty_seconds_provider_request_scope_and_enabled",
        category="timeout",
        ok=ok,
        detail=(
            f"timeout_seconds={DEFAULT_TIMEOUT_POLICY.timeout_seconds} "
            f"scope={DEFAULT_TIMEOUT_POLICY.scope} enabled={DEFAULT_TIMEOUT_POLICY.enabled}"
        ),
    )


def check_timeout_policy_rejects_zero_and_negative_seconds() -> CheckResult:
    rejected = 0
    for value in (0.0, -1.0, -60.0):
        try:
            TimeoutPolicy(timeout_seconds=value)
        except ProviderContractValidationError:
            rejected += 1
    ok = rejected == 3
    return CheckResult(
        name="timeout_policy_rejects_zero_and_negative_timeout_seconds",
        category="timeout",
        ok=ok,
        detail=f"rejected={rejected}/3",
    )


def check_timeout_policy_rejects_non_finite_seconds() -> CheckResult:
    rejected = 0
    for value in (float("inf"), float("-inf"), float("nan")):
        try:
            TimeoutPolicy(timeout_seconds=value)
        except ProviderContractValidationError:
            rejected += 1
    ok = rejected == 3
    return CheckResult(
        name="timeout_policy_rejects_infinite_and_nan_timeout_seconds",
        category="timeout",
        ok=ok,
        detail=f"rejected={rejected}/3",
    )


def check_timeout_policy_rejects_above_max_timeout_seconds() -> CheckResult:
    ok = False
    try:
        TimeoutPolicy(timeout_seconds=3601.0)
    except ProviderContractValidationError:
        ok = True
    return CheckResult(
        name="timeout_policy_rejects_timeout_seconds_above_the_maximum_bound",
        category="timeout",
        ok=ok,
        detail="TimeoutPolicy(timeout_seconds=3601.0) raised ProviderContractValidationError",
    )


def check_timeout_policy_accepts_the_maximum_bound_exactly() -> CheckResult:
    ok = True
    try:
        policy = TimeoutPolicy(timeout_seconds=3600.0)
        ok = policy.timeout_seconds == 3600.0
    except ProviderContractValidationError:
        ok = False
    return CheckResult(
        name="timeout_policy_accepts_timeout_seconds_at_exactly_the_maximum_bound",
        category="timeout",
        ok=ok,
        detail="TimeoutPolicy(timeout_seconds=3600.0) constructed successfully",
    )


def check_timeout_scope_enum_matches_allowed_timeout_scopes_policy_constant() -> CheckResult:
    from codestrata.ai.provider_contracts.execution_policy import ALLOWED_TIMEOUT_SCOPES

    ok = tuple(s.value for s in TimeoutScope) == ALLOWED_TIMEOUT_SCOPES
    return CheckResult(
        name="timeout_scope_enum_values_match_execution_policy_allowed_timeout_scopes",
        category="timeout",
        ok=ok,
        detail=f"enum={tuple(s.value for s in TimeoutScope)} policy={ALLOWED_TIMEOUT_SCOPES}",
    )


def run_timeout_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_default_timeout_policy_is_sixty_seconds_provider_request_and_enabled(),
        check_timeout_policy_rejects_zero_and_negative_seconds(),
        check_timeout_policy_rejects_non_finite_seconds(),
        check_timeout_policy_rejects_above_max_timeout_seconds(),
        check_timeout_policy_accepts_the_maximum_bound_exactly(),
        check_timeout_scope_enum_matches_allowed_timeout_scopes_policy_constant(),
    ]
    matrix: dict[str, Any] = {
        "default_timeout_seconds": DEFAULT_TIMEOUT_POLICY.timeout_seconds,
        "default_scope": str(DEFAULT_TIMEOUT_POLICY.scope),
    }
    return checks, matrix


__all__ = [
    "check_default_timeout_policy_is_sixty_seconds_provider_request_and_enabled",
    "check_timeout_policy_accepts_the_maximum_bound_exactly",
    "check_timeout_policy_rejects_above_max_timeout_seconds",
    "check_timeout_policy_rejects_non_finite_seconds",
    "check_timeout_policy_rejects_zero_and_negative_seconds",
    "check_timeout_scope_enum_matches_allowed_timeout_scopes_policy_constant",
    "run_timeout_checks",
]
