"""Tests for ``AIProviderExecutor``'s unexpected-exception handling and BaseException propagation.

Covers: ``AIProvider.execute()`` raising an ordinary ``Exception`` (a
contract violation) is converted into a safe, fail-soft ``FAILED`` result;
``KeyboardInterrupt``/``SystemExit`` (which do not subclass ``Exception``)
always propagate unmodified, since the executor only catches ``Exception``.
"""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.error_classification import UNEXPECTED_EXCEPTION_SAFE_CODE
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from tests.ai.provider_contracts.execution_fakes import FakeRaisingProvider, RecordingSleeper

_SECRET_TOKEN = "sk-super-secret-token-value"


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="advise", context_payload_text="context"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("fake-model"),
    )


def test_unexpected_exception_is_converted_to_a_failed_result_not_raised() -> None:
    provider = FakeRaisingProvider()
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())  # must not raise
    assert result.status is ProviderExecutionStatus.FAILED
    assert result.terminal_error_category is ErrorCategory.INTERNAL_FAILURE


def test_unexpected_exception_result_uses_the_fixed_safe_code_never_the_message() -> None:
    provider = FakeRaisingProvider(
        exception_factory=lambda: ValueError(f"leaked: {_SECRET_TOKEN}")
    )
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    assert result.provider_result is not None
    assert result.provider_result.error is not None
    assert result.provider_result.error.code == UNEXPECTED_EXCEPTION_SAFE_CODE
    assert _SECRET_TOKEN not in result.provider_result.error.detail
    assert _SECRET_TOKEN not in result.provider_result.error.code
    assert "ValueError" not in result.provider_result.error.detail


def test_unexpected_exception_is_retried_when_internal_failure_is_made_retryable() -> None:
    provider = FakeRaisingProvider()
    executor = AIProviderExecutor(
        provider,
        sleeper=RecordingSleeper(),
        retry_policy=AIProviderRetryPolicy(
            maximum_attempts=3,
            retryable_categories=frozenset({ErrorCategory.INTERNAL_FAILURE}),
        ),
    )
    result = executor.execute(_request())
    assert result.attempts == 3
    assert provider.call_count == 3
    assert result.status is ProviderExecutionStatus.FAILED


def test_unexpected_exception_is_not_retried_under_the_default_policy() -> None:
    provider = FakeRaisingProvider()
    executor = AIProviderExecutor(provider, sleeper=RecordingSleeper())
    result = executor.execute(_request())
    assert result.attempts == 1
    assert provider.call_count == 1


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_base_exceptions_that_are_not_exception_subclasses_always_propagate(
    exception_type: type[BaseException],
) -> None:
    provider = FakeRaisingProvider(exception_factory=lambda: exception_type("must propagate"))
    executor = AIProviderExecutor(provider)
    with pytest.raises(exception_type):
        executor.execute(_request())


def test_generator_exit_also_propagates() -> None:
    """GeneratorExit is a BaseException, not an Exception; must also propagate."""

    provider = FakeRaisingProvider(exception_factory=lambda: GeneratorExit("must propagate"))
    executor = AIProviderExecutor(provider)
    with pytest.raises(GeneratorExit):
        executor.execute(_request())
