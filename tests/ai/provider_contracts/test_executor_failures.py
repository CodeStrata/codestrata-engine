"""Tests for ``AIProviderExecutor`` failure paths: non-retryable, contract violations."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from tests.ai.provider_contracts.execution_fakes import (
    FakeAlwaysFailingProvider,
    FakeWrongProviderIdProvider,
    RecordingSleeper,
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
        ErrorCategory.INTERNAL_FAILURE,
    ],
)
def test_executor_never_retries_a_non_retryable_category_even_with_budget(
    category: ErrorCategory,
) -> None:
    provider = FakeAlwaysFailingProvider(category=category)
    executor = AIProviderExecutor(
        provider,
        sleeper=RecordingSleeper(),
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
    )
    result = executor.execute(_request())
    assert result.status is ProviderExecutionStatus.FAILED
    assert result.attempts == 1
    assert provider.call_count == 1
    assert result.terminal_error_category is category


def test_executor_terminal_result_carries_matching_provider_result() -> None:
    provider = FakeAlwaysFailingProvider(category=ErrorCategory.INVALID_REQUEST)
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.provider_result is not None
    assert result.provider_result.status is ProviderExecutionStatus.FAILED
    assert result.provider_result.error is not None
    assert result.provider_result.error.category is ErrorCategory.INVALID_REQUEST


def test_executor_raises_on_provider_id_mismatch_between_provider_and_result() -> None:
    provider = FakeWrongProviderIdProvider()
    executor = AIProviderExecutor(provider)
    with pytest.raises(ProviderContractValidationError):
        executor.execute(_request())


def test_executor_never_leaks_the_error_detail_text_beyond_what_the_provider_supplied() -> None:
    """The executor must not append or fabricate additional unsafe detail text."""

    provider = FakeAlwaysFailingProvider(category=ErrorCategory.INVALID_REQUEST, code="safe_code")
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.provider_result is not None
    assert result.provider_result.error is not None
    assert result.provider_result.error.code == "safe_code"
    assert "/Users/" not in result.provider_result.error.detail
    assert "Traceback" not in result.provider_result.error.detail
