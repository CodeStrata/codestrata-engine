"""Converse request mapping: the wire shape and the prompt bytes are unchanged."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import request_mapping
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_adapters.bedrock.legacy_bridge import (
    DEVELOPER_PREFIX,
    build_provider_request,
    fold_prompt_messages,
)
from codestrata.ai.prompts.models import PromptMessage
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.providers.bedrock import build_converse_request, split_prompt_for_converse
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import (
    DEVELOPER_PREFIX as EXPECTED_DEVELOPER_PREFIX,
    EXPECTED_CONVERSE_KWARG_NAMES,
    EXPECTED_INFERENCE_CONFIG_KEYS,
    EXPECTED_MESSAGE_ROLES,
    FORBIDDEN_REQUEST_KWARG_NAMES,
    STRUCTURED_JSON_INSTRUCTION,
    SUPPORTS_NATIVE_STRUCTURED_JSON,
)
from verification.bedrock_provider_migration.models import CheckResult


def _sent_kwargs(request: Any = None) -> dict[str, Any]:
    client = fixtures.Client()
    build_bedrock_provider(client=client).execute(request or fixtures.provider_request())
    return client.calls[0]


def check_the_converse_kwarg_names_are_unchanged() -> CheckResult:
    kwargs = _sent_kwargs()
    actual = tuple(sorted(kwargs))
    return CheckResult(
        name="the_converse_call_sends_exactly_model_id_messages_inference_config_and_system",
        category="requests",
        ok=actual == EXPECTED_CONVERSE_KWARG_NAMES,
        detail=f"kwarg_names={list(actual)}",
    )


def check_no_openai_style_kwarg_is_sent() -> CheckResult:
    kwargs = _sent_kwargs()
    offenders = sorted(name for name in FORBIDDEN_REQUEST_KWARG_NAMES if name in kwargs)
    return CheckResult(
        name="no_openai_style_kwarg_leaked_into_the_converse_call",
        category="requests",
        ok=not offenders,
        detail=f"offending_kwargs={offenders}",
        evidence={"forbidden_kwarg_names": list(FORBIDDEN_REQUEST_KWARG_NAMES)},
    )


def check_the_message_shape_is_unchanged() -> CheckResult:
    messages = _sent_kwargs()["messages"]
    roles = tuple(message["role"] for message in messages)
    single_text_block = (
        len(messages) == 1
        and isinstance(messages[0]["content"], list)
        and len(messages[0]["content"]) == 1
        and set(messages[0]["content"][0]) == {"text"}
    )
    return CheckResult(
        name="the_converse_messages_array_is_one_user_message_with_one_text_block",
        category="requests",
        ok=roles == EXPECTED_MESSAGE_ROLES and single_text_block,
        detail=f"message_roles={list(roles)} message_count={len(messages)}",
    )


def check_the_inference_config_shape_is_unchanged() -> CheckResult:
    inference_config = _sent_kwargs()["inferenceConfig"]
    actual = tuple(sorted(inference_config))
    return CheckResult(
        name="the_inference_config_carries_max_tokens_and_temperature",
        category="requests",
        ok=actual == EXPECTED_INFERENCE_CONFIG_KEYS,
        detail=f"inference_config_keys={list(actual)}",
    )


def check_the_system_block_shape_is_unchanged() -> CheckResult:
    system = _sent_kwargs()["system"]
    return CheckResult(
        name="the_system_block_is_a_single_text_entry",
        category="requests",
        ok=(
            isinstance(system, list)
            and len(system) == 1
            and set(system[0]) == {"text"}
        ),
        detail=f"system_block_count={len(system) if isinstance(system, list) else 0}",
    )


def check_the_json_instruction_is_still_appended() -> CheckResult:
    system_text = _sent_kwargs()["system"][0]["text"]
    return CheckResult(
        name="the_structured_json_instruction_is_still_appended_to_the_system_block",
        category="requests",
        ok=system_text.endswith(STRUCTURED_JSON_INSTRUCTION),
        detail="prompt-instruction-only structured JSON, unchanged",
        evidence={"supports_native_structured_json": SUPPORTS_NATIVE_STRUCTURED_JSON},
    )


def check_the_json_instruction_is_never_doubled() -> CheckResult:
    """A prompt with no system/developer message must not repeat the sentence."""

    request = build_provider_request(
        fixtures.prompt_request(system=None, developer=None),
        fixtures.invocation_options(),
        model_id="synthetic-model",
    )
    system_text = request_mapping.build_converse_kwargs(request)["system"][0]["text"]
    return CheckResult(
        name="the_structured_json_instruction_is_never_appended_twice",
        category="requests",
        ok=system_text.count(STRUCTURED_JSON_INSTRUCTION) == 1,
        detail=f"instruction_occurrences={system_text.count(STRUCTURED_JSON_INSTRUCTION)}",
    )


def check_the_developer_prefix_is_unchanged() -> CheckResult:
    payload = fold_prompt_messages(
        [
            PromptMessage(role="system", content="alpha"),
            PromptMessage(role="developer", content="beta"),
            PromptMessage(role="user", content="gamma"),
        ]
    )
    expected = f"alpha\n\n{EXPECTED_DEVELOPER_PREFIX}beta"
    return CheckResult(
        name="system_and_developer_text_fold_with_the_unchanged_developer_prefix",
        category="requests",
        ok=payload.instruction_text == expected and DEVELOPER_PREFIX == EXPECTED_DEVELOPER_PREFIX,
        detail="instruction text folds system, then the prefixed developer block",
    )


def check_multiple_user_messages_join_with_a_blank_line() -> CheckResult:
    payload = fold_prompt_messages(
        [
            PromptMessage(role="system", content="alpha"),
            PromptMessage(role="user", content="one"),
            PromptMessage(role="user", content="two"),
        ]
    )
    return CheckResult(
        name="multiple_user_messages_still_join_with_a_blank_line",
        category="requests",
        ok=payload.context_payload_text == "one\n\ntwo",
        detail="user parts joined with a blank line, unchanged",
    )


def check_the_module_level_helper_matches_the_adapter() -> CheckResult:
    """``build_converse_request`` and the adapter must produce identical kwargs."""

    prompt = fixtures.prompt_request()
    options = fixtures.invocation_options()
    helper_kwargs = build_converse_request(prompt, options)
    adapter_kwargs = request_mapping.build_converse_kwargs(
        build_provider_request(prompt, options, model_id=options.model_id)
    )
    return CheckResult(
        name="the_module_level_build_converse_request_matches_the_adapter_mapping",
        category="requests",
        ok=helper_kwargs == adapter_kwargs,
        detail="the retained helper and the adapter share one mapping implementation",
    )


def check_the_split_helper_matches_the_system_text_mapping() -> CheckResult:
    messages = fixtures.prompt_request().messages
    system_text, user_text = split_prompt_for_converse(list(messages))
    payload = fold_prompt_messages(messages)
    expected_system = request_mapping.build_system_text(
        payload.instruction_text, response_expectation=ResponseExpectation.STRUCTURED_JSON
    )
    return CheckResult(
        name="the_module_level_split_prompt_helper_matches_the_adapter_system_text",
        category="requests",
        ok=system_text == expected_system and user_text == payload.context_payload_text,
        detail="the retained helper and the adapter share one folding implementation",
    )


def check_the_request_shape_view_is_prompt_free() -> CheckResult:
    shape = request_mapping.request_shape(fixtures.provider_request())
    rendered = repr(shape)
    leaked = sorted(
        token
        for token in (fixtures.SYNTHETIC_INSTRUCTION, fixtures.SYNTHETIC_CONTEXT)
        if token in rendered
    )
    return CheckResult(
        name="the_request_shape_diagnostic_view_records_structure_and_no_prompt_text",
        category="requests",
        ok=not leaked and shape["json_mode_requested"] is False,
        detail=f"leaked={leaked}",
    )


def run_request_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_converse_kwarg_names_are_unchanged(),
        check_no_openai_style_kwarg_is_sent(),
        check_the_message_shape_is_unchanged(),
        check_the_inference_config_shape_is_unchanged(),
        check_the_system_block_shape_is_unchanged(),
        check_the_json_instruction_is_still_appended(),
        check_the_json_instruction_is_never_doubled(),
        check_the_developer_prefix_is_unchanged(),
        check_multiple_user_messages_join_with_a_blank_line(),
        check_the_module_level_helper_matches_the_adapter(),
        check_the_split_helper_matches_the_system_text_mapping(),
        check_the_request_shape_view_is_prompt_free(),
    ]
    matrix: dict[str, Any] = {
        "converse_kwarg_names": list(EXPECTED_CONVERSE_KWARG_NAMES),
        "inference_config_keys": list(EXPECTED_INFERENCE_CONFIG_KEYS),
        "message_roles": list(EXPECTED_MESSAGE_ROLES),
        "native_structured_json_supported": SUPPORTS_NATIVE_STRUCTURED_JSON,
        "structured_json_strategy": "prompt_instruction_only",
    }
    return checks, matrix


__all__ = [
    "check_multiple_user_messages_join_with_a_blank_line",
    "check_no_openai_style_kwarg_is_sent",
    "check_the_converse_kwarg_names_are_unchanged",
    "check_the_developer_prefix_is_unchanged",
    "check_the_inference_config_shape_is_unchanged",
    "check_the_json_instruction_is_never_doubled",
    "check_the_json_instruction_is_still_appended",
    "check_the_message_shape_is_unchanged",
    "check_the_module_level_helper_matches_the_adapter",
    "check_the_request_shape_view_is_prompt_free",
    "check_the_split_helper_matches_the_system_text_mapping",
    "check_the_system_block_shape_is_unchanged",
    "run_request_checks",
]
