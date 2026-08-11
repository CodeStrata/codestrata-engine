"""Privacy tests: prompts/responses/credentials/paths must never leak."""

from __future__ import annotations

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

_CREDENTIAL_LOOKING_TEXT = "aws_secret_access_key=AKIAABCDEFGHIJKLMNOP"
_PATH_LOOKING_TEXT = "/Users/someone/.codestrata/secrets.json"
_PROMPT_TEXT = "Please modernize this repository and never reveal " + _CREDENTIAL_LOOKING_TEXT


def test_request_diagnostics_never_include_instruction_or_context_text() -> None:
    request = AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=_PROMPT_TEXT,
            context_payload_text=_PATH_LOOKING_TEXT,
        ),
        response_expectation=ResponseExpectation.TEXT,
        model_reference=ProviderModelReference("secret-internal-model-name"),
    )
    view = diagnostic_view_of_request(request)
    blob = repr(view)
    assert _PROMPT_TEXT not in blob
    assert _CREDENTIAL_LOOKING_TEXT not in blob
    assert _PATH_LOOKING_TEXT not in blob
    assert "secret-internal-model-name" not in blob
    assert view["model_reference"] == "[model_ref]"


def test_result_diagnostics_never_include_content_text() -> None:
    result = AIProviderResult(
        provider_id=ProviderId.OPENAI,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.SUCCESS,
        content=AIProviderResultContent(
            text=_PROMPT_TEXT, structured_payload={"secret": _CREDENTIAL_LOOKING_TEXT}
        ),
    )
    view = diagnostic_view_of_result(result)
    blob = repr(view)
    assert _PROMPT_TEXT not in blob
    assert _CREDENTIAL_LOOKING_TEXT not in blob


def test_serialized_forms_never_include_sensitive_text() -> None:
    request = AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=_PROMPT_TEXT, context_payload_text=_PATH_LOOKING_TEXT
        ),
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        model_reference=ProviderModelReference("another-secret-model"),
    )
    result = AIProviderResult(
        provider_id=ProviderId.BEDROCK,
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        status=ProviderExecutionStatus.FAILED,
        error=AIProviderError(
            category=ErrorCategory.AUTHENTICATION_FAILED,
            code="missing_credentials",
            detail="credentials were not found in the configured location",
        ),
    )
    for text in (
        serialize_request_for_diagnostics(request),
        serialize_result_for_diagnostics(result),
    ):
        assert _PROMPT_TEXT not in text
        assert _CREDENTIAL_LOOKING_TEXT not in text
        assert _PATH_LOOKING_TEXT not in text
        assert "another-secret-model" not in text
        assert "/Users/" not in text
        assert "/home/" not in text


def test_provider_model_reference_value_is_never_equal_to_its_redacted_form() -> None:
    ref = ProviderModelReference("gpt-4o-mini")
    assert ref.value != ref.redacted()
