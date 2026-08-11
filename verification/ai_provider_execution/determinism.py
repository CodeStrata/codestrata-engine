"""Determinism helpers and checks: two runs of this suite must produce identical JSON."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, BackoffStrategy
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.execution_serialization import (
    serialize_execution_result_for_diagnostics,
)
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from verification.ai_provider_execution.models import CheckResult


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def reports_are_identical(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return canonical_json(first) == canonical_json(second)


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

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="ok"),
        )


def check_default_executor_serialization_is_stable_across_five_runs() -> CheckResult:
    def _run() -> str:
        executor = AIProviderExecutor(_FakeSucceedingProvider())
        return serialize_execution_result_for_diagnostics(executor.execute(_request()))

    outputs = {_run() for _ in range(5)}
    ok = len(outputs) == 1
    return CheckResult(
        name="default_executor_serialization_is_stable_across_five_runs",
        category="determinism",
        ok=ok,
        detail=f"distinct_outputs={len(outputs)}",
    )


def check_backoff_delay_sequence_is_stable_across_five_runs() -> CheckResult:
    @dataclass
    class _FlakyProvider:
        provider_id: ProviderId = ProviderId.BEDROCK
        _remaining_failures: int = 3

        def supports(self, capability: CapabilityId) -> bool:
            return True

        def execute(self, request: AIProviderRequest) -> AIProviderResult:
            from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory

            if self._remaining_failures > 0:
                self._remaining_failures -= 1
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

    def _run_delays() -> tuple[float, ...]:
        calls: list[float] = []
        executor = AIProviderExecutor(
            _FlakyProvider(),
            sleeper=calls.append,
            retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
            backoff_policy=BackoffPolicy(
                strategy=BackoffStrategy.EXPONENTIAL,
                base_delay_seconds=0.1,
                multiplier=2.0,
                jitter=True,
            ),
        )
        executor.execute(_request())
        return tuple(calls)

    runs = {_run_delays() for _ in range(5)}
    ok = len(runs) == 1
    return CheckResult(
        name="retry_backoff_delay_sequence_is_deterministic_across_five_runs",
        category="determinism",
        ok=ok,
        detail=f"distinct_delay_sequences={len(runs)}",
    )


def check_execution_result_hash_is_stable_across_five_runs() -> CheckResult:
    def _hash_result() -> str:
        executor = AIProviderExecutor(_FakeSucceedingProvider())
        text = serialize_execution_result_for_diagnostics(executor.execute(_request()))
        return stable_hash(json.loads(text))

    hashes = {_hash_result() for _ in range(5)}
    ok = len(hashes) == 1
    return CheckResult(
        name="execution_result_hash_is_stable_across_five_runs",
        category="determinism",
        ok=ok,
        detail=f"distinct_hashes={len(hashes)}",
    )


def run_determinism_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_default_executor_serialization_is_stable_across_five_runs(),
        check_backoff_delay_sequence_is_stable_across_five_runs(),
        check_execution_result_hash_is_stable_across_five_runs(),
    ]
    matrix: dict[str, Any] = {}
    return checks, matrix


__all__ = [
    "canonical_json",
    "check_backoff_delay_sequence_is_stable_across_five_runs",
    "check_default_executor_serialization_is_stable_across_five_runs",
    "check_execution_result_hash_is_stable_across_five_runs",
    "reports_are_identical",
    "run_determinism_checks",
    "stable_hash",
]
