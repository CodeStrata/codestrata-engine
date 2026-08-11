"""Privacy characterization: execution diagnostics/serialization never leak content/exceptions."""

from __future__ import annotations

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.execution_serialization import (
    private_view_of_execution_result,
    serialize_execution_result_for_diagnostics,
    serialize_execution_result_private,
)
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from tests.ai.provider_contracts.execution_fakes import FakeRaisingProvider
from tests.ai.provider_contracts.fakes import FakeSucceedingProvider

_FAKE_SECRET_CONTENT = "fake-internal-secret-response-value-do-not-leak"


class _FakeSecretContentProvider(FakeSucceedingProvider):
    def execute(self, request: AIProviderRequest):  # type: ignore[override]
        from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
        from codestrata.ai.provider_contracts.responses import (
            AIProviderResult,
            AIProviderResultContent,
        )

        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text=_FAKE_SECRET_CONTENT),
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


def test_diagnostic_serialization_excludes_provider_result_content() -> None:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    text = serialize_execution_result_for_diagnostics(result)
    assert _FAKE_SECRET_CONTENT not in text


def test_private_view_and_serialization_include_the_content_for_internal_test_use() -> None:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    view = private_view_of_execution_result(result)
    assert view["provider_result"]["text"] == _FAKE_SECRET_CONTENT
    text = serialize_execution_result_private(result)
    assert _FAKE_SECRET_CONTENT in text


def test_diagnostic_and_private_views_are_correctly_distinct() -> None:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    diagnostic_text = serialize_execution_result_for_diagnostics(result)
    private_text = serialize_execution_result_private(result)
    assert diagnostic_text != private_text


def test_unexpected_exception_message_never_appears_in_diagnostic_or_private_serialization() -> (
    None
):
    secret = "sk-super-secret-token-should-never-appear"
    provider = FakeRaisingProvider(exception_factory=lambda: RuntimeError(f"leak: {secret}"))
    executor = AIProviderExecutor(provider)
    result = executor.execute(_request())
    diagnostic_text = serialize_execution_result_for_diagnostics(result)
    private_text = serialize_execution_result_private(result)
    assert secret not in diagnostic_text
    assert secret not in private_text
    assert "RuntimeError" not in diagnostic_text
    assert "RuntimeError" not in private_text


def test_diagnostic_serialization_never_contains_absolute_home_paths() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    result = executor.execute(_request())
    text = serialize_execution_result_for_diagnostics(result)
    assert "/Users/" not in text
    assert "/home/" not in text
