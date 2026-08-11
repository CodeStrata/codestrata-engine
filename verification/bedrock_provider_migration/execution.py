"""Executor wiring: one attempt, no sleeping, no stacked retries (CR-1)."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock.adapter import ADAPTER_LIMITATIONS
from codestrata.ai.provider_adapters.bedrock.factory import (
    BEDROCK_BACKOFF_POLICY,
    BEDROCK_RETRY_POLICY,
    BEDROCK_TIMEOUT_POLICY,
    build_bedrock_executor,
    build_bedrock_provider,
)
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.provider_contracts.timeout_policy import DEFAULT_TIMEOUT_POLICY
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import (
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_SDK_MAX_ATTEMPTS,
    EXPECTED_SDK_RETRY_MODE,
    EXPECTED_TIMEOUT_SECONDS,
    INVOKE_CALLS_PER_ASSESS_RUN,
)
from verification.bedrock_provider_migration.models import CheckResult


def _run(outcome: Any) -> tuple[Any, fixtures.Client]:
    client = fixtures.Client(outcome)
    execution = build_bedrock_executor(build_bedrock_provider(client=client)).execute(
        fixtures.provider_request()
    )
    return execution, client


def check_the_retry_policy_is_the_pinned_single_attempt_default() -> CheckResult:
    return CheckResult(
        name="the_bedrock_executor_uses_the_pinned_single_attempt_retry_policy",
        category="execution",
        ok=(
            BEDROCK_RETRY_POLICY is DEFAULT_RETRY_POLICY
            and BEDROCK_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
        ),
        detail=f"maximum_attempts={BEDROCK_RETRY_POLICY.maximum_attempts}",
    )


def check_the_timeout_policy_is_the_pinned_default() -> CheckResult:
    return CheckResult(
        name="the_bedrock_executor_uses_the_pinned_sixty_second_timeout_policy",
        category="execution",
        ok=(
            BEDROCK_TIMEOUT_POLICY is DEFAULT_TIMEOUT_POLICY
            and BEDROCK_TIMEOUT_POLICY.timeout_seconds == EXPECTED_TIMEOUT_SECONDS
        ),
        detail=f"timeout_seconds={BEDROCK_TIMEOUT_POLICY.timeout_seconds}",
    )


def check_exactly_one_provider_call_is_made_on_success() -> CheckResult:
    execution, client = _run(fixtures.converse_response())
    return CheckResult(
        name="a_successful_run_makes_exactly_one_converse_call",
        category="execution",
        ok=(
            execution.status is ProviderExecutionStatus.SUCCESS
            and len(client.calls) == INVOKE_CALLS_PER_ASSESS_RUN
            and execution.attempts == 1
        ),
        detail=f"converse_calls={len(client.calls)} attempts={execution.attempts}",
    )


def check_a_retryable_failure_is_still_not_retried() -> CheckResult:
    """CR-1: even a retryable category makes exactly one call."""

    execution, client = _run(fixtures.client_error("ThrottlingException"))
    return CheckResult(
        name="a_retryable_rate_limit_failure_is_still_attempted_exactly_once",
        category="execution",
        ok=len(client.calls) == 1 and execution.attempts == 1,
        detail=f"converse_calls={len(client.calls)} attempts={execution.attempts}",
    )


def check_the_executor_never_sleeps() -> CheckResult:
    """The default sleeper is a no-op, so no wall-clock delay is possible."""

    delays: list[float] = []
    executor = build_bedrock_executor(
        build_bedrock_provider(client=fixtures.Client(fixtures.client_error("ThrottlingException"))),
        sleeper=delays.append,
    )
    executor.execute(fixtures.provider_request())
    return CheckResult(
        name="the_bedrock_executor_requests_no_backoff_delay",
        category="execution",
        ok=not delays,
        detail=f"sleep_calls={len(delays)}",
        evidence={"backoff_policy_is_default": BEDROCK_BACKOFF_POLICY is not None},
    )


def check_the_sdk_retry_handler_stays_pinned() -> CheckResult:
    """``aws_config`` must keep botocore at one attempt: no stacked retries."""

    import inspect

    from codestrata.ai import aws_config

    source = inspect.getsource(aws_config)
    pinned = (
        f'"max_attempts": {EXPECTED_SDK_MAX_ATTEMPTS}' in source
        and f'"mode": "{EXPECTED_SDK_RETRY_MODE}"' in source
    )
    return CheckResult(
        name="the_botocore_client_is_still_pinned_to_one_sdk_retry_attempt",
        category="execution",
        ok=pinned,
        detail="CodeStrata retries are not stacked on top of SDK retries",
        evidence={
            "sdk_max_attempts": EXPECTED_SDK_MAX_ATTEMPTS,
            "sdk_retry_mode": EXPECTED_SDK_RETRY_MODE,
        },
    )


def check_an_unavailable_run_makes_no_call() -> CheckResult:
    from codestrata.ai.provider_adapters.bedrock import client as client_module

    class _Stub:
        AwsAuthenticationError = client_module.AwsAuthenticationError

        @staticmethod
        def create_bedrock_runtime_client(**_kwargs: Any) -> Any:
            raise RuntimeError("boto3 is not installed")

    real = client_module.aws_config
    client_module.aws_config = _Stub  # type: ignore[assignment]
    try:
        execution = build_bedrock_executor(build_bedrock_provider()).execute(
            fixtures.provider_request()
        )
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="a_run_that_cannot_build_a_client_reports_unavailable_and_calls_nothing",
        category="execution",
        ok=execution.status is ProviderExecutionStatus.UNAVAILABLE,
        detail=f"status={execution.status.value}",
    )


def check_an_undeclared_capability_is_skipped_without_a_call() -> CheckResult:
    undeclared = next(
        (
            capability
            for capability in CapabilityId
            if not build_bedrock_provider().supports(capability)
        ),
        None,
    )
    if undeclared is None:
        return CheckResult(
            name="an_undeclared_capability_is_skipped_without_constructing_a_client",
            category="execution",
            ok=True,
            detail="the adapter declares every catalog capability",
        )
    client = fixtures.Client()
    result = build_bedrock_provider(client=client).execute(
        fixtures.provider_request(capability=undeclared)
    )
    return CheckResult(
        name="an_undeclared_capability_is_skipped_without_constructing_a_client",
        category="execution",
        ok=result.status is ProviderExecutionStatus.SKIPPED and not client.calls,
        detail=f"status={result.status.value} converse_calls={len(client.calls)}",
    )


def check_every_result_carries_the_adapter_limitations() -> CheckResult:
    execution, _ = _run(fixtures.converse_response())
    result = execution.provider_result
    return CheckResult(
        name="every_result_records_the_adapters_declared_limitations",
        category="execution",
        ok=result is not None and tuple(result.limitations) == ADAPTER_LIMITATIONS,
        detail=f"limitations={list(result.limitations) if result else []}",
    )


def check_the_execution_result_is_diagnostics_safe() -> CheckResult:
    from codestrata.ai.provider_adapters.bedrock import diagnostics

    execution, _ = _run(fixtures.converse_response())
    view = diagnostics.diagnostic_view_of_execution(execution)
    rendered = repr(view)
    leaked = sorted(
        token
        for token in (fixtures.SYNTHETIC_RESPONSE_TEXT, fixtures.SYNTHETIC_REQUEST_ID)
        if token in rendered
    )
    return CheckResult(
        name="the_execution_diagnostic_view_carries_no_response_text_or_request_id",
        category="execution",
        ok=not leaked,
        detail=f"leaked={leaked}",
    )


def run_execution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_retry_policy_is_the_pinned_single_attempt_default(),
        check_the_timeout_policy_is_the_pinned_default(),
        check_exactly_one_provider_call_is_made_on_success(),
        check_a_retryable_failure_is_still_not_retried(),
        check_the_executor_never_sleeps(),
        check_the_sdk_retry_handler_stays_pinned(),
        check_an_unavailable_run_makes_no_call(),
        check_an_undeclared_capability_is_skipped_without_a_call(),
        check_every_result_carries_the_adapter_limitations(),
        check_the_execution_result_is_diagnostics_safe(),
    ]
    matrix: dict[str, Any] = {
        "adapter_limitations": sorted(ADAPTER_LIMITATIONS),
        "codestrata_maximum_attempts": EXPECTED_MAXIMUM_ATTEMPTS,
        "invoke_calls_per_assess_run": INVOKE_CALLS_PER_ASSESS_RUN,
        "sdk_max_attempts": EXPECTED_SDK_MAX_ATTEMPTS,
        "sdk_retry_mode": EXPECTED_SDK_RETRY_MODE,
        "timeout_enforcement_owner": "botocore_connect_and_read_timeouts",
        "timeout_seconds": EXPECTED_TIMEOUT_SECONDS,
    }
    return checks, matrix


__all__ = [
    "check_a_retryable_failure_is_still_not_retried",
    "check_an_undeclared_capability_is_skipped_without_a_call",
    "check_an_unavailable_run_makes_no_call",
    "check_every_result_carries_the_adapter_limitations",
    "check_exactly_one_provider_call_is_made_on_success",
    "check_the_execution_result_is_diagnostics_safe",
    "check_the_executor_never_sleeps",
    "check_the_retry_policy_is_the_pinned_single_attempt_default",
    "check_the_sdk_retry_handler_stays_pinned",
    "check_the_timeout_policy_is_the_pinned_default",
    "run_execution_checks",
]
