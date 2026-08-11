"""Fail-soft: the same legacy exception type and message reach enrichment.

``AiEnrichmentService`` degrades an assess run rather than failing it when a
provider raises. Which exception subclass it sees, and what message it
records, is what this module pins — because that is the entire observable
contract between the migrated wrapper and the unchanged enrichment layer.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import error_mapping, legacy_bridge
from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
)
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import LEGACY_EXCEPTION_MATRIX
from verification.bedrock_provider_migration.models import CheckResult

_SDK_EXCEPTION_NAMES = frozenset(error_mapping.SDK_EXCEPTION_NAME_TO_CODE)


def _raise_through_wrapper(outcome: Any) -> BaseException | None:
    provider = BedrockAIModelProvider(client=fixtures.Client(outcome))
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    except BaseException as error:  # noqa: BLE001 - the raised type is the subject
        return error
    return None


def _failure_for(name: str) -> BaseException:
    if name in _SDK_EXCEPTION_NAMES:
        return fixtures.sdk_exception(name)
    return fixtures.client_error(name)


def check_every_failure_raises_the_expected_legacy_exception_type() -> CheckResult:
    mismatches: list[str] = []
    for name, expected in sorted(LEGACY_EXCEPTION_MATRIX.items()):
        raised = _raise_through_wrapper(_failure_for(name))
        actual = type(raised).__name__ if raised is not None else "None"
        if actual != expected:
            mismatches.append(f"{name}:{actual}!={expected}")
    return CheckResult(
        name="every_sdk_failure_still_raises_the_same_legacy_exception_type",
        category="fail_soft",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
        evidence={"failure_cases_checked": len(LEGACY_EXCEPTION_MATRIX)},
    )


def check_every_raised_exception_is_an_ai_provider_error() -> CheckResult:
    """Enrichment catches ``AIProviderError``; nothing may escape that base."""

    offenders: list[str] = []
    for name in sorted(LEGACY_EXCEPTION_MATRIX):
        raised = _raise_through_wrapper(_failure_for(name))
        if not isinstance(raised, AIProviderError):
            offenders.append(name)
    return CheckResult(
        name="every_raised_failure_is_still_an_ai_provider_error_subclass",
        category="fail_soft",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_the_legacy_messages_are_rebuilt_verbatim() -> CheckResult:
    cases = {
        error_mapping.CODE_TIMEOUT: "Bedrock invocation timed out: detail",
        error_mapping.CODE_RATE_LIMITED: "Bedrock temporary service failure: detail",
        error_mapping.CODE_AUTHORIZATION_FAILED: (
            "Bedrock model access denied. Verify IAM permissions for Bedrock "
            "and the selected model. Details: detail"
        ),
        error_mapping.CODE_INVALID_REQUEST: (
            "Bedrock invalid model or request configuration: detail"
        ),
        error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE: "Bedrock invocation failed: detail",
    }
    mismatches: list[str] = []
    for code, expected in cases.items():
        message = str(
            legacy_bridge.legacy_error_for(
                error_mapping.build_error(code), legacy_detail="detail"
            )
        )
        if message != expected:
            mismatches.append(code)
    return CheckResult(
        name="the_legacy_failure_messages_are_rebuilt_verbatim",
        category="fail_soft",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
    )


def check_the_service_error_message_still_names_the_label() -> CheckResult:
    message = str(
        legacy_bridge.legacy_error_for(
            error_mapping.build_error(error_mapping.CODE_SERVICE_ERROR),
            legacy_detail="detail",
            legacy_label="SomeCode",
        )
    )
    return CheckResult(
        name="the_generic_service_error_message_still_interpolates_the_aws_code",
        category="fail_soft",
        ok=message == "Bedrock service error (SomeCode): detail",
        detail="the legacy label is rebuilt from the bridge-only detail",
    )


def check_the_structural_failure_messages_are_unchanged() -> CheckResult:
    from codestrata.ai.providers.bedrock import extract_converse_response

    mismatches: list[str] = []
    for response, expected in (
        ("not-a-mapping", "Bedrock Converse response must be a mapping"),
        ({}, "Bedrock Converse response is missing output"),
        ({"output": {}}, "Bedrock Converse response is missing output.message"),
        (
            {"output": {"message": {}}},
            "Bedrock Converse response is missing output.message.content",
        ),
        (
            {"output": {"message": {"content": []}}},
            "Bedrock Converse response did not include assistant text content",
        ),
    ):
        try:
            extract_converse_response(response)
        except AIProviderInvocationError as error:
            if str(error) != expected:
                mismatches.append(str(error))
        else:
            mismatches.append("no exception raised")
    return CheckResult(
        name="the_four_structural_response_messages_are_unchanged",
        category="fail_soft",
        ok=not mismatches,
        detail=f"mismatches={mismatches}",
    )


def check_a_timeout_is_still_a_timeout_error() -> CheckResult:
    raised = _raise_through_wrapper(fixtures.sdk_exception("ReadTimeoutError"))
    return CheckResult(
        name="a_read_timeout_still_raises_the_legacy_timeout_error",
        category="fail_soft",
        ok=isinstance(raised, AIProviderTimeoutError),
        detail=f"raised={type(raised).__name__}",
    )


def check_a_credential_failure_still_yields_aws_guidance() -> CheckResult:
    raised = _raise_through_wrapper(fixtures.sdk_exception("NoCredentialsError"))
    message = str(raised) if raised is not None else ""
    return CheckResult(
        name="a_missing_credential_still_raises_the_actionable_aws_guidance_message",
        category="fail_soft",
        ok=isinstance(raised, AIProviderInvocationError) and "aws sso login" in message.lower(),
        detail=f"raised={type(raised).__name__}",
    )


def check_a_client_failure_still_yields_a_configuration_error() -> CheckResult:
    error = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_DEPENDENCY),
        legacy_detail="boto3 is not installed",
    )
    return CheckResult(
        name="a_client_construction_failure_still_maps_to_the_legacy_configuration_error",
        category="fail_soft",
        ok=isinstance(error, AIProviderConfigurationError)
        and str(error) == "boto3 is not installed",
        detail="the message the constructor used to raise is preserved verbatim",
    )


def check_a_success_still_returns_legacy_metadata() -> CheckResult:
    provider = BedrockAIModelProvider(
        client=fixtures.Client(fixtures.converse_response(latency_ms=42))
    )
    result = provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    metadata = result.metadata
    return CheckResult(
        name="a_successful_invoke_still_returns_the_legacy_metadata_contract",
        category="fail_soft",
        ok=(
            metadata.provider == "bedrock"
            and metadata.request_id == fixtures.SYNTHETIC_REQUEST_ID
            and metadata.stop_reason == fixtures.SYNTHETIC_STOP_REASON
            and metadata.latency_ms == 42.0
            and metadata.usage.total_tokens == 33
        ),
        detail=f"provider={metadata.provider} latency_ms={metadata.latency_ms}",
    )


def check_an_explicit_request_id_still_overrides_the_provider_one() -> CheckResult:
    provider = BedrockAIModelProvider(client=fixtures.Client(fixtures.converse_response()))
    result = provider.invoke(
        fixtures.model_request(), fixtures.invocation_options(request_id="caller-supplied")
    )
    return CheckResult(
        name="a_caller_supplied_request_id_still_overrides_the_provider_request_id",
        category="fail_soft",
        ok=result.metadata.request_id == "caller-supplied",
        detail=f"request_id_override_honored={result.metadata.request_id == 'caller-supplied'}",
    )


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_every_failure_raises_the_expected_legacy_exception_type(),
        check_every_raised_exception_is_an_ai_provider_error(),
        check_the_legacy_messages_are_rebuilt_verbatim(),
        check_the_service_error_message_still_names_the_label(),
        check_the_structural_failure_messages_are_unchanged(),
        check_a_timeout_is_still_a_timeout_error(),
        check_a_credential_failure_still_yields_aws_guidance(),
        check_a_client_failure_still_yields_a_configuration_error(),
        check_a_success_still_returns_legacy_metadata(),
        check_an_explicit_request_id_still_overrides_the_provider_one(),
    ]
    matrix: dict[str, Any] = {
        "enrichment_catches": "AIProviderError",
        "legacy_exception_matrix": dict(sorted(LEGACY_EXCEPTION_MATRIX.items())),
        "raise_based_fail_soft_preserved": True,
    }
    return checks, matrix


__all__ = [
    "check_a_client_failure_still_yields_a_configuration_error",
    "check_a_credential_failure_still_yields_aws_guidance",
    "check_a_success_still_returns_legacy_metadata",
    "check_a_timeout_is_still_a_timeout_error",
    "check_an_explicit_request_id_still_overrides_the_provider_one",
    "check_every_failure_raises_the_expected_legacy_exception_type",
    "check_every_raised_exception_is_an_ai_provider_error",
    "check_the_legacy_messages_are_rebuilt_verbatim",
    "check_the_service_error_message_still_names_the_label",
    "check_the_structural_failure_messages_are_unchanged",
    "run_fail_soft_checks",
]
