"""Tests for ``AIProviderExecutor`` happy paths: skip, first-try success, retry-then-success."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, BackoffStrategy
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from tests.ai.provider_contracts.execution_fakes import (
    FakeRetryableThenSucceedingProvider,
    RecordingSleeper,
)
from tests.ai.provider_contracts.fakes import (
    FakeFailingProvider,
    FakeSucceedingProvider,
    FakeUnavailableProvider,
)


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="advise", context_payload_text="context"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("fake-model"),
    )


def test_executor_returns_skipped_without_invoking_execute_when_capability_unsupported() -> None:
    provider = FakeUnavailableProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.SKIPPED
    assert result.provider_result is None
    assert result.attempts == 0
    assert result.retry_count == 0
    assert result.terminal_error_category is None


def test_executor_succeeds_on_first_attempt_with_default_policy() -> None:
    provider = FakeSucceedingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.SUCCESS
    assert result.attempts == 1
    assert result.retry_count == 0
    assert result.provider_result is not None
    assert result.usage is not None


def test_executor_default_policy_makes_exactly_one_attempt_even_on_retryable_failure() -> None:
    provider = FakeFailingProvider()  # PROVIDER_UNAVAILABLE, retryable by default partition
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.FAILED
    assert result.attempts == 1
    assert result.retry_count == 0


def test_executor_retries_a_retryable_failure_until_it_succeeds() -> None:
    provider = FakeRetryableThenSucceedingProvider(fail_count=2)
    sleeper = RecordingSleeper()
    executor = AIProviderExecutor(
        provider,
        sleeper=sleeper,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
        backoff_policy=BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=0.1),
    )
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.SUCCESS
    assert result.attempts == 3
    assert result.retry_count == 2
    assert provider.call_count == 3
    assert sleeper.calls == [0.1, 0.1]


def test_executor_stops_retrying_once_maximum_attempts_reached() -> None:
    provider = FakeRetryableThenSucceedingProvider(fail_count=10)
    executor = AIProviderExecutor(
        provider,
        sleeper=RecordingSleeper(),
        retry_policy=AIProviderRetryPolicy(maximum_attempts=3),
    )
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.FAILED
    assert result.attempts == 3
    assert result.retry_count == 2
    assert provider.call_count == 3


def test_executor_records_timeout_applied_when_timeout_category_observed() -> None:
    provider = FakeRetryableThenSucceedingProvider(
        fail_count=1, category=ErrorCategory.TIMEOUT
    )
    executor = AIProviderExecutor(
        provider, sleeper=RecordingSleeper(), retry_policy=AIProviderRetryPolicy(maximum_attempts=3)
    )
    result = executor.execute(_request())
    assert result.timeout_applied is True


def test_executor_does_not_record_timeout_applied_when_no_timeout_observed() -> None:
    provider = FakeSucceedingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.timeout_applied is False


def test_executor_records_limitations_on_every_result() -> None:
    provider = FakeSucceedingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert "executor_not_wired" in result.limitations
    assert "providers_not_migrated" in result.limitations
    assert "timeout_enforcement_deferred_to_adapters" in result.limitations


def test_executor_rejects_non_request_argument() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    with pytest.raises(ProviderContractValidationError):
        executor.execute("not-a-request")  # type: ignore[arg-type]


def test_executor_rejects_non_provider_argument() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor("not-a-provider")  # type: ignore[arg-type]


def test_executor_rejects_invalid_policy_arguments() -> None:
    provider = FakeSucceedingProvider()
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor(provider, timeout_policy="not-a-policy")  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor(provider, retry_policy="not-a-policy")  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor(provider, backoff_policy="not-a-policy")  # type: ignore[arg-type]


def test_executor_rejects_non_callable_clock_and_sleeper() -> None:
    provider = FakeSucceedingProvider()
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor(provider, clock="not-callable")  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        AIProviderExecutor(provider, sleeper="not-callable")  # type: ignore[arg-type]


def test_executor_result_provider_id_matches_wrapped_provider() -> None:
    provider = FakeSucceedingProvider(provider_id=ProviderId.BEDROCK)
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.provider_id is ProviderId.BEDROCK
