"""Request mapping: byte-compatible prompts and an unchanged wire shape.

Every check compares the migrated mapping against the *pre-migration*
``_chat_messages`` implementation, which is still present in
``ai/providers/openai_provider.py`` as a retained module helper. Prompt
*content* is compared inside this module and never recorded: the report
carries only structural facts (kwarg names, role order, equality booleans).
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import legacy_bridge, request_mapping
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.providers.openai_provider import _chat_messages
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.contract import (
    DEVELOPER_PREFIX,
    EXPECTED_CHAT_KWARG_NAMES,
    EXPECTED_MESSAGE_ROLES,
    JSON_RESPONSE_FORMAT,
    OPENAI_DEFAULT_ANSWER_MODEL,
    STRUCTURED_JSON_INSTRUCTION,
)
from verification.openai_provider_migration.models import CheckResult


def _migrated_messages(prompt_request: Any) -> list[dict[str, str]]:
    payload = legacy_bridge.fold_prompt_request(prompt_request)
    return request_mapping.build_chat_messages(
        payload, response_expectation=ResponseExpectation.STRUCTURED_JSON
    )


def check_prompt_folding_is_byte_compatible() -> CheckResult:
    """The migrated path reproduces ``_chat_messages`` byte for byte."""

    cases = {
        "system_developer_user": fixtures.prompt_request(),
        "system_and_user_only": fixtures.prompt_request(developer=None),
        "developer_and_user_only": fixtures.prompt_request(system=None),
        "user_only": fixtures.prompt_request(system=None, developer=None),
    }
    mismatches = sorted(
        name
        for name, prompt_request in cases.items()
        if _migrated_messages(prompt_request) != _chat_messages(prompt_request)
    )
    return CheckResult(
        name="migrated_prompt_folding_is_byte_identical_to_the_pre_migration_helper",
        category="requests",
        ok=not mismatches,
        detail=f"mismatched_cases={mismatches}",
        evidence={"cases_compared": sorted(cases)},
    )


def check_message_roles_and_order_are_unchanged() -> CheckResult:
    messages = _migrated_messages(fixtures.prompt_request())
    roles = tuple(message["role"] for message in messages)
    return CheckResult(
        name="message_roles_and_order_are_still_system_then_user",
        category="requests",
        ok=roles == EXPECTED_MESSAGE_ROLES,
        detail=f"message_roles={list(roles)}",
    )


def check_developer_instructions_prefix_is_unchanged() -> CheckResult:
    messages = _migrated_messages(fixtures.prompt_request())
    system_content = messages[0]["content"]
    ok = (
        legacy_bridge.DEVELOPER_PREFIX == DEVELOPER_PREFIX
        and DEVELOPER_PREFIX in system_content
    )
    return CheckResult(
        name="developer_messages_still_carry_the_developer_instructions_prefix",
        category="requests",
        ok=ok,
        detail="the folded system message contains the unchanged developer prefix",
    )


def check_structured_json_instruction_is_appended_exactly_once() -> CheckResult:
    messages = _migrated_messages(fixtures.prompt_request())
    system_content = messages[0]["content"]
    occurrences = system_content.count(STRUCTURED_JSON_INSTRUCTION)
    ok = (
        request_mapping.STRUCTURED_JSON_INSTRUCTION == STRUCTURED_JSON_INSTRUCTION
        and occurrences == 1
        and system_content.endswith(STRUCTURED_JSON_INSTRUCTION)
    )
    return CheckResult(
        name="the_structured_json_instruction_is_appended_exactly_once_at_the_end",
        category="requests",
        ok=ok,
        detail=f"json_instruction_occurrences={occurrences}",
    )


def check_the_degenerate_prompt_does_not_double_append() -> CheckResult:
    """A prompt with no system/developer message yields exactly one instruction."""

    prompt_request = fixtures.prompt_request(system=None, developer=None)
    messages = _migrated_messages(prompt_request)
    system_content = messages[0]["content"]
    ok = (
        messages == _chat_messages(prompt_request)
        and system_content.count(STRUCTURED_JSON_INSTRUCTION) == 1
    )
    return CheckResult(
        name="a_prompt_without_system_or_developer_text_does_not_double_append",
        category="requests",
        ok=ok,
        detail="the folded instruction fallback is not appended twice",
    )


def check_text_expectation_omits_json_mode_and_the_trailer() -> CheckResult:
    request = fixtures.provider_request(response_expectation=ResponseExpectation.TEXT)
    kwargs = request_mapping.build_chat_completion_kwargs(request)
    system_content = kwargs["messages"][0]["content"]
    ok = "response_format" not in kwargs and STRUCTURED_JSON_INSTRUCTION not in system_content
    return CheckResult(
        name="a_text_expectation_requests_neither_json_mode_nor_the_json_trailer",
        category="requests",
        ok=ok,
        detail=f"kwarg_names={sorted(kwargs)}",
    )


def check_json_response_format_is_unchanged() -> CheckResult:
    kwargs = request_mapping.build_chat_completion_kwargs(fixtures.provider_request())
    ok = (
        kwargs.get("response_format") == JSON_RESPONSE_FORMAT
        and request_mapping.JSON_RESPONSE_FORMAT == JSON_RESPONSE_FORMAT
    )
    return CheckResult(
        name="structured_json_still_requests_the_json_object_response_format",
        category="requests",
        ok=ok,
        detail="response_format={'type': 'json_object'}",
    )


def check_wire_kwargs_are_exactly_the_pre_migration_set() -> CheckResult:
    kwargs = request_mapping.build_chat_completion_kwargs(fixtures.provider_request())
    actual = tuple(sorted(kwargs))
    return CheckResult(
        name="chat_completions_receives_exactly_the_pre_migration_kwarg_set",
        category="requests",
        ok=actual == tuple(sorted(EXPECTED_CHAT_KWARG_NAMES)),
        detail=f"kwarg_names={list(actual)}",
    )


def check_optional_options_are_omitted_when_unset() -> CheckResult:
    request = fixtures.provider_request(temperature=None, max_tokens=None)
    kwargs = request_mapping.build_chat_completion_kwargs(request)
    ok = "temperature" not in kwargs and "max_tokens" not in kwargs
    return CheckResult(
        name="unset_temperature_and_max_tokens_are_omitted_rather_than_defaulted",
        category="requests",
        ok=ok,
        detail=f"kwarg_names={sorted(kwargs)}",
    )


def check_the_model_value_comes_only_from_the_request() -> CheckResult:
    """No default model is baked into the adapter's request mapping."""

    request = fixtures.provider_request(model_id=OPENAI_DEFAULT_ANSWER_MODEL)
    kwargs = request_mapping.build_chat_completion_kwargs(request)
    module_text_has_default = (
        OPENAI_DEFAULT_ANSWER_MODEL in request_mapping.__doc__ if request_mapping.__doc__ else False
    )
    ok = kwargs["model"] == OPENAI_DEFAULT_ANSWER_MODEL and not module_text_has_default
    return CheckResult(
        name="the_model_value_is_taken_from_the_request_and_never_defaulted_in_the_mapping",
        category="requests",
        ok=ok,
        detail="model_reference.value is forwarded verbatim",
    )


