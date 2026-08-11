"""Test-only fake AIProvider implementations.

These fakes exist solely for unit/verification tests. They are never
imported by production code and must not be registered as defaults anywhere.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata


class FakeSucceedingProvider:
    """A fake provider that always succeeds with canned, non-sensitive content."""

    def __init__(self, provider_id: ProviderId = ProviderId.OPENAI) -> None:
        self._provider_id = provider_id

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self._provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="fake modernization advice"),
            usage=ProviderUsageMetadata(input_tokens=12, output_tokens=8, total_tokens=20),
        )


class FakeFailingProvider:
    """A fake provider that always fails with a bounded, safe error."""

    def __init__(self, provider_id: ProviderId = ProviderId.BEDROCK) -> None:
        self._provider_id = provider_id

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return capability is CapabilityId.MODERNIZATION_ADVISOR

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self._provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.FAILED,
            error=AIProviderError(
                category=ErrorCategory.PROVIDER_UNAVAILABLE,
                code="fake_provider_unavailable",
                detail="fake provider is intentionally unavailable for this test",
            ),
        )


class FakeUnavailableProvider:
    """A fake provider that declares no capability support and is never invoked."""

    def __init__(self, provider_id: ProviderId = ProviderId.OPENAI) -> None:
        self._provider_id = provider_id

    @property
    def provider_id(self) -> ProviderId:
        return self._provider_id

    def supports(self, capability: CapabilityId) -> bool:
        return False

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self._provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.UNAVAILABLE,
            error=AIProviderError(
                category=ErrorCategory.DEPENDENCY_UNAVAILABLE,
                code="fake_capability_unsupported",
                detail="fake provider does not support the requested capability",
            ),
        )


__all__ = [
    "FakeFailingProvider",
    "FakeSucceedingProvider",
    "FakeUnavailableProvider",
]
