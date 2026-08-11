"""``AIProviderExecutor``: a standardized execution loop with retries.

**Wired for OpenAI only (Slice 11.6).**
``codestrata.ai.provider_adapters.openai.factory.build_openai_executor``
constructs an executor around the OpenAI ``AIProvider`` adapter, and
``codestrata.ai.providers.openai_provider.OpenAIAIModelProvider`` calls it on
the assess path. It is pinned there to ``DEFAULT_RETRY_POLICY``
(``maximum_attempts=1``) and ``DEFAULT_TIMEOUT_POLICY`` so the observable
single-attempt CR-1 behavior is unchanged.

Everything else remains unwired: Bedrock (``ai/providers/bedrock.py``),
``codestrata.ai.enrichment``, ``codestrata.ai.providers.doctor``, and the
CLI/factory modules neither construct nor call ``AIProviderExecutor``.

**What it does:**

* Confirms the target provider declares support for the request's
  capability (``AIProvider.supports()``) before ever calling ``execute()``;
  when unsupported, it returns a ``SKIPPED`` ``AIProviderExecutionResult``
  without invoking the provider at all (zero attempts).
* Calls ``AIProvider.execute(request)`` and, on a ``FAILED``/
  ``UNAVAILABLE`` result whose error category is retryable under the
  configured ``AIProviderRetryPolicy`` (and while attempts remain under
  ``maximum_attempts``), uses ``retry_decision.decide_retry`` to decide
  whether to retry, and if so, calls the injected ``sleeper`` with the
  computed backoff delay before making the next attempt.
* Validates that the ``AIProviderResult`` returned by ``execute()`` reports
  the same ``provider_id`` as the provider itself — a contract violation
  otherwise, which raises ``ProviderContractValidationError``.
* Catches any unexpected ``Exception`` raised by ``AIProvider.execute()``
  (a contract violation — ``execute()`` is documented to never raise for
  expected failures; see ``provider.AIProvider.execute``) and converts it
  into a synthetic ``FAILED`` result classified as
  ``ErrorCategory.INTERNAL_FAILURE`` via ``error_classification.
  classify_unexpected_exception``, which never inspects the exception's
  message, type, or traceback. ``KeyboardInterrupt`` and ``SystemExit`` do
  not subclass ``Exception`` and always propagate unmodified.

**What it deliberately does NOT do** (see ``engine/docs/ai-provider-execution.md``):

* It never enforces a wall-clock timeout itself — no threads, no signals, no
  ``asyncio``. ``AIProviderExecutionResult.timeout_applied`` only records
  whether a provider-reported ``ErrorCategory.TIMEOUT`` was observed on any
  attempt. Real wall-clock enforcement is deferred to a future
  provider-adapter-level client timeout, which is out of scope here.
* It never reads ``os.environ`` or a configuration file, never constructs a
  provider client, and never mutates a report — it only calls the
  already-constructed ``provider`` argument's ``execute()`` method with the
  already-constructed ``request`` argument.
* It is called by nothing in this slice; only fakes (test-only, see
  ``engine/tests/ai/provider_contracts/execution_fakes.py``) and this
  module's own tests/verification suite exercise it.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from codestrata.ai.provider_contracts.backoff import DEFAULT_BACKOFF_POLICY, BackoffPolicy
from codestrata.ai.provider_contracts.error_classification import classify_unexpected_exception
from codestrata.ai.provider_contracts.errors import (
    AIProviderError,
    ErrorCategory,
    ProviderContractValidationError,
)
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.execution_models import (
    AIProviderExecutionResult,
    ExecutionDiagnostics,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.provider import AIProvider
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult
from codestrata.ai.provider_contracts.retry_decision import decide_retry
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    AIProviderRetryPolicy,
)
from codestrata.ai.provider_contracts.timeout_policy import DEFAULT_TIMEOUT_POLICY, TimeoutPolicy

Clock = Callable[[], float]
Sleeper = Callable[[float], None]

EXECUTOR_LIMITATIONS: tuple[str, ...] = (
    "executor_not_wired",
    "providers_not_migrated",
    "timeout_enforcement_deferred_to_adapters",
)

_PROVIDER_ID_MISMATCH_MESSAGE = (
    "AIProvider.execute() returned a result whose provider_id does not match "
    "provider.provider_id"
)


class AIProviderExecutor:
    """Runs one ``AIProviderRequest`` against one ``AIProvider``, applying retry/backoff policy."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
        timeout_policy: TimeoutPolicy = DEFAULT_TIMEOUT_POLICY,
        retry_policy: AIProviderRetryPolicy = DEFAULT_RETRY_POLICY,
        backoff_policy: BackoffPolicy = DEFAULT_BACKOFF_POLICY,
    ) -> None:
        if not isinstance(provider, AIProvider):
            raise ProviderContractValidationError(
                f"provider must implement the AIProvider protocol, got {type(provider).__name__}"
            )
        if not callable(clock):
            raise ProviderContractValidationError("clock must be callable")
        if not callable(sleeper):
            raise ProviderContractValidationError("sleeper must be callable")
        if not isinstance(timeout_policy, TimeoutPolicy):
            raise ProviderContractValidationError("timeout_policy must be a TimeoutPolicy")
        if not isinstance(retry_policy, AIProviderRetryPolicy):
            raise ProviderContractValidationError(
                "retry_policy must be an AIProviderRetryPolicy"
            )
        if not isinstance(backoff_policy, BackoffPolicy):
            raise ProviderContractValidationError("backoff_policy must be a BackoffPolicy")
        self._provider = provider
        self._clock = clock
        self._sleeper = sleeper
        self._timeout_policy = timeout_policy
        self._retry_policy = retry_policy
        self._backoff_policy = backoff_policy

    def execute(self, request: AIProviderRequest) -> AIProviderExecutionResult:
        """Execute ``request`` against the wrapped provider, retrying per policy. Never raises

        for an expected provider/parsing/validation failure — those surface as a terminal
        ``FAILED``/``UNAVAILABLE`` ``AIProviderExecutionResult`` instead.
        """

        if not isinstance(request, AIProviderRequest):
            raise ProviderContractValidationError("request must be an AIProviderRequest")

        provider_id = self._provider.provider_id
        capability = request.capability

        if not self._provider.supports(capability):
            return self._build_result(
                provider_id=provider_id,
                capability=capability,
                status=ProviderExecutionStatus.SKIPPED,
                provider_result=None,
                attempts=0,
                terminal_error_category=None,
                timeout_applied=False,
                attempt_error_categories=(),
            )

        attempt = 1
        attempt_error_categories: list[ErrorCategory] = []
        timeout_applied = False

        while True:
            result = self._invoke_provider_once(request)
            if result.provider_id != provider_id:
                raise ProviderContractValidationError(_PROVIDER_ID_MISMATCH_MESSAGE)

            if result.status is ProviderExecutionStatus.SUCCESS:
                return self._build_result(
                    provider_id=provider_id,
                    capability=capability,
                    status=ProviderExecutionStatus.SUCCESS,
                    provider_result=result,
                    attempts=attempt,
                    terminal_error_category=None,
                    timeout_applied=timeout_applied,
                    attempt_error_categories=tuple(attempt_error_categories),
                )

            if result.status is ProviderExecutionStatus.SKIPPED:
                # A provider-level skip after supports() already returned True
                # is unusual but contract-valid; treat it as terminal — there
                # is no error category on a SKIPPED result to key a retry on.
                return self._build_result(
                    provider_id=provider_id,
                    capability=capability,
                    status=ProviderExecutionStatus.SKIPPED,
                    provider_result=result,
                    attempts=attempt,
                    terminal_error_category=None,
                    timeout_applied=timeout_applied,
                    attempt_error_categories=tuple(attempt_error_categories),
                )

            # FAILED or UNAVAILABLE.
            error = result.error
            category = error.category if error is not None else ErrorCategory.INTERNAL_FAILURE
            attempt_error_categories.append(category)
            if category is ErrorCategory.TIMEOUT:
                timeout_applied = True

            decision = decide_retry(
                attempt=attempt,
                category=category,
                retry_policy=self._retry_policy,
                backoff_policy=self._backoff_policy,
            )
            if not decision.should_retry:
                return self._build_result(
                    provider_id=provider_id,
                    capability=capability,
                    status=result.status,
                    provider_result=result,
                    attempts=attempt,
                    terminal_error_category=category,
                    timeout_applied=timeout_applied,
                    attempt_error_categories=tuple(attempt_error_categories),
                )

            self._sleeper(decision.delay_seconds)
            attempt = decision.next_attempt

    def _invoke_provider_once(self, request: AIProviderRequest) -> AIProviderResult:
        try:
            return self._provider.execute(request)
        except Exception:  # noqa: BLE001 - intentional: see module docstring
            classification = classify_unexpected_exception(self._retry_policy)
            return AIProviderResult(
                provider_id=self._provider.provider_id,
                capability=request.capability,
                status=ProviderExecutionStatus.FAILED,
                error=AIProviderError(
                    category=classification.category,
                    code=classification.safe_code,
                    detail="AIProvider.execute() raised an unexpected exception",
                ),
            )

    def _build_result(
        self,
        *,
        provider_id: ProviderId,
        capability: CapabilityId,
        status: ProviderExecutionStatus,
        provider_result: AIProviderResult | None,
        attempts: int,
        terminal_error_category: ErrorCategory | None,
        timeout_applied: bool,
        attempt_error_categories: tuple[ErrorCategory, ...],
    ) -> AIProviderExecutionResult:
        diagnostics = ExecutionDiagnostics(
            attempt_error_categories=tuple(str(item) for item in attempt_error_categories),
            timeout_policy_scope=str(self._timeout_policy.scope),
            timeout_policy_seconds=self._timeout_policy.timeout_seconds,
            retry_policy_maximum_attempts=self._retry_policy.maximum_attempts,
            backoff_strategy=str(self._backoff_policy.strategy),
        )
        return AIProviderExecutionResult(
            provider_id=provider_id,
            capability=capability,
            status=status,
            provider_result=provider_result,
            attempts=attempts,
            retry_count=max(attempts - 1, 0),
            terminal_error_category=terminal_error_category,
            timeout_applied=timeout_applied,
            usage=provider_result.usage if provider_result is not None else None,
            diagnostics=diagnostics,
            limitations=EXECUTOR_LIMITATIONS,
        )


__all__ = ["EXECUTOR_LIMITATIONS", "AIProviderExecutor", "Clock", "Sleeper"]
