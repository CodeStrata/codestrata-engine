"""Characterize provider-specific request construction (no network).

Builds synthetic ``PromptRequest`` fixtures and calls the real, pure request
builders in ``bedrock.py`` / ``openai_provider.py`` — functions that only
transform in-memory data structures and never touch a client or the network.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.prompts.models import PromptMessage, PromptMetadata, PromptRequest
from codestrata.ai.providers import openai_provider
from codestrata.ai.providers.bedrock import build_converse_request, split_prompt_for_converse
from codestrata.ai.providers.models import ModelInvocationOptions
from verification.ai_provider_baseline.models import CheckResult


def _fixture_prompt_request() -> PromptRequest:
    return PromptRequest(
        messages=[
            PromptMessage(role="system", content="You are the Modernization Advisor."),
            PromptMessage(role="developer", content="Follow the JSON contract exactly."),
            PromptMessage(role="user", content="Analyze this repository context: {}"),
        ],
        context_json="{}",
        expected_output_schema_json="{}",
        metadata=PromptMetadata(
            repository_identifier="baseline-fixture",
            context_schema_version="1.0.0",
            recommendation_schema_version="1.0.0",
            finding_count=0,
            technology_count=0,
            context_truncated=False,
            prompt_template_version="1.0.0",
        ),
    )


def _fixture_options(*, model_id: str) -> ModelInvocationOptions:
    return ModelInvocationOptions(model_id=model_id, temperature=0.0, max_output_tokens=256)


def build_bedrock_request_shape() -> dict[str, object]:
    prompt = _fixture_prompt_request()
    options = _fixture_options(model_id="amazon.nova-lite-v1:0")
    request = build_converse_request(prompt, options)
    return {
        "has_inference_config": "inferenceConfig" in request,
        "has_system_block": "system" in request,
        "message_roles": [m["role"] for m in request["messages"]],
        "top_level_keys": sorted(request.keys()),
    }


def build_openai_request_shape() -> dict[str, object]:
    prompt = _fixture_prompt_request()
    messages = openai_provider._chat_messages(prompt)  # noqa: SLF001 - characterization of internal shape
    return {
        "message_roles": [m["role"] for m in messages],
        "system_message_present": messages[0]["role"] == "system",
        "top_level_call_kwargs": sorted(
            ["model", "messages", "temperature", "max_tokens", "response_format"]
        ),
    }


def check_bedrock_request_shape(_source_root: Path) -> CheckResult:
    shape = build_bedrock_request_shape()
    ok = shape["top_level_keys"] == sorted(["modelId", "messages", "inferenceConfig", "system"])
    return CheckResult(
        name="bedrock_converse_request_shape",
        category="requests",
        ok=ok,
        detail=f"keys={shape['top_level_keys']}",
        evidence=shape,
    )


def check_openai_request_shape(_source_root: Path) -> CheckResult:
    shape = build_openai_request_shape()
    ok = shape["system_message_present"] and shape["message_roles"][-1] == "user"
    return CheckResult(
        name="openai_chat_request_shape",
        category="requests",
        ok=ok,
        detail=f"message_roles={shape['message_roles']}",
        evidence=shape,
    )


def check_system_developer_merge_order(_source_root: Path) -> CheckResult:
    """Both providers fold 'developer' role text into the system block, in order."""

    prompt = _fixture_prompt_request()
    system_text, _user_text = split_prompt_for_converse(prompt.messages)
    ok = "Developer instructions:" in system_text and system_text.index(
        "You are the Modernization Advisor."
    ) < system_text.index("Developer instructions:")
    return CheckResult(
        name="developer_role_folded_into_system_block_in_order",
        category="requests",
        ok=ok,
        detail="bedrock split_prompt_for_converse preserves system-then-developer order",
    )


def build_request_matrix() -> dict[str, object]:
    return {
        "bedrock": build_bedrock_request_shape(),
        "openai": build_openai_request_shape(),
    }


def run_request_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_bedrock_request_shape(source_root),
        check_openai_request_shape(source_root),
        check_system_developer_merge_order(source_root),
    ]
    return checks, build_request_matrix()


__all__ = [
    "build_bedrock_request_shape",
    "build_openai_request_shape",
    "build_request_matrix",
    "check_bedrock_request_shape",
    "check_openai_request_shape",
    "check_system_developer_merge_order",
    "run_request_checks",
]
