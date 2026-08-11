"""Verifies ``AIProviderExecutor``: fail-soft, retry/backoff loop, contract validation.

Defines tiny, self-contained fake ``AIProvider`` implementations directly in
this module (never importing ``engine/tests/...`` — the verification tree
must not depend on the test tree) purely to exercise the executor's control
flow deterministically and offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, BackoffStrategy
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import EXECUTOR_LIMITATIONS, AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from verification.ai_provider_execution.models import CheckResult


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="advise", context_payload_text="context"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("verification-fake-model"),
    )


@dataclass
class _FakeSucceedingProvider:
    provider_id: ProviderId = ProviderId.BEDROCK
    call_count: int = field(default=0, init=False)

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="ok"),
        )


@dataclass
class _FakeAlwaysFailingProvider:
    category: ErrorCategory
    provider_id: ProviderId = ProviderId.BEDROCK
    call_count: int = field(default=0, init=False)

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.FAILED,
            error=AIProviderError(category=self.category, code=f"{self.category.value}_always"),
        )


@dataclass
class _FakeRetryableThenSucceedingProvider:
    fail_count: int
    provider_id: ProviderId = ProviderId.BEDROCK
    call_count: int = field(default=0, init=False)

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            return AIProviderResult(
                provider_id=self.provider_id,
                capability=request.capability,
                status=ProviderExecutionStatus.UNAVAILABLE,
                error=AIProviderError(category=ErrorCategory.PROVIDER_UNAVAILABLE, code="down"),
            )
        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="ok"),
        )


@dataclass
class _FakeUnsupportedProvider:
    provider_id: ProviderId = ProviderId.OPENAI
    call_count: int = field(default=0, init=False)

    def supports(self, capability: CapabilityId) -> bool:
        return False

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        raise AssertionError("execute() must never be called when supports() is False")


@dataclass
class _FakeRaisingProvider:
    provider_id: ProviderId = ProviderId.BEDROCK

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        raise RuntimeError(f"fake-secret-should-never-leak-{id(self)}")


class _RecordingSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def check_executor_skips_when_provider_does_not_support_capability() -> CheckResult:
    provider = _FakeUnsupportedProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    ok = (
        result.status is ProviderExecutionStatus.SKIPPED
        and result.attempts == 0
        and provider.call_count == 0
    )
    return CheckResult(
        name="executor_skips_without_invoking_execute_when_supports_returns_false",
        category="executor",
        ok=ok,
        detail=f"status={result.status} attempts={result.attempts} calls={provider.call_count}",
    )


def check_executor_returns_success_on_first_try_by_default() -> CheckResult:
    provider = _FakeSucceedingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    ok = (
        result.status is ProviderExecutionStatus.SUCCESS
        and result.attempts == 1
        and result.retry_count == 0
        and provider.call_count == 1
    )
    return CheckResult(
        name="executor_returns_success_on_first_try_with_default_retry_policy",
        category="executor",
        ok=ok,
        detail=f"attempts={result.attempts} calls={provider.call_count}",
    )


def check_executor_never_raises_for_a_failed_result() -> CheckResult:
    provider = _FakeAlwaysFailingProvider(category=ErrorCategory.INVALID_MODEL)
    executor = AIProviderExecutor(provider)
    raised = False
    result = None
    try:
        result = executor.execute(_request())
    except Exception:  # noqa: BLE001 - intentional: proving no exception escapes
        raised = True
    ok = not raised and result is not None and result.status is ProviderExecutionStatus.FAILED
    return CheckResult(
        name="executor_never_raises_for_a_failed_provider_result",
        category="executor",
        ok=ok,
        detail=f"raised={raised} status={result.status if result else None}",
    )


def check_executor_retries_a_retryable_category_until_success() -> CheckResult:
    provider = _FakeRetryableThenSucceedingProvider(fail_count=2)
    sleeper = _RecordingSleeper()
    executor = AIProviderExecutor(
        provider,
        sleeper=sleeper,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
        backoff_policy=BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=0.01),
    )
    result = executor.execute(_request())
    ok = (
        result.status is ProviderExecutionStatus.SUCCESS
        and result.attempts == 3
        and result.retry_count == 2
        and len(sleeper.calls) == 2
    )
    return CheckResult(
        name="executor_retries_a_retryable_category_until_success",
        category="executor",
        ok=ok,
        detail=f"attempts={result.attempts} sleeper_calls={len(sleeper.calls)}",
    )


def check_executor_does_not_retry_a_non_retryable_category() -> CheckResult:
    provider = _FakeAlwaysFailingProvider(category=ErrorCategory.AUTHENTICATION_FAILED)
    sleeper = _RecordingSleeper()
    executor = AIProviderExecutor(
        provider,
        sleeper=sleeper,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
    )
    result = executor.execute(_request())
    ok = provider.call_count == 1 and len(sleeper.calls) == 0 and result.attempts == 1
    return CheckResult(
        name="executor_does_not_retry_a_non_retryable_error_category",
        category="executor",
        ok=ok,
        detail=f"calls={provider.call_count} sleeper_calls={len(sleeper.calls)}",
    )


def check_executor_stops_at_maximum_attempts_even_when_retryable() -> CheckResult:
    provider = _FakeAlwaysFailingProvider(category=ErrorCategory.TIMEOUT)
    executor = AIProviderExecutor(
        provider, retry_policy=AIProviderRetryPolicy(maximum_attempts=3)
    )
    result = executor.execute(_request())
    ok = provider.call_count == 3 and result.attempts == 3 and result.retry_count == 2
    return CheckResult(
        name="executor_stops_retrying_once_maximum_attempts_is_reached",
        category="executor",
        ok=ok,
        detail=f"calls={provider.call_count} attempts={result.attempts}",
    )


def check_executor_sets_timeout_applied_when_timeout_category_observed() -> CheckResult:
    provider = _FakeAlwaysFailingProvider(category=ErrorCategory.TIMEOUT)
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    ok = result.timeout_applied is True
    return CheckResult(
        name="executor_records_timeout_applied_when_a_timeout_category_is_observed",
        category="executor",
        ok=ok,
        detail=f"timeout_applied={result.timeout_applied}",
    )


def check_executor_converts_unexpected_exception_to_internal_failure() -> CheckResult:
    from codestrata.ai.provider_contracts.error_classification import (
        UNEXPECTED_EXCEPTION_SAFE_CODE,
    )

    provider = _FakeRaisingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    ok = (
        result.status is ProviderExecutionStatus.FAILED
        and result.terminal_error_category is ErrorCategory.INTERNAL_FAILURE
        and result.provider_result is not None
        and result.provider_result.error is not None
        and result.provider_result.error.code == UNEXPECTED_EXCEPTION_SAFE_CODE
        and "fake-secret" not in repr(result)
    )
    return CheckResult(
        name="executor_converts_an_unexpected_exception_into_an_internal_failure_result",
        category="executor",
        ok=ok,
        detail=f"status={result.status} category={result.terminal_error_category}",
    )


def check_executor_propagates_keyboard_interrupt() -> CheckResult:
    @dataclass
    class _InterruptingProvider:
        provider_id: ProviderId = ProviderId.BEDROCK

        def supports(self, capability: CapabilityId) -> bool:
            return True

        def execute(self, request: AIProviderRequest) -> AIProviderResult:
            raise KeyboardInterrupt("must propagate")

    executor = AIProviderExecutor(_InterruptingProvider())
    propagated = False
    try:
        executor.execute(_request())
    except KeyboardInterrupt:
        propagated = True
    return CheckResult(
        name="executor_does_not_swallow_keyboard_interrupt",
        category="executor",
        ok=propagated,
        detail=f"propagated={propagated}",
    )


def check_executor_raises_on_provider_id_mismatch() -> CheckResult:
    from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

    @dataclass
    class _MismatchedProvider:
        provider_id: ProviderId = ProviderId.BEDROCK

        def supports(self, capability: CapabilityId) -> bool:
            return True

        def execute(self, request: AIProviderRequest) -> AIProviderResult:
            return AIProviderResult(
                provider_id=ProviderId.OPENAI,
                capability=request.capability,
                status=ProviderExecutionStatus.SUCCESS,
                content=AIProviderResultContent(text="ok"),
            )

    executor = AIProviderExecutor(_MismatchedProvider())
    raised = False
    try:
        executor.execute(_request())
    except ProviderContractValidationError:
        raised = True
    return CheckResult(
        name="executor_raises_provider_contract_validation_error_on_provider_id_mismatch",
        category="executor",
        ok=raised,
        detail=f"raised={raised}",
    )


def run_executor_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_executor_skips_when_provider_does_not_support_capability(),
        check_executor_returns_success_on_first_try_by_default(),
        check_executor_never_raises_for_a_failed_result(),
        check_executor_retries_a_retryable_category_until_success(),
        check_executor_does_not_retry_a_non_retryable_category(),
        check_executor_stops_at_maximum_attempts_even_when_retryable(),
        check_executor_sets_timeout_applied_when_timeout_category_observed(),
        check_executor_converts_unexpected_exception_to_internal_failure(),
        check_executor_propagates_keyboard_interrupt(),
        check_executor_raises_on_provider_id_mismatch(),
    ]
    matrix: dict[str, Any] = {"executor_limitations": list(EXECUTOR_LIMITATIONS)}
    return checks, matrix


__all__ = [
    "check_executor_converts_unexpected_exception_to_internal_failure",
    "check_executor_does_not_retry_a_non_retryable_category",
    "check_executor_never_raises_for_a_failed_result",
    "check_executor_propagates_keyboard_interrupt",
    "check_executor_raises_on_provider_id_mismatch",
    "check_executor_retries_a_retryable_category_until_success",
    "check_executor_returns_success_on_first_try_by_default",
    "check_executor_sets_timeout_applied_when_timeout_category_observed",
    "check_executor_skips_when_provider_does_not_support_capability",
    "check_executor_stops_at_maximum_attempts_even_when_retryable",
    "run_executor_checks",
]
