"""Test-only fake ``AIProvider`` implementations for Slice 11.4 execution tests.

These fakes exist solely for unit/verification tests. They are never
imported by production code and must not be registered as defaults
anywhere. See ``fakes.py`` for the Slice 11.2 always-succeed/always-fail/
unavailable fakes this module complements.
"""

from __future__ import annotations

from collections.abc import Callable

from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata


class FakeRetryableThenSucceedingProvider:
    """Fails with a retryable category ``fail_count`` times, then succeeds."""

    def __init__(
        self,
        *,
        fail_count: int,
        category: ErrorCategory = ErrorCategory.PROVIDER_UNAVAILABLE,
        provider_id: ProviderId = ProviderId.BEDROCK,
    ) -> None:
        self._fail_count = fail_count
        self._category = category
        self._provider_id = provider_id
        self.call_count = 0

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            return AIProviderResult(
                provider_id=self._provider_id,
                capability=request.capability,
                status=ProviderExecutionStatus.FAILED,
                error=AIProviderError(
                    category=self._category,
                    code="fake_transient_failure",
                    detail="fake transient failure for retry testing",
                ),
            )
        return AIProviderResult(
            provider_id=self._provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="fake advice after retry"),
            usage=ProviderUsageMetadata(input_tokens=5, output_tokens=5, total_tokens=10),
        )


class FakeAlwaysFailingProvider:
    """Always fails with a caller-chosen (default: non-retryable) category."""

    def __init__(
        self,
        *,
        category: ErrorCategory = ErrorCategory.INVALID_REQUEST,
        provider_id: ProviderId = ProviderId.OPENAI,
        code: str = "fake_permanent_failure",
    ) -> None:
        self._category = category
        self._provider_id = provider_id
        self._code = code
        self.call_count = 0

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        return AIProviderResult(
            provider_id=self._provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.FAILED,
            error=AIProviderError(
                category=self._category,
                code=self._code,
                detail="fake permanent failure for terminal-decision testing",
            ),
        )


class FakeRaisingProvider:
    """Raises an unexpected exception from ``execute()`` (a contract violation)."""

    def __init__(
        self,
        *,
        exception_factory: Callable[[], BaseException] | None = None,
        provider_id: ProviderId = ProviderId.OPENAI,
    ) -> None:
        self._exception_factory = exception_factory or (
            lambda: RuntimeError("fake unexpected internal error: sk-super-secret-token-value")
        )
        self._provider_id = provider_id
        self.call_count = 0

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        self.call_count += 1
        raise self._exception_factory()


class FakeWrongProviderIdProvider:
    """Contract-violating fake: ``execute()`` returns a mismatched ``provider_id``."""

    def __init__(
        self,
        *,
        declared_provider_id: ProviderId = ProviderId.OPENAI,
        returned_provider_id: ProviderId = ProviderId.BEDROCK,
    ) -> None:
        self._declared_provider_id = declared_provider_id
        self._returned_provider_id = returned_provider_id

    @property
    def provider_id(self) -> ProviderId:
        return self._declared_provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self._returned_provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="mismatched provider result"),
        )


class RecordingSleeper:
    """A test ``sleeper`` callable that records every requested delay instead of sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


__all__ = [
    "FakeAlwaysFailingProvider",
    "FakeRaisingProvider",
    "FakeRetryableThenSucceedingProvider",
    "FakeWrongProviderIdProvider",
    "RecordingSleeper",
]
