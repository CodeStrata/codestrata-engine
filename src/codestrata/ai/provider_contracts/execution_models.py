"""``AIProviderExecutionContext``/``AIProviderExecutionResult``: the executor's inputs/outputs.

Neither type is ever constructed by, or consulted by, the actual assess
factory, providers, enrichment, doctor, or CLI — see ``executor.py``'s
module docstring for the executor itself, and
``engine/tests/ai/provider_contracts/test_execution_runtime_unwired.py`` for
the test proving no product-path file imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.backoff import BackoffStrategy
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.responses import AIProviderResult
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy
from codestrata.ai.provider_contracts.timeout_policy import TimeoutPolicy, TimeoutScope
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata

_TERMINAL_STATUSES_REQUIRING_ERROR_CATEGORY = (
    ProviderExecutionStatus.FAILED,
    ProviderExecutionStatus.UNAVAILABLE,
)

_TIMEOUT_SCOPE_VALUES: frozenset[str] = frozenset(scope.value for scope in TimeoutScope)
_BACKOFF_STRATEGY_VALUES: frozenset[str] = frozenset(strategy.value for strategy in BackoffStrategy)


@dataclass(frozen=True, slots=True)
class AIProviderExecutionContext:
    """Immutable description of a single ``AIProviderExecutor.execute()`` call's policies."""

    provider_id: ProviderId
    capability: CapabilityId
    timeout_policy: TimeoutPolicy
    retry_policy: AIProviderRetryPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if not isinstance(self.capability, CapabilityId):
            raise ProviderContractValidationError(
                f"capability must be a CapabilityId, got {type(self.capability).__name__}"
            )
        if not isinstance(self.timeout_policy, TimeoutPolicy):
            raise ProviderContractValidationError("timeout_policy must be a TimeoutPolicy")
        if not isinstance(self.retry_policy, AIProviderRetryPolicy):
            raise ProviderContractValidationError(
                "retry_policy must be an AIProviderRetryPolicy"
            )


@dataclass(frozen=True, slots=True)
class ExecutionDiagnostics:
    """Bounded, safe-to-log per-execution diagnostics. Never carries content/exception text."""

    attempt_error_categories: tuple[str, ...]
    timeout_policy_scope: str
    timeout_policy_seconds: float
    retry_policy_maximum_attempts: int
    backoff_strategy: str

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_error_categories, tuple) or not all(
            isinstance(item, str) for item in self.attempt_error_categories
        ):
            raise ProviderContractValidationError(
                "attempt_error_categories must be a tuple of strings"
            )
        if self.timeout_policy_scope not in _TIMEOUT_SCOPE_VALUES:
            raise ProviderContractValidationError(
                "timeout_policy_scope must be a TimeoutScope value, got "
                f"{self.timeout_policy_scope!r}"
            )
        if isinstance(self.timeout_policy_seconds, bool) or not isinstance(
            self.timeout_policy_seconds, (int, float)
        ):
            raise ProviderContractValidationError("timeout_policy_seconds must be a number")
        if (
            isinstance(self.retry_policy_maximum_attempts, bool)
            or not isinstance(self.retry_policy_maximum_attempts, int)
            or self.retry_policy_maximum_attempts < 1
        ):
            raise ProviderContractValidationError(
                "retry_policy_maximum_attempts must be a positive int"
            )
        if self.backoff_strategy not in _BACKOFF_STRATEGY_VALUES:
            raise ProviderContractValidationError(
                f"backoff_strategy must be a BackoffStrategy value, got {self.backoff_strategy!r}"
            )


