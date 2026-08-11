"""Fail-soft: the wrapper still raises the legacy exceptions enrichment expects.

``application.assessment.service._map_provider_error`` classifies a provider
failure by inspecting the raised exception's *message text*, so the wrapper's
messages are load-bearing. These checks pin the exception type, the message
text, and the resulting AI execution status for every SDK failure the
pre-migration provider handled — without any real credential or network call.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import error_mapping, legacy_bridge
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseParsingError,
)
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.application.assessment.service import _map_provider_error
from codestrata.config.settings import OpenAISettings
from codestrata.reporting.modernization_models import AIExecutionStatus
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.contract import (
    LEGACY_EXCEPTION_MATRIX,
    OPENAI_API_KEY_ENV_DEFAULT,
    OPENAI_DEFAULT_ANSWER_MODEL,
)
from verification.openai_provider_migration.models import CheckResult

_UNSET_KEY_VAR = "SYNTHETIC_UNSET_OPENAI_KEY_VAR"

# Which AI execution status each SDK failure must still produce at the assess
# layer. Derived from the legacy message text, which is why the messages are
# pinned in this module rather than merely the exception types.
_AI_STATUS_MATRIX: dict[str, AIExecutionStatus] = {
    "APIConnectionError": AIExecutionStatus.PROVIDER_FAILED,
    "APITimeoutError": AIExecutionStatus.PROVIDER_FAILED,
    "AuthenticationError": AIExecutionStatus.AUTHENTICATION_FAILED,
    "BadRequestError": AIExecutionStatus.PROVIDER_FAILED,
    "InternalServerError": AIExecutionStatus.PROVIDER_FAILED,
    "NotFoundError": AIExecutionStatus.PROVIDER_FAILED,
    "PermissionDeniedError": AIExecutionStatus.AUTHENTICATION_FAILED,
    "RateLimitError": AIExecutionStatus.PROVIDER_FAILED,
    "UnprocessableEntityError": AIExecutionStatus.PROVIDER_FAILED,
}

_LEGACY_EXCEPTION_TYPES: dict[str, type[Exception]] = {
    "AIProviderConfigurationError": AIProviderConfigurationError,
    "AIProviderInvocationError": AIProviderInvocationError,
    "AIProviderTimeoutError": AIProviderTimeoutError,
}


def _invoke(outcome: Any, **provider_kwargs: Any) -> Exception | None:
    """Invoke through the wrapper with an injected client; return what it raised."""

    provider = OpenAIAIModelProvider(
        client=fixtures.Client(outcome) if outcome is not None else None, **provider_kwargs
    )
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    except Exception as error:  # noqa: BLE001 - the raise is what is under test
        return error
    return None


def check_every_sdk_failure_raises_the_legacy_exception_type() -> CheckResult:
    wrong: dict[str, str] = {}
    for class_name, expected_type_name in LEGACY_EXCEPTION_MATRIX.items():
        raised = _invoke(fixtures.sdk_exception(class_name))
        expected = _LEGACY_EXCEPTION_TYPES[expected_type_name]
        if raised is None or type(raised) is not expected:
            wrong[class_name] = type(raised).__name__ if raised else "no exception"
    return CheckResult(
        name="every_sdk_failure_still_raises_its_pre_migration_legacy_exception_type",
        category="fail_soft",
        ok=not wrong,
        detail=f"mismatches={sorted(wrong)}",
        evidence={"matrix_size": len(LEGACY_EXCEPTION_MATRIX)},
    )


def check_every_sdk_failure_maps_to_the_same_ai_status() -> CheckResult:
    wrong: dict[str, str] = {}
    for class_name, expected_status in _AI_STATUS_MATRIX.items():
        raised = _invoke(fixtures.sdk_exception(class_name))
        if raised is None:
            wrong[class_name] = "no exception"
            continue
        mapped = _map_provider_error(raised, model_id=OPENAI_DEFAULT_ANSWER_MODEL)
        if mapped.ai_status is not expected_status:
            wrong[class_name] = mapped.ai_status.value
    return CheckResult(
        name="every_sdk_failure_still_maps_to_the_same_assess_layer_ai_status",
        category="fail_soft",
        ok=not wrong,
        detail=f"mismatches={sorted(wrong)}",
        evidence={"statuses": sorted({status.value for status in _AI_STATUS_MATRIX.values()})},
    )


def check_the_legacy_messages_are_reproduced_verbatim() -> CheckResult:
    expected_messages = {
        "AuthenticationError": (
            "OpenAI authentication failed. Verify API key and model access. Details: {detail}"
        ),
        "PermissionDeniedError": (
            "OpenAI authentication failed. Verify API key and model access. Details: {detail}"
        ),
        "RateLimitError": "OpenAI temporary service failure: {detail}",
        "APITimeoutError": "OpenAI temporary service failure: {detail}",
        "APIConnectionError": "OpenAI temporary service failure: {detail}",
        "InternalServerError": "OpenAI temporary service failure: {detail}",
        "BadRequestError": "OpenAI invalid model or request configuration: {detail}",
        "NotFoundError": "OpenAI invalid model or request configuration: {detail}",
        "UnprocessableEntityError": "OpenAI invalid model or request configuration: {detail}",
    }
    body = "synthetic sdk failure body"
    wrong: list[str] = []
    for class_name, template in expected_messages.items():
        raised = _invoke(fixtures.sdk_exception(class_name, body))
        expected = template.format(detail=sanitize_provider_text(body))
        if raised is None or str(raised) != expected:
            wrong.append(class_name)
    return CheckResult(
        name="the_legacy_failure_messages_are_reproduced_verbatim",
        category="fail_soft",
        ok=not wrong,
        detail=f"reworded_messages={sorted(wrong)}",
    )


def check_a_missing_api_key_raises_the_legacy_configuration_error() -> CheckResult:
    raised = _invoke(None, openai_settings=OpenAISettings(api_key_env=_UNSET_KEY_VAR))
    expected = f"OpenAI API key not found in environment variable {_UNSET_KEY_VAR}"
    ok = isinstance(raised, AIProviderConfigurationError) and str(raised) == expected
    return CheckResult(
        name="a_missing_api_key_still_raises_the_legacy_configuration_error_naming_the_variable",
        category="fail_soft",
        ok=ok,
        detail="the message names the configured environment variable, never its value",
    )


def check_the_missing_key_message_names_whichever_variable_is_configured() -> CheckResult:
    """Asserted at the bridge so no check ever reads a real developer credential."""

    missing_key_error = error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY)
    default_message = str(legacy_bridge.legacy_error_for(missing_key_error))
    custom_message = str(
        legacy_bridge.legacy_error_for(missing_key_error, api_key_env_name=_UNSET_KEY_VAR)
    )
    ok = (
        default_message
        == f"OpenAI API key not found in environment variable {OPENAI_API_KEY_ENV_DEFAULT}"
        and custom_message
        == f"OpenAI API key not found in environment variable {_UNSET_KEY_VAR}"
    )
    return CheckResult(
        name="the_missing_key_message_names_whichever_environment_variable_is_configured",
        category="fail_soft",
        ok=ok,
        detail="the default and an override both appear by name, never by value",
    )


def check_an_empty_response_raises_the_legacy_invocation_error() -> CheckResult:
    raised = _invoke(fixtures.response(""))
    expected = "OpenAI response did not include assistant text"
    ok = isinstance(raised, AIProviderInvocationError) and str(raised) == expected
    return CheckResult(
        name="an_empty_assistant_response_still_raises_the_legacy_invocation_error",
        category="fail_soft",
        ok=ok,
        detail="the pre-migration empty-response message is unchanged",
    )


def check_an_undecodable_response_raises_the_legacy_parsing_error() -> CheckResult:
    raised = _invoke(fixtures.response("this is not json"))
    ok = isinstance(raised, AIResponseParsingError) and raised.metadata is not None
    return CheckResult(
        name="an_undecodable_response_still_raises_the_legacy_parsing_error_with_metadata",
        category="fail_soft",
        ok=ok,
        detail="the legacy recommendation parse path is preserved, metadata included",
    )


def check_failure_messages_carry_no_secret() -> CheckResult:
    """Whatever the SDK says, an api-key-shaped token never reaches the message."""

    secret = "sk-synthetic-failsoft-key-0123456789abcdef"  # noqa: S105 - synthetic
    raised = _invoke(fixtures.sdk_exception("BadRequestError", f"rejected {secret}"))
    message = str(raised)
    return CheckResult(
        name="a_failure_message_never_carries_an_api_key_shaped_token",
        category="fail_soft",
        ok=secret not in message,
        detail="sanitize_provider_text redacts the credential before the message is built",
    )


def check_failure_messages_are_bounded() -> CheckResult:
    raised = _invoke(fixtures.sdk_exception("BadRequestError", "y" * 20000))
    message = str(raised)
    ok = len(message) < 20000
    return CheckResult(
        name="a_failure_message_is_length_bounded_rather_than_echoing_the_whole_body",
        category="fail_soft",
        ok=ok,
        detail=f"message_length_under_the_raw_body={ok}",
    )


def check_exactly_one_provider_call_per_failed_invocation() -> CheckResult:
    client = fixtures.Client(fixtures.sdk_exception("RateLimitError"))
    provider = OpenAIAIModelProvider(client=client)
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options())
    except Exception:  # noqa: BLE001 - counting calls, not asserting the type
        pass
    return CheckResult(
        name="a_failed_invocation_still_makes_exactly_one_provider_call",
        category="fail_soft",
        ok=len(client.calls) == 1,
        detail=f"sdk_calls={len(client.calls)}",
    )


def check_a_blank_model_id_is_rejected_before_any_call() -> CheckResult:
    client = fixtures.Client(fixtures.response())
    provider = OpenAIAIModelProvider(client=client)
    raised: Exception | None = None
    try:
        provider.invoke(fixtures.model_request(), fixtures.invocation_options(model_id="   "))
    except Exception as error:  # noqa: BLE001 - the raise is what is under test
        raised = error
    ok = isinstance(raised, AIProviderConfigurationError) and not client.calls
    return CheckResult(
        name="a_blank_model_id_is_rejected_before_any_provider_call",
        category="fail_soft",
        ok=ok,
        detail=f"sdk_calls={len(client.calls)}",
    )


def check_a_non_positive_timeout_is_rejected_at_construction() -> CheckResult:
    raised: Exception | None = None
    try:
        OpenAIAIModelProvider(timeout_seconds=0)
    except Exception as error:  # noqa: BLE001 - the raise is what is under test
        raised = error
    ok = isinstance(raised, AIProviderConfigurationError)
    return CheckResult(
        name="a_non_positive_timeout_is_still_rejected_at_construction_time",
        category="fail_soft",
        ok=ok,
        detail="timeout_seconds must be positive, unchanged from before the migration",
    )


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_every_sdk_failure_raises_the_legacy_exception_type(),
        check_every_sdk_failure_maps_to_the_same_ai_status(),
        check_the_legacy_messages_are_reproduced_verbatim(),
        check_a_missing_api_key_raises_the_legacy_configuration_error(),
        check_the_missing_key_message_names_whichever_variable_is_configured(),
        check_an_empty_response_raises_the_legacy_invocation_error(),
        check_an_undecodable_response_raises_the_legacy_parsing_error(),
        check_failure_messages_carry_no_secret(),
        check_failure_messages_are_bounded(),
        check_exactly_one_provider_call_per_failed_invocation(),
        check_a_blank_model_id_is_rejected_before_any_call(),
        check_a_non_positive_timeout_is_rejected_at_construction(),
    ]
    matrix: dict[str, Any] = {
        "ai_execution_status_matrix": {
            class_name: status.value for class_name, status in sorted(_AI_STATUS_MATRIX.items())
        },
        "legacy_exception_matrix": dict(sorted(LEGACY_EXCEPTION_MATRIX.items())),
    }
    return checks, matrix


__all__ = [
    "check_a_blank_model_id_is_rejected_before_any_call",
    "check_a_missing_api_key_raises_the_legacy_configuration_error",
    "check_a_non_positive_timeout_is_rejected_at_construction",
    "check_an_empty_response_raises_the_legacy_invocation_error",
    "check_an_undecodable_response_raises_the_legacy_parsing_error",
    "check_every_sdk_failure_maps_to_the_same_ai_status",
    "check_every_sdk_failure_raises_the_legacy_exception_type",
    "check_exactly_one_provider_call_per_failed_invocation",
    "check_failure_messages_are_bounded",
    "check_failure_messages_carry_no_secret",
    "check_the_legacy_messages_are_reproduced_verbatim",
    "check_the_missing_key_message_names_whichever_variable_is_configured",
    "run_fail_soft_checks",
]
