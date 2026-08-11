"""Privacy characterization: execution diagnostics/serialization never leak content/exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.execution_diagnostics import (
    diagnostic_view_of_execution_result,
)
from codestrata.ai.provider_contracts.execution_serialization import (
    serialize_execution_result_for_diagnostics,
    serialize_execution_result_private,
)
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from verification.ai_provider_execution.models import CheckResult

_FAKE_SECRET_CONTENT = "fake-internal-secret-verification-response-do-not-leak"
_FAKE_EXCEPTION_SECRET = "fake-internal-secret-exception-message-do-not-leak"


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
class _FakeSecretContentProvider:
    provider_id: ProviderId = ProviderId.BEDROCK

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        return AIProviderResult(
            provider_id=self.provider_id,
            capability=request.capability,
            status=ProviderExecutionStatus.SUCCESS,
            content=AIProviderResultContent(text=_FAKE_SECRET_CONTENT),
        )


@dataclass
class _FakeRaisingProvider:
    provider_id: ProviderId = ProviderId.BEDROCK

    def supports(self, capability: CapabilityId) -> bool:
        return True

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        raise RuntimeError(_FAKE_EXCEPTION_SECRET)


def check_diagnostic_serialization_excludes_provider_result_content() -> CheckResult:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    text = serialize_execution_result_for_diagnostics(result)
    ok = _FAKE_SECRET_CONTENT not in text
    return CheckResult(
        name="diagnostic_serialization_excludes_provider_result_content",
        category="privacy",
        ok=ok,
        detail="fake secret content absent from diagnostic serialization" if ok else "leaked",
    )


def check_private_view_may_include_content_for_internal_use_only() -> CheckResult:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    text = serialize_execution_result_private(result)
    ok = _FAKE_SECRET_CONTENT in text
    return CheckResult(
        name="private_serialization_may_include_content_reserved_for_internal_use_only",
        category="privacy",
        ok=ok,
        detail="private serialization carries fake secret content" if ok else "not found",
    )


def check_diagnostic_and_private_serializations_are_distinct() -> CheckResult:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    diagnostic_text = serialize_execution_result_for_diagnostics(result)
    private_text = serialize_execution_result_private(result)
    ok = diagnostic_text != private_text
    return CheckResult(
        name="diagnostic_and_private_execution_serializations_are_correctly_distinct",
        category="privacy",
        ok=ok,
        detail=f"equal={diagnostic_text == private_text}",
    )


def check_unexpected_exception_text_never_appears_in_any_serialization() -> CheckResult:
    executor = AIProviderExecutor(_FakeRaisingProvider())
    result = executor.execute(_request())
    diagnostic_text = serialize_execution_result_for_diagnostics(result)
    private_text = serialize_execution_result_private(result)
    ok = (
        _FAKE_EXCEPTION_SECRET not in diagnostic_text
        and _FAKE_EXCEPTION_SECRET not in private_text
        and "RuntimeError" not in diagnostic_text
        and "RuntimeError" not in private_text
    )
    return CheckResult(
        name="unexpected_exception_message_and_type_never_appear_in_any_execution_serialization",
        category="privacy",
        ok=ok,
        detail="fake exception secret and 'RuntimeError' absent from both serializations",
    )


def check_diagnostic_view_never_contains_absolute_home_paths() -> CheckResult:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    blob = repr(view)
    ok = "/Users/" not in blob and "/home/" not in blob
    return CheckResult(
        name="diagnostic_view_never_contains_an_absolute_home_directory_path",
        category="privacy",
        ok=ok,
        detail="no absolute path patterns found" if ok else "path leaked",
    )


def check_diagnostic_view_has_exactly_the_expected_bounded_keys() -> CheckResult:
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    result = executor.execute(_request())
    view = diagnostic_view_of_execution_result(result)
    expected_keys = {
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
    ok = set(view) == expected_keys
    return CheckResult(
        name="diagnostic_view_of_execution_result_has_exactly_the_expected_bounded_keys",
        category="privacy",
        ok=ok,
        detail=f"keys={sorted(view)}",
    )


def run_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_diagnostic_serialization_excludes_provider_result_content(),
        check_private_view_may_include_content_for_internal_use_only(),
        check_diagnostic_and_private_serializations_are_distinct(),
        check_unexpected_exception_text_never_appears_in_any_serialization(),
        check_diagnostic_view_never_contains_absolute_home_paths(),
        check_diagnostic_view_has_exactly_the_expected_bounded_keys(),
    ]
    executor = AIProviderExecutor(_FakeSecretContentProvider())
    sample_view = diagnostic_view_of_execution_result(executor.execute(_request()))
    matrix: dict[str, Any] = {"sample_diagnostic_view": sample_view}
    return checks, matrix


__all__ = [
    "check_diagnostic_and_private_serializations_are_distinct",
    "check_diagnostic_serialization_excludes_provider_result_content",
    "check_diagnostic_view_has_exactly_the_expected_bounded_keys",
    "check_diagnostic_view_never_contains_absolute_home_paths",
    "check_private_view_may_include_content_for_internal_use_only",
    "check_unexpected_exception_text_never_appears_in_any_serialization",
    "run_privacy_checks",
]
