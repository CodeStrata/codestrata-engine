"""Characterize model capability defaults and invocation-option bounds."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from codestrata.ai.providers.factory import (
    CODESTRATA_BEDROCK_MODEL_ID_ENV,
    CODESTRATA_OPENAI_MODEL_ID_ENV,
)
from codestrata.ai.providers.models import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    ModelInvocationOptions,
)
from codestrata.config.settings import BedrockSettings, OpenAISettings
from verification.ai_provider_baseline.contract import ASSESS_ADVISOR_MAX_OUTPUT_TOKENS
from verification.ai_provider_baseline.models import CheckResult


def build_capabilities_matrix() -> dict[str, object]:
    bedrock = BedrockSettings()
    openai = OpenAISettings()
    return {
        "bedrock": {
            "embedding_model_default": bedrock.embedding_model,
            "env_model_override": CODESTRATA_BEDROCK_MODEL_ID_ENV,
        },
        "invocation_defaults": {
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            "temperature": DEFAULT_TEMPERATURE,
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        },
        "modernization_advisor_assess_max_output_tokens": ASSESS_ADVISOR_MAX_OUTPUT_TOKENS,
        "openai": {
            "answer_model_default": openai.answer_model,
            "env_model_override": CODESTRATA_OPENAI_MODEL_ID_ENV,
        },
    }


def check_max_output_tokens_default_is_8192(_source_root: Path) -> CheckResult:
    ok = DEFAULT_MAX_OUTPUT_TOKENS == 8192
    return CheckResult(
        name="default_max_output_tokens_is_8192",
        category="capabilities",
        ok=ok,
        detail=f"DEFAULT_MAX_OUTPUT_TOKENS == {DEFAULT_MAX_OUTPUT_TOKENS}",
    )


def check_temperature_default_is_zero(_source_root: Path) -> CheckResult:
    ok = DEFAULT_TEMPERATURE == 0.0
    return CheckResult(
        name="default_temperature_is_0",
        category="capabilities",
        ok=ok,
        detail=f"DEFAULT_TEMPERATURE == {DEFAULT_TEMPERATURE}",
    )


def check_assess_advisor_overrides_max_output_tokens_to_5000(_source_root: Path) -> CheckResult:
    ok = ASSESS_ADVISOR_MAX_OUTPUT_TOKENS == 5000
    return CheckResult(
        name="assess_advisor_path_overrides_max_output_tokens_to_5000",
        category="capabilities",
        ok=ok,
        detail=(
            "application.assessment.service.DEFAULT_ASSESS_MAX_OUTPUT_TOKENS == "
            f"{ASSESS_ADVISOR_MAX_OUTPUT_TOKENS} (overrides the provider-neutral "
            f"{DEFAULT_MAX_OUTPUT_TOKENS} default at the CLI/application layer)"
        ),
    )


def check_temperature_bounds_enforced(_source_root: Path) -> CheckResult:
    try:
        ModelInvocationOptions(model_id="fixture", temperature=1.5)
    except ValidationError:
        rejected = True
    else:
        rejected = False
    return CheckResult(
        name="model_invocation_options_temperature_bounded_0_to_1",
        category="capabilities",
        ok=rejected,
        detail="ModelInvocationOptions(temperature=1.5) raises ValidationError",
    )


def check_max_output_tokens_must_be_positive(_source_root: Path) -> CheckResult:
    try:
        ModelInvocationOptions(model_id="fixture", max_output_tokens=0)
    except ValidationError:
        rejected = True
    else:
        rejected = False
    return CheckResult(
        name="model_invocation_options_max_output_tokens_must_be_positive",
        category="capabilities",
        ok=rejected,
        detail="ModelInvocationOptions(max_output_tokens=0) raises ValidationError",
    )


def run_capability_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_max_output_tokens_default_is_8192(source_root),
        check_temperature_default_is_zero(source_root),
        check_assess_advisor_overrides_max_output_tokens_to_5000(source_root),
        check_temperature_bounds_enforced(source_root),
        check_max_output_tokens_must_be_positive(source_root),
    ]
    return checks, build_capabilities_matrix()


__all__ = [
    "build_capabilities_matrix",
    "check_assess_advisor_overrides_max_output_tokens_to_5000",
    "check_max_output_tokens_default_is_8192",
    "check_max_output_tokens_must_be_positive",
    "check_temperature_bounds_enforced",
    "check_temperature_default_is_zero",
    "run_capability_checks",
]
