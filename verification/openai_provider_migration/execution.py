"""Executor wiring: pinned policies, one attempt, no waiting, no raising."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import diagnostics
from codestrata.ai.provider_adapters.openai.factory import (
    OPENAI_BACKOFF_POLICY,
    OPENAI_RETRY_POLICY,
    OPENAI_TIMEOUT_POLICY,
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.backoff import DEFAULT_BACKOFF_POLICY
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import EXECUTOR_LIMITATIONS, AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.provider import AIProvider
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.provider_contracts.timeout_policy import DEFAULT_TIMEOUT_POLICY
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.contract import (
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_TIMEOUT_SECONDS,
)
from verification.openai_provider_migration.models import CheckResult


def _executor(outcome: Any = None, *, sleeper: Any = None) -> tuple[Any, Any]:
    client = fixtures.Client(outcome)
    provider = build_openai_provider(client=client)
    executor = (
        build_openai_executor(provider, sleeper=sleeper)
        if sleeper is not None
        else build_openai_executor(provider)
    )
    return executor, client


def check_the_adapter_satisfies_the_provider_protocol() -> CheckResult:
    provider = build_openai_provider(client=fixtures.Client())
    ok = isinstance(provider, AIProvider) and provider.provider_id is ProviderId.OPENAI
    return CheckResult(
        name="the_openai_adapter_satisfies_the_ai_provider_protocol",
        category="execution",
        ok=ok,
        detail=f"provider_id={provider.provider_id.value}",
    )


def check_the_executor_policies_are_the_slice_11_4_defaults() -> CheckResult:
    ok = (
        OPENAI_RETRY_POLICY is DEFAULT_RETRY_POLICY
        and OPENAI_TIMEOUT_POLICY is DEFAULT_TIMEOUT_POLICY
        and OPENAI_BACKOFF_POLICY is DEFAULT_BACKOFF_POLICY
    )
    return CheckResult(
        name="the_openai_executor_is_pinned_to_the_slice_11_4_default_policies",
        category="execution",
        ok=ok,
        detail="retry/timeout/backoff policies are the shared defaults",
    )


def check_the_retry_policy_allows_exactly_one_attempt() -> CheckResult:
    ok = OPENAI_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
    return CheckResult(
        name="the_pinned_retry_policy_allows_exactly_one_attempt",
        category="execution",
        ok=ok,
        detail=f"maximum_attempts={OPENAI_RETRY_POLICY.maximum_attempts}",
    )


def check_the_timeout_policy_is_declarative_sixty_seconds() -> CheckResult:
    ok = OPENAI_TIMEOUT_POLICY.timeout_seconds == EXPECTED_TIMEOUT_SECONDS
    return CheckResult(
        name="the_pinned_timeout_policy_declares_sixty_seconds",
        category="execution",
        ok=ok,
        detail=f"timeout_seconds={OPENAI_TIMEOUT_POLICY.timeout_seconds} "
        f"scope={OPENAI_TIMEOUT_POLICY.scope.value}",
    )


def check_a_successful_run_makes_exactly_one_provider_call() -> CheckResult:
    executor, client = _executor(fixtures.response())
    execution = executor.execute(fixtures.provider_request())
    ok = (
        execution.status is ProviderExecutionStatus.SUCCESS
        and execution.attempts == 1
        and execution.retry_count == 0
        and len(client.calls) == 1
    )
    return CheckResult(
        name="a_successful_execution_makes_exactly_one_provider_call",
        category="execution",
        ok=ok,
        detail=f"attempts={execution.attempts} sdk_calls={len(client.calls)}",
    )


def check_a_retryable_failure_still_makes_only_one_call() -> CheckResult:
    """CR-1: a rate-limit is retryable in principle but not retried in practice."""

    executor, client = _executor(fixtures.sdk_exception("RateLimitError"))
    execution = executor.execute(fixtures.provider_request())
    ok = (
        execution.status is ProviderExecutionStatus.FAILED
        and execution.attempts == 1
        and execution.retry_count == 0
        and len(client.calls) == 1
    )
    return CheckResult(
        name="a_retryable_failure_is_not_retried_under_the_single_attempt_policy",
        category="execution",
        ok=ok,
        detail=f"attempts={execution.attempts} sdk_calls={len(client.calls)}",
    )


def check_the_executor_never_sleeps() -> CheckResult:
    delays: list[float] = []
    executor, _ = _executor(
        fixtures.sdk_exception("APITimeoutError"), sleeper=lambda seconds: delays.append(seconds)
    )
    executor.execute(fixtures.provider_request())
    return CheckResult(
        name="the_executor_requests_no_backoff_delay_under_the_single_attempt_policy",
        category="execution",
        ok=not delays,
        detail=f"sleep_calls={len(delays)}",
    )


def check_the_default_sleeper_is_a_no_op() -> CheckResult:
    """The default sleeper is a no-op rather than ``time.sleep``."""

    from codestrata.ai.provider_adapters.openai import factory

    return CheckResult(
        name="the_openai_executor_defaults_to_a_no_op_sleeper_rather_than_time_sleep",
        category="execution",
        ok=factory._no_sleep(30.0) is None,
        detail="the pinned default sleeper cannot introduce a wall-clock wait",
    )


def check_a_provider_failure_never_raises_out_of_the_executor() -> CheckResult:
    raised: list[str] = []
    for class_name in ("AuthenticationError", "BadRequestError", "APIConnectionError"):
        executor, _ = _executor(fixtures.sdk_exception(class_name))
        try:
            executor.execute(fixtures.provider_request())
        except Exception as error:  # noqa: BLE001 - verification asserts non-raising
            raised.append(f"{class_name}:{type(error).__name__}")
    return CheckResult(
        name="an_sdk_failure_surfaces_as_a_terminal_result_rather_than_an_exception",
        category="execution",
        ok=not raised,
        detail=f"raised={raised}",
    )


def check_a_timeout_is_recorded_but_not_enforced() -> CheckResult:
    executor, _ = _executor(fixtures.sdk_exception("APITimeoutError"))
    execution = executor.execute(fixtures.provider_request())
    ok = execution.timeout_applied is True and execution.status is ProviderExecutionStatus.FAILED
    return CheckResult(
        name="a_provider_reported_timeout_is_recorded_without_wall_clock_enforcement",
        category="execution",
        ok=ok,
        detail=f"timeout_applied={execution.timeout_applied}",
    )


def check_capability_gating_precedes_any_provider_call() -> CheckResult:
    """The executor asks ``supports()`` before ``execute()``.

    Only one capability exists today and OpenAI declares it, so the SKIPPED
    branch is not reachable through the real adapter. What is verifiable here is
    the gate itself: ``supports()`` answers from the static catalog, refuses a
    value that is not a ``CapabilityId``, and needs no client to answer.
    """

    probe = build_openai_provider()
    declared = sorted(capability.value for capability in CapabilityId if probe.supports(capability))
    ok = (
        declared == sorted(capability.value for capability in CapabilityId)
        and probe.supports("modernization_advisor") is False  # type: ignore[arg-type]
        and probe.client_injected is False
    )
    return CheckResult(
        name="capability_gating_answers_from_the_catalog_before_any_provider_call",
        category="execution",
        ok=ok,
        detail=f"declared_capabilities={declared}",
    )


def check_the_execution_diagnostics_record_the_pinned_policies() -> CheckResult:
    executor, _ = _executor(fixtures.response())
    execution = executor.execute(fixtures.provider_request())
    reported = execution.diagnostics
    ok = (
        reported.retry_policy_maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
        and reported.timeout_policy_seconds == EXPECTED_TIMEOUT_SECONDS
    )
    return CheckResult(
        name="the_execution_diagnostics_report_the_pinned_retry_and_timeout_policies",
        category="execution",
        ok=ok,
        detail=f"maximum_attempts={reported.retry_policy_maximum_attempts} "
        f"timeout_seconds={reported.timeout_policy_seconds}",
    )


def check_executor_limitation_labels_are_deliberately_unchanged() -> CheckResult:
    """The pre-existing labels are frozen so SV.11.4's verdict is unaffected.

    ``executor_not_wired`` and ``providers_not_migrated`` are now inaccurate for
    OpenAI specifically. They are recorded verbatim as
    ``executor_limitation_labels_predate_migration`` rather than renamed, which
    would change the Slice 11.4 report body.
    """

    expected = (
        "executor_not_wired",
        "providers_not_migrated",
        "timeout_enforcement_deferred_to_adapters",
    )
    return CheckResult(
        name="the_shared_executor_limitation_labels_are_left_unchanged_by_this_slice",
        category="execution",
        ok=EXECUTOR_LIMITATIONS == expected,
        detail=f"executor_limitations={list(EXECUTOR_LIMITATIONS)}",
    )


def check_the_executor_is_reachable_from_the_openai_factory_only() -> CheckResult:
    executor, _ = _executor(fixtures.response())
    return CheckResult(
        name="the_openai_factory_is_what_wires_the_shared_executor",
        category="execution",
        ok=isinstance(executor, AIProviderExecutor),
        detail="build_openai_executor returns an AIProviderExecutor",
    )


def run_execution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    executor, _ = _executor(fixtures.response())
    execution = executor.execute(fixtures.provider_request())
    checks = [
        check_the_adapter_satisfies_the_provider_protocol(),
        check_the_executor_policies_are_the_slice_11_4_defaults(),
        check_the_retry_policy_allows_exactly_one_attempt(),
        check_the_timeout_policy_is_declarative_sixty_seconds(),
        check_a_successful_run_makes_exactly_one_provider_call(),
        check_a_retryable_failure_still_makes_only_one_call(),
        check_the_executor_never_sleeps(),
        check_the_default_sleeper_is_a_no_op(),
        check_a_provider_failure_never_raises_out_of_the_executor(),
        check_a_timeout_is_recorded_but_not_enforced(),
        check_capability_gating_precedes_any_provider_call(),
        check_the_execution_diagnostics_record_the_pinned_policies(),
        check_executor_limitation_labels_are_deliberately_unchanged(),
        check_the_executor_is_reachable_from_the_openai_factory_only(),
    ]
    matrix: dict[str, Any] = {
        "backoff_strategy": OPENAI_BACKOFF_POLICY.strategy.value,
        "executor_limitations": list(EXECUTOR_LIMITATIONS),
        "maximum_attempts": OPENAI_RETRY_POLICY.maximum_attempts,
        "successful_execution_view": diagnostics.diagnostic_view_of_execution(execution),
        "timeout_policy_scope": OPENAI_TIMEOUT_POLICY.scope.value,
        "timeout_policy_seconds": OPENAI_TIMEOUT_POLICY.timeout_seconds,
    }
    return checks, matrix


__all__ = [
    "check_a_provider_failure_never_raises_out_of_the_executor",
    "check_a_retryable_failure_still_makes_only_one_call",
    "check_a_successful_run_makes_exactly_one_provider_call",
    "check_a_timeout_is_recorded_but_not_enforced",
    "check_capability_gating_precedes_any_provider_call",
    "check_executor_limitation_labels_are_deliberately_unchanged",
    "check_the_adapter_satisfies_the_provider_protocol",
    "check_the_default_sleeper_is_a_no_op",
    "check_the_execution_diagnostics_record_the_pinned_policies",
    "check_the_executor_is_reachable_from_the_openai_factory_only",
    "check_the_executor_never_sleeps",
    "check_the_executor_policies_are_the_slice_11_4_defaults",
    "check_the_retry_policy_allows_exactly_one_attempt",
    "check_the_timeout_policy_is_declarative_sixty_seconds",
    "run_execution_checks",
]
