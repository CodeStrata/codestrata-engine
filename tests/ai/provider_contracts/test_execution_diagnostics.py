"""Tests for ``diagnostic_view_of_execution_result``."""

from __future__ import annotations

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.execution_diagnostics import (
    diagnostic_view_of_execution_result,
)
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from tests.ai.provider_contracts.fakes import FakeFailingProvider, FakeSucceedingProvider


def _request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="advise", context_payload_text="context"
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("fake-model"),
    )


def test_diagnostic_view_contains_the_expected_bounded_keys() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    assert set(view) == {
        "attempts",
        "capability",
        "diagnostics",
        "has_usage",
        "limitations",
        "provider_id",
        "provider_result",
        "retry_count",
        "status",
        "terminal_error_category",
        "timeout_applied",
    }


def test_diagnostic_view_never_includes_provider_result_content() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    assert "text" not in view["provider_result"]
    assert "structured_payload" not in view["provider_result"]
    assert "content" not in view["provider_result"]


def test_diagnostic_view_reports_has_usage_true_when_usage_present() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    assert view["has_usage"] is True


def test_diagnostic_view_reports_terminal_error_category_for_a_failure() -> None:
    executor = AIProviderExecutor(FakeFailingProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    assert view["terminal_error_category"] == "provider_unavailable"
    assert view["status"] == "failed"


def test_diagnostic_view_diagnostics_block_is_bounded_and_safe() -> None:
    executor = AIProviderExecutor(FakeSucceedingProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    diagnostics = view["diagnostics"]
    assert set(diagnostics) == {
        "attempt_error_categories",
        "backoff_strategy",
        "retry_policy_maximum_attempts",
        "timeout_policy_scope",
        "timeout_policy_seconds",
    }
    assert diagnostics["timeout_policy_scope"] == "provider_request"
    assert diagnostics["timeout_policy_seconds"] == 60.0
    assert diagnostics["retry_policy_maximum_attempts"] == 1
    assert diagnostics["backoff_strategy"] == "none"