@dataclass(frozen=True, slots=True)
class AIProviderExecutionResult:
    """Immutable result of a full ``AIProviderExecutor.execute()`` call, including retries."""

    provider_id: ProviderId
    capability: CapabilityId
    status: ProviderExecutionStatus
    provider_result: AIProviderResult | None
    attempts: int
    retry_count: int
    terminal_error_category: ErrorCategory | None
    timeout_applied: bool
    usage: ProviderUsageMetadata | None
    diagnostics: ExecutionDiagnostics
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if not isinstance(self.capability, CapabilityId):
            raise ProviderContractValidationError(
                f"capability must be a CapabilityId, got {type(self.capability).__name__}"
            )
        if not isinstance(self.status, ProviderExecutionStatus):
            raise ProviderContractValidationError(
                f"status must be a ProviderExecutionStatus, got {type(self.status).__name__}"
            )
        if self.provider_result is not None and not isinstance(
            self.provider_result, AIProviderResult
        ):
            raise ProviderContractValidationError(
                "provider_result must be an AIProviderResult when present"
            )
        if (
            isinstance(self.attempts, bool)
            or not isinstance(self.attempts, int)
            or self.attempts < 0
        ):
            raise ProviderContractValidationError("attempts must be a non-negative int")
        if (
            isinstance(self.retry_count, bool)
            or not isinstance(self.retry_count, int)
            or self.retry_count < 0
        ):
            raise ProviderContractValidationError("retry_count must be a non-negative int")
        expected_retry_count = max(self.attempts - 1, 0)
        if self.retry_count != expected_retry_count:
            raise ProviderContractValidationError(
                f"retry_count ({self.retry_count}) must equal attempts - 1 "
                f"({expected_retry_count}); every retry is exactly one more attempt"
            )
        if self.terminal_error_category is not None and not isinstance(
            self.terminal_error_category, ErrorCategory
        ):
            raise ProviderContractValidationError(
                "terminal_error_category must be an ErrorCategory or None"
            )
        if not isinstance(self.timeout_applied, bool):
            raise ProviderContractValidationError("timeout_applied must be a bool")
        if self.usage is not None and not isinstance(self.usage, ProviderUsageMetadata):
            raise ProviderContractValidationError(
                "usage must be a ProviderUsageMetadata when present"
            )
        if not isinstance(self.diagnostics, ExecutionDiagnostics):
            raise ProviderContractValidationError("diagnostics must be an ExecutionDiagnostics")
        if not isinstance(self.limitations, tuple) or not all(
            isinstance(item, str) and item for item in self.limitations
        ):
            raise ProviderContractValidationError(
                "limitations must be a tuple of non-empty strings"
            )
        if not self.limitations:
            raise ProviderContractValidationError(
                "limitations must be non-empty for an unwired execution result"
            )

        if self.status is ProviderExecutionStatus.SUCCESS:
            if (
                self.provider_result is None
                or self.provider_result.status is not ProviderExecutionStatus.SUCCESS
            ):
                raise ProviderContractValidationError(
                    "a SUCCESS execution result must carry a SUCCESS provider_result"
                )
            if self.terminal_error_category is not None:
                raise ProviderContractValidationError(
                    "a SUCCESS execution result must not carry a terminal_error_category"
                )
            if self.attempts < 1:
                raise ProviderContractValidationError(
                    "a SUCCESS execution result must have made at least one attempt"
                )
        elif self.status in _TERMINAL_STATUSES_REQUIRING_ERROR_CATEGORY:
            if self.provider_result is None or self.provider_result.status is not self.status:
                raise ProviderContractValidationError(
                    f"a {self.status.value.upper()} execution result must carry a matching "
                    "provider_result"
                )
            if self.terminal_error_category is None:
                raise ProviderContractValidationError(
                    f"a {self.status.value.upper()} execution result must carry a "
                    "terminal_error_category"
                )
            if self.attempts < 1:
                raise ProviderContractValidationError(
                    f"a {self.status.value.upper()} execution result must have made at least "
                    "one attempt"
                )
        elif self.status is ProviderExecutionStatus.SKIPPED:
            if (
                self.provider_result is not None
                and self.provider_result.status is not ProviderExecutionStatus.SKIPPED
            ):
                raise ProviderContractValidationError(
                    "a SKIPPED execution result's provider_result, when present, must also "
                    "be SKIPPED"
                )
            if self.provider_result is None:
                if self.attempts != 0 or self.retry_count != 0:
                    raise ProviderContractValidationError(
                        "a pre-flight SKIPPED execution result (no provider_result) must "
                        "record zero attempts and zero retries"
                    )
            elif self.attempts < 1:
                raise ProviderContractValidationError(
                    "a SKIPPED execution result carrying a provider_result must have made "
                    "at least one attempt"
                )
            if self.terminal_error_category is not None:
                raise ProviderContractValidationError(
                    "a SKIPPED execution result must not carry a terminal_error_category"
                )


__all__ = [
    "AIProviderExecutionContext",
    "AIProviderExecutionResult",
    "ExecutionDiagnostics",
]
