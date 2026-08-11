"""Verifies ``retry_policy``/``retry_decision``/``backoff``: bounded, deterministic, sleep-free."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.backoff import (
    BackoffPolicy,
    BackoffStrategy,
    compute_backoff_delay,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.retry_decision import decide_retry
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    SETTINGS_REPRESENTABLE_RETRY_POLICY,
    AIProviderRetryPolicy,
    max_retries_to_maximum_attempts,
)
from verification.ai_provider_execution.models import CheckResult


def check_max_retries_to_maximum_attempts_adds_one() -> CheckResult:
    ok = (
        max_retries_to_maximum_attempts(0) == 1
        and max_retries_to_maximum_attempts(3) == 4
        and max_retries_to_maximum_attempts(9) == 10
    )
    return CheckResult(
        name="max_retries_to_maximum_attempts_always_adds_exactly_one",
        category="retries",
        ok=ok,
        detail="0->1, 3->4, 9->10",
    )


def check_max_retries_to_maximum_attempts_rejects_negative_input() -> CheckResult:
    ok = False
    try:
        max_retries_to_maximum_attempts(-1)
    except ProviderContractValidationError:
        ok = True
    return CheckResult(
        name="max_retries_to_maximum_attempts_rejects_a_negative_max_retries",
        category="retries",
        ok=ok,
        detail="max_retries_to_maximum_attempts(-1) raised ProviderContractValidationError",
    )


def check_default_retry_policy_is_maximum_attempts_one() -> CheckResult:
    ok = DEFAULT_RETRY_POLICY.maximum_attempts == 1
    return CheckResult(
        name="default_retry_policy_has_maximum_attempts_of_one",
        category="retries",
        ok=ok,
        detail=f"maximum_attempts={DEFAULT_RETRY_POLICY.maximum_attempts}",
    )


def check_settings_representable_retry_policy_is_maximum_attempts_four() -> CheckResult:
    ok = SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts == 4
    return CheckResult(
        name="settings_representable_retry_policy_has_maximum_attempts_of_four",
        category="retries",
        ok=ok,
        detail=f"maximum_attempts={SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts}",
    )


def check_retry_policy_rejects_zero_maximum_attempts() -> CheckResult:
    ok = False
    try:
        AIProviderRetryPolicy(maximum_attempts=0)
    except ProviderContractValidationError:
        ok = True
    return CheckResult(
        name="retry_policy_rejects_zero_maximum_attempts",
        category="retries",
        ok=ok,
        detail="AIProviderRetryPolicy(maximum_attempts=0) raised ProviderContractValidationError",
    )


def check_decide_retry_stops_at_maximum_attempts() -> CheckResult:
    policy = AIProviderRetryPolicy(maximum_attempts=2)
    decision = decide_retry(
        attempt=2,
        category=ErrorCategory.TIMEOUT,
        retry_policy=policy,
        backoff_policy=BackoffPolicy(),
    )
    ok = decision.should_retry is False and decision.terminal is True
    return CheckResult(
        name="decide_retry_stops_when_maximum_attempts_is_reached",
        category="retries",
        ok=ok,
        detail=f"reason_code={decision.reason_code}",
    )


def check_decide_retry_stops_for_non_retryable_category() -> CheckResult:
    policy = AIProviderRetryPolicy(maximum_attempts=5)
    decision = decide_retry(
        attempt=1,
        category=ErrorCategory.AUTHENTICATION_FAILED,
        retry_policy=policy,
        backoff_policy=BackoffPolicy(),
    )
    ok = decision.should_retry is False and decision.terminal is True
    return CheckResult(
        name="decide_retry_stops_for_a_non_retryable_error_category",
        category="retries",
        ok=ok,
        detail=f"reason_code={decision.reason_code}",
    )


def check_decide_retry_schedules_a_retry_for_a_retryable_category_within_budget() -> CheckResult:
    policy = AIProviderRetryPolicy(maximum_attempts=3)
    decision = decide_retry(
        attempt=1,
        category=ErrorCategory.TIMEOUT,
        retry_policy=policy,
        backoff_policy=BackoffPolicy(),
    )
    ok = decision.should_retry is True and decision.terminal is False and decision.next_attempt == 2
    return CheckResult(
        name="decide_retry_schedules_a_retry_for_a_retryable_category_within_budget",
        category="retries",
        ok=ok,
        detail=f"next_attempt={decision.next_attempt} should_retry={decision.should_retry}",
    )


def check_decide_retry_never_sleeps() -> CheckResult:
    """decide_retry is a pure function: it never calls time.sleep or any injected sleeper."""

    import inspect

    source = inspect.getsource(decide_retry)
    ok = "sleep(" not in source
    return CheckResult(
        name="decide_retry_source_never_calls_sleep",
        category="retries",
        ok=ok,
        detail="'sleep(' token absent from decide_retry source",
    )


def check_backoff_none_strategy_always_returns_zero() -> CheckResult:
    policy = BackoffPolicy(strategy=BackoffStrategy.NONE)
    delays = [compute_backoff_delay(policy, attempt) for attempt in range(1, 6)]
    ok = all(delay == 0.0 for delay in delays)
    return CheckResult(
        name="backoff_none_strategy_always_returns_zero_delay",
        category="retries",
        ok=ok,
        detail=f"delays={delays}",
    )


def check_backoff_fixed_strategy_is_constant() -> CheckResult:
    policy = BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=2.0)
    delays = [compute_backoff_delay(policy, attempt) for attempt in range(1, 6)]
    ok = all(delay == 2.0 for delay in delays)
    return CheckResult(
        name="backoff_fixed_strategy_returns_a_constant_delay",
        category="retries",
        ok=ok,
        detail=f"delays={delays}",
    )


def check_backoff_exponential_strategy_grows_and_is_capped() -> CheckResult:
    policy = BackoffPolicy(
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay_seconds=1.0,
        multiplier=2.0,
        max_delay_seconds=10.0,
    )
    delays = [compute_backoff_delay(policy, attempt) for attempt in range(1, 6)]
    ok = delays == [1.0, 2.0, 4.0, 8.0, 10.0]
    return CheckResult(
        name="backoff_exponential_strategy_grows_and_is_capped_at_max_delay_seconds",
        category="retries",
        ok=ok,
        detail=f"delays={delays}",
    )


def check_backoff_delay_is_deterministic_across_repeated_calls() -> CheckResult:
    policy = BackoffPolicy(
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay_seconds=0.5,
        multiplier=1.5,
        jitter=True,
    )
    first = [compute_backoff_delay(policy, attempt) for attempt in range(1, 6)]
    second = [compute_backoff_delay(policy, attempt) for attempt in range(1, 6)]
    ok = first == second
    return CheckResult(
        name="backoff_delay_with_jitter_enabled_is_still_deterministic_given_the_same_attempt",
        category="retries",
        ok=ok,
        detail=f"first={first} second={second}",
    )


def check_default_backoff_jitter_is_disabled() -> CheckResult:
    ok = BackoffPolicy().jitter is False
    return CheckResult(
        name="default_backoff_policy_has_jitter_disabled",
        category="retries",
        ok=ok,
        detail=f"jitter={BackoffPolicy().jitter}",
    )


def check_backoff_never_sleeps() -> CheckResult:
    """AST-based (not docstring-fooled): backoff.py never imports time or calls sleep()."""

    import ast
    import inspect

    from codestrata.ai.provider_contracts import backoff as backoff_module

    source = inspect.getsource(backoff_module)
    tree = ast.parse(source, filename="backoff.py")
    imports_time = any(
        (isinstance(node, ast.Import) and any(alias.name == "time" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "time")
        for node in ast.walk(tree)
    )
    calls_sleep = any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "sleep")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "sleep")
        )
        for node in ast.walk(tree)
    )
    ok = not imports_time and not calls_sleep
    return CheckResult(
        name="backoff_module_never_imports_time_or_calls_sleep",
        category="retries",
        ok=ok,
        detail=f"imports_time={imports_time} calls_sleep={calls_sleep}",
    )


def run_retry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_max_retries_to_maximum_attempts_adds_one(),
        check_max_retries_to_maximum_attempts_rejects_negative_input(),
        check_default_retry_policy_is_maximum_attempts_one(),
        check_settings_representable_retry_policy_is_maximum_attempts_four(),
        check_retry_policy_rejects_zero_maximum_attempts(),
        check_decide_retry_stops_at_maximum_attempts(),
        check_decide_retry_stops_for_non_retryable_category(),
        check_decide_retry_schedules_a_retry_for_a_retryable_category_within_budget(),
        check_decide_retry_never_sleeps(),
        check_backoff_none_strategy_always_returns_zero(),
        check_backoff_fixed_strategy_is_constant(),
        check_backoff_exponential_strategy_grows_and_is_capped(),
        check_backoff_delay_is_deterministic_across_repeated_calls(),
        check_default_backoff_jitter_is_disabled(),
        check_backoff_never_sleeps(),
    ]
    matrix: dict[str, Any] = {
        "default_retry_policy_maximum_attempts": DEFAULT_RETRY_POLICY.maximum_attempts,
        "settings_representable_retry_policy_maximum_attempts": (
            SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts
        ),
    }
    return checks, matrix


__all__ = [
    "check_backoff_delay_is_deterministic_across_repeated_calls",
    "check_backoff_exponential_strategy_grows_and_is_capped",
    "check_backoff_fixed_strategy_is_constant",
    "check_backoff_never_sleeps",
    "check_backoff_none_strategy_always_returns_zero",
    "check_decide_retry_never_sleeps",
    "check_decide_retry_schedules_a_retry_for_a_retryable_category_within_budget",
    "check_decide_retry_stops_at_maximum_attempts",
    "check_decide_retry_stops_for_non_retryable_category",
    "check_default_backoff_jitter_is_disabled",
    "check_default_retry_policy_is_maximum_attempts_one",
    "check_max_retries_to_maximum_attempts_adds_one",
    "check_max_retries_to_maximum_attempts_rejects_negative_input",
    "check_retry_policy_rejects_zero_maximum_attempts",
    "check_settings_representable_retry_policy_is_maximum_attempts_four",
    "run_retry_checks",
]
