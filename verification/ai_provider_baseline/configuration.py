"""Characterize AI-relevant settings defaults (pure Pydantic model construction).

No I/O, no file reads beyond ``ast``-parsing ``config/settings.py`` for the
structural field inventory (see :mod:`verification.ai_provider_baseline.inventory`).
"""

from __future__ import annotations

from pathlib import Path

from codestrata.config.settings import AiSettings, AwsSettings, BedrockSettings, OpenAISettings
from verification.ai_provider_baseline.inventory import find_settings_classes
from verification.ai_provider_baseline.models import CheckResult


def build_settings_defaults_matrix() -> dict[str, dict[str, object]]:
    """Deterministic snapshot of default field values for AI-relevant settings."""

    ai = AiSettings()
    bedrock = BedrockSettings()
    openai = OpenAISettings()
    aws = AwsSettings()
    return {
        "ai": {
            "answer_provider": ai.answer_provider,
            "embedding_provider": ai.embedding_provider,
            "provider": ai.provider,
        },
        "aws": {
            "profile": aws.profile,
            "region": aws.region,
        },
        "bedrock": {
            "answer_model": bedrock.answer_model,
            "embedding_model": bedrock.embedding_model,
            "max_retries": bedrock.max_retries,
            "model_id": bedrock.model_id,
            "region": bedrock.region,
            "timeout_seconds": bedrock.timeout_seconds,
        },
        "openai": {
            "answer_model": openai.answer_model,
            "api_key_env": openai.api_key_env,
            "base_url": openai.base_url,
            "embedding_dimensions": openai.embedding_dimensions,
            "embedding_model": openai.embedding_model,
            "max_retries": openai.max_retries,
            "timeout_seconds": openai.timeout_seconds,
        },
    }


def check_bedrock_timeout_default_is_60(_source_root: Path) -> CheckResult:
    bedrock = BedrockSettings()
    ok = bedrock.timeout_seconds == 60
    return CheckResult(
        name="bedrock_settings_timeout_seconds_default_is_60",
        category="configuration",
        ok=ok,
        detail=f"BedrockSettings().timeout_seconds == {bedrock.timeout_seconds}",
    )


def check_openai_timeout_default_is_60(_source_root: Path) -> CheckResult:
    openai = OpenAISettings()
    ok = openai.timeout_seconds == 60
    return CheckResult(
        name="openai_settings_timeout_seconds_default_is_60",
        category="configuration",
        ok=ok,
        detail=f"OpenAISettings().timeout_seconds == {openai.timeout_seconds}",
    )


def check_max_retries_fields_exist(_source_root: Path) -> CheckResult:
    bedrock = BedrockSettings()
    openai = OpenAISettings()
    ok = bedrock.max_retries == 3 and openai.max_retries == 3
    return CheckResult(
        name="max_retries_settings_fields_exist_with_default_3",
        category="configuration",
        ok=ok,
        detail=(
            f"bedrock.max_retries={bedrock.max_retries} openai.max_retries={openai.max_retries}"
        ),
    )


def check_settings_field_inventory_matches(source_root: Path) -> CheckResult:
    inventory = find_settings_classes(source_root)
    names = sorted(str(item["class_name"]) for item in inventory)
    expected = sorted(("AiSettings", "AwsSettings", "BedrockSettings", "OpenAISettings"))
    ok = names == expected
    return CheckResult(
        name="ai_settings_classes_present_in_config_settings_module",
        category="configuration",
        ok=ok,
        detail=f"found={names}",
        evidence={"classes": inventory},
    )


def run_configuration_checks(
    source_root: Path,
) -> tuple[list[CheckResult], dict[str, dict[str, object]]]:
    checks = [
        check_bedrock_timeout_default_is_60(source_root),
        check_openai_timeout_default_is_60(source_root),
        check_max_retries_fields_exist(source_root),
        check_settings_field_inventory_matches(source_root),
    ]
    matrix = build_settings_defaults_matrix()
    return checks, matrix


__all__ = [
    "build_settings_defaults_matrix",
    "check_bedrock_timeout_default_is_60",
    "check_max_retries_fields_exist",
    "check_openai_timeout_default_is_60",
    "check_settings_field_inventory_matches",
    "run_configuration_checks",
]
