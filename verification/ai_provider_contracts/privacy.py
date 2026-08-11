"""Privacy characterization: diagnostics/serialization never leak sensitive text."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.diagnostics import (
    diagnostic_view_of_request,
    diagnostic_view_of_result,
)
from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.responses import AIProviderResult, AIProviderResultContent
from codestrata.ai.provider_contracts.serialization import (
    serialize_request_for_diagnostics,
    serialize_result_for_diagnostics,
)
from verification.ai_provider_contracts.models import CheckResult

_FAKE_PROMPT = "fake instruction mentioning AKIAFAKEEXAMPLE0000 and sk-fakeexampletoken00000000"
_FAKE_CONTEXT = "fake context payload with /Users/fake/secret.txt"
_FAKE_MODEL = "fake-internal-only-model-reference"
_FAKE_RESPONSE_TEXT = "fake response containing Bearer fake0000000000000000example"


def _sample_request() -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=_FAKE_PROMPT, context_payload_text=_FAKE_CONTEXT
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference(_FAKE_MODEL),
    )


def _sample_success_result() -> AIProviderResult:
    return AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SUCCESS,
        content=AIProviderResultContent(text=_FAKE_RESPONSE_TEXT),
    )


def _sample_failed_result() -> AIProviderResult:
    return AIProviderResult(
        provider_id=ProviderId.BEDROCK,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.FAILED,
        error=AIProviderError(
            category=ErrorCategory.AUTHENTICATION_FAILED,
            code="fake_missing_credentials",
            detail="fake safe diagnostic detail",
        ),
    )


def check_request_diagnostics_exclude_prompt_and_raw_model_value() -> CheckResult:
    view = diagnostic_view_of_request(_sample_request())
    blob = repr(view)
    leaks = [token for token in (_FAKE_PROMPT, _FAKE_CONTEXT, _FAKE_MODEL) if token in blob]
    ok = not leaks and view["model_reference"] == "[model_ref]"
    return CheckResult(
        name="request_diagnostic_view_excludes_prompt_and_raw_model_reference",
        category="privacy",
        ok=ok,
        detail=f"leaked_field_count={len(leaks)}",
    )


def check_result_diagnostics_exclude_response_text() -> CheckResult:
    view = diagnostic_view_of_result(_sample_success_result())
    blob = repr(view)
    ok = _FAKE_RESPONSE_TEXT not in blob
    return CheckResult(
        name="result_diagnostic_view_excludes_response_text",
        category="privacy",
        ok=ok,
        detail="response text absent from diagnostic view" if ok else "response text leaked",
    )


def check_serialized_forms_exclude_sensitive_text() -> CheckResult:
    texts = [
        serialize_request_for_diagnostics(_sample_request()),
        serialize_result_for_diagnostics(_sample_success_result()),
        serialize_result_for_diagnostics(_sample_failed_result()),
    ]
    forbidden = (_FAKE_PROMPT, _FAKE_CONTEXT, _FAKE_MODEL, _FAKE_RESPONSE_TEXT, "/Users/", "/home/")
    hits = [token for token in forbidden if any(token in text for text in texts)]
    ok = not hits
    return CheckResult(
        name="serialized_diagnostic_forms_exclude_sensitive_text",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def check_error_detail_never_contains_credential_shaped_tokens() -> CheckResult:
    import re

    credential_patterns = (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[A-Za-z0-9]{10,}"),
        re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
    )
    result = _sample_failed_result()
    detail = result.error.detail if result.error else ""
    hits = [p.pattern for p in credential_patterns if p.search(detail)]
    ok = not hits
    return CheckResult(
        name="error_detail_never_contains_credential_shaped_tokens",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def run_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_request_diagnostics_exclude_prompt_and_raw_model_value(),
        check_result_diagnostics_exclude_response_text(),
        check_serialized_forms_exclude_sensitive_text(),
        check_error_detail_never_contains_credential_shaped_tokens(),
    ]
    matrix = {"sample_diagnostic_view_of_request": diagnostic_view_of_request(_sample_request())}
    return checks, matrix


__all__ = [
    "check_error_detail_never_contains_credential_shaped_tokens",
    "check_request_diagnostics_exclude_prompt_and_raw_model_value",
    "check_result_diagnostics_exclude_response_text",
    "check_serialized_forms_exclude_sensitive_text",
    "run_privacy_checks",
]
