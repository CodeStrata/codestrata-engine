"""Unit tests for provider_contracts.responses."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError as CErr
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent


def _error() -> AIProviderError:
    return AIProviderError(category=ErrorCategory.TIMEOUT, code="timeout", detail="timed out")


def test_result_content_requires_at_least_one_field() -> None:
    with pytest.raises(CErr):
        AIProviderResultContent()


def test_result_content_accepts_text_only() -> None:
    content = AIProviderResultContent(text="hello")
    assert content.text == "hello"
    assert content.structured_payload is None


def test_result_content_accepts_structured_payload_only() -> None:
    content = AIProviderResultContent(structured_payload={"a": 1})
    assert content.structured_payload == {"a": 1}


def test_success_result_requires_content_and_forbids_error() -> None:
    with pytest.raises(CErr):
        AIProviderResult(
            provider_id=ProviderId.OPENAI,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=ProviderExecutionStatus.SUCCESS,
        )
    with pytest.raises(CErr):
        AIProviderResult(
            provider_id=ProviderId.OPENAI,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text="ok"),
            error=_error(),
        )


def test_success_result_with_content_is_valid() -> None:
    result = AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SUCCESS,
        content=AIProviderResultContent(text="ok"),
    )
    assert result.status is ProviderExecutionStatus.SUCCESS


@pytest.mark.parametrize(
    "status", [ProviderExecutionStatus.FAILED, ProviderExecutionStatus.UNAVAILABLE]
)
def test_failed_and_unavailable_results_require_error_and_forbid_content(
    status: ProviderExecutionStatus,
) -> None:
    with pytest.raises(CErr):
        AIProviderResult(
            provider_id=ProviderId.BEDROCK,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=status,
        )
    with pytest.raises(CErr):
        AIProviderResult(
            provider_id=ProviderId.BEDROCK,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=status,
            error=_error(),
            content=AIProviderResultContent(text="unexpected"),
        )
    result = AIProviderResult(
        provider_id=ProviderId.BEDROCK,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=status,
        error=_error(),
    )
    assert result.error is not None


def test_skipped_result_forbids_content_and_error() -> None:
    result = AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SKIPPED,
    )
    assert result.content is None
    assert result.error is None
    with pytest.raises(CErr):
        AIProviderResult(
            provider_id=ProviderId.OPENAI,
            capability=CapabilityId.MODERNIZATION_ADVISOR,
            status=ProviderExecutionStatus.SKIPPED,
            error=_error(),
        )


def test_result_is_frozen() -> None:
    result = AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SKIPPED,
    )
    with pytest.raises(AttributeError):
        result.status = ProviderExecutionStatus.SUCCESS  # type: ignore[misc]
