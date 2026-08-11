"""Determinism tests: identical inputs must produce byte-identical serialized output."""

from __future__ import annotations

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, BackoffStrategy
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.execution_serialization import (
    serialize_execution_result_for_diagnostics,
)
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from tests.ai.provider_contracts.execution_fakes import (
    FakeRetryableThenSucceedingProvider,
    RecordingSleeper,
)
from tests.ai.provider_contracts.fakes import FakeSucceedingProvider


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="advise", context_payload_text="context"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("fake-model"),
    )


def test_default_executor_serialization_is_stable_across_five_runs() -> None:
    def _run() -> str:
        executor = AIProviderExecutor(FakeSucceedingProvider())
        return serialize_execution_result_for_diagnostics(executor.execute(_request()))

    outputs = {_run() for _ in range(5)}
    assert len(outputs) == 1


def test_retry_backoff_delays_are_deterministic_across_five_runs() -> None:
    def _run_delays() -> tuple[float, ...]:
        provider = FakeRetryableThenSucceedingProvider(fail_count=3)
        sleeper = RecordingSleeper()
        executor = AIProviderExecutor(
            provider,
            sleeper=sleeper,
            retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
            backoff_policy=BackoffPolicy(
                strategy=BackoffStrategy.EXPONENTIAL,
                base_delay_seconds=0.1,
                multiplier=2.0,
                jitter=True,
            ),
        )
        executor.execute(_request())
        return tuple(sleeper.calls)

    runs = {_run_delays() for _ in range(5)}
    assert len(runs) == 1


def test_two_independently_constructed_executors_produce_identical_results() -> None:
    def _build_and_run() -> str:
        executor = AIProviderExecutor(
            FakeSucceedingProvider(), retry_policy=AIProviderRetryPolicy(maximum_attempts=1)
        )
        return serialize_execution_result_for_diagnostics(executor.execute(_request()))

    assert _build_and_run() == _build_and_run()