def check_request_shape_is_prompt_free() -> CheckResult:
    shape = request_mapping.request_shape(fixtures.provider_request())
    serialized = repr(shape)
    leaked = [
        label
        for label, value in (
            ("instruction", fixtures.SYNTHETIC_INSTRUCTION),
            ("context", fixtures.SYNTHETIC_CONTEXT),
            ("model", OPENAI_DEFAULT_ANSWER_MODEL),
        )
        if value in serialized
    ]
    return CheckResult(
        name="the_reportable_request_shape_contains_no_prompt_or_model_value",
        category="requests",
        ok=not leaked,
        detail=f"leaked_fields={leaked}",
        evidence={"shape_keys": sorted(shape)},
    )


def run_request_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_prompt_folding_is_byte_compatible(),
        check_message_roles_and_order_are_unchanged(),
        check_developer_instructions_prefix_is_unchanged(),
        check_structured_json_instruction_is_appended_exactly_once(),
        check_the_degenerate_prompt_does_not_double_append(),
        check_text_expectation_omits_json_mode_and_the_trailer(),
        check_json_response_format_is_unchanged(),
        check_wire_kwargs_are_exactly_the_pre_migration_set(),
        check_optional_options_are_omitted_when_unset(),
        check_the_model_value_comes_only_from_the_request(),
        check_request_shape_is_prompt_free(),
    ]
    matrix: dict[str, Any] = {
        "expected_chat_kwarg_names": list(EXPECTED_CHAT_KWARG_NAMES),
        "expected_message_roles": list(EXPECTED_MESSAGE_ROLES),
        "json_response_format": dict(JSON_RESPONSE_FORMAT),
        "structured_json_request_shape": request_mapping.request_shape(
            fixtures.provider_request()
        ),
        "text_request_shape": request_mapping.request_shape(
            fixtures.provider_request(response_expectation=ResponseExpectation.TEXT)
        ),
    }
    return checks, matrix


__all__ = [
    "check_developer_instructions_prefix_is_unchanged",
    "check_json_response_format_is_unchanged",
    "check_message_roles_and_order_are_unchanged",
    "check_optional_options_are_omitted_when_unset",
    "check_prompt_folding_is_byte_compatible",
    "check_request_shape_is_prompt_free",
    "check_structured_json_instruction_is_appended_exactly_once",
    "check_text_expectation_omits_json_mode_and_the_trailer",
    "check_the_degenerate_prompt_does_not_double_append",
    "check_the_model_value_comes_only_from_the_request",
    "check_wire_kwargs_are_exactly_the_pre_migration_set",
    "run_request_checks",
]
