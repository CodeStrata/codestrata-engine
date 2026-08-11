"""Model-resolution cross-checks against the real ``resolve_assess_model_id``.

These checks call the **real** production
``codestrata.ai.providers.factory.resolve_assess_model_id`` (with a
constructed, in-memory ``CodestrataSettings`` — no file I/O) side-by-side
with the pure ``model_configuration.resolve_model_reference``, to prove the
two orders agree. Environment variables are saved and restored around each
check; no network access or real credentials are used.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from codestrata.ai.provider_contracts.identifiers import ProviderId
from codestrata.ai.provider_contracts.model_configuration import resolve_model_reference
from codestrata.ai.providers.factory import (
    CODESTRATA_BEDROCK_MODEL_ID_ENV,
    CODESTRATA_OPENAI_MODEL_ID_ENV,
    resolve_assess_model_id,
)
from codestrata.config.settings import CodestrataSettings
from verification.ai_provider_configuration.models import CheckResult


@contextmanager
def _temporary_environ(overrides: dict[str, str | None]) -> Iterator[None]:
    """Set/unset environment variables for the duration of the block, then restore them."""

    previous: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _settings_with(provider: str, **ai_overrides: Any) -> CodestrataSettings:
    payload: dict[str, Any] = {
        "repository": {"path": "."},
        "ai": {"provider": provider, **ai_overrides},
    }
    return CodestrataSettings.model_validate(payload)


def check_bedrock_default_matches_real_factory() -> CheckResult:
    with _temporary_environ({CODESTRATA_BEDROCK_MODEL_ID_ENV: None}):
        settings = _settings_with("bedrock")
        real = resolve_assess_model_id(cli_model_id=None, settings=settings)
        contract_ref, _source = resolve_model_reference(
            provider_id=ProviderId.BEDROCK,
            cli_model_id=None,
            env_model_id=os.environ.get(CODESTRATA_BEDROCK_MODEL_ID_ENV),
            file_model_id=settings.ai.bedrock.model_id,
        )
    ok = real == contract_ref.value
    return CheckResult(
        name="bedrock_default_model_resolution_matches_real_factory",
        category="model_resolution",
        ok=ok,
        detail=f"real={real!r} contract={contract_ref.redacted()}",
    )


def check_openai_default_matches_real_factory() -> CheckResult:
    with _temporary_environ({CODESTRATA_OPENAI_MODEL_ID_ENV: None}):
        settings = _settings_with("openai")
        real = resolve_assess_model_id(cli_model_id=None, settings=settings)
        contract_ref, _source = resolve_model_reference(
            provider_id=ProviderId.OPENAI,
            cli_model_id=None,
            env_model_id=os.environ.get(CODESTRATA_OPENAI_MODEL_ID_ENV),
            file_model_id=settings.ai.openai.answer_model,
        )
    ok = real == contract_ref.value
    return CheckResult(
        name="openai_default_model_resolution_matches_real_factory",
        category="model_resolution",
        ok=ok,
        detail=f"real={real!r} contract={contract_ref.redacted()}",
    )


def check_cli_model_id_wins_over_everything_for_both_providers() -> CheckResult:
    mismatches: list[str] = []
    for provider, env_var, provider_id in (
        ("bedrock", CODESTRATA_BEDROCK_MODEL_ID_ENV, ProviderId.BEDROCK),
        ("openai", CODESTRATA_OPENAI_MODEL_ID_ENV, ProviderId.OPENAI),
    ):
        with _temporary_environ({env_var: "env-should-lose"}):
            settings = _settings_with(provider)
            real = resolve_assess_model_id(cli_model_id="cli-wins", settings=settings)
            contract_ref, _source = resolve_model_reference(
                provider_id=provider_id,
                cli_model_id="cli-wins",
                env_model_id=os.environ.get(env_var),
                file_model_id=None,
            )
        if real != contract_ref.value or real != "cli-wins":
            mismatches.append(provider)
    ok = not mismatches
    return CheckResult(
        name="cli_model_id_wins_over_environment_and_file_for_both_providers",
        category="model_resolution",
        ok=ok,
        detail=f"mismatches={mismatches}",
    )


def check_bedrock_env_var_is_both_overlaid_and_read_at_resolution_time() -> CheckResult:
    """Ground truth: CODESTRATA_BEDROCK_MODEL_ID is read again at resolve time.

    Unlike CODESTRATA_OPENAI_MODEL_ID, resolve_assess_model_id re-reads
    CODESTRATA_BEDROCK_MODEL_ID directly (rather than only relying on it
    having been overlaid into settings by apply_environment_overlays).
    """

    with _temporary_environ({CODESTRATA_BEDROCK_MODEL_ID_ENV: "env-model-id"}):
        settings = _settings_with("bedrock")  # settings built without overlay applied
        real = resolve_assess_model_id(cli_model_id=None, settings=settings)
    ok = real == "env-model-id"
    return CheckResult(
        name="bedrock_env_var_is_read_directly_at_resolution_time",
        category="model_resolution",
        ok=ok,
        detail=f"real={real!r}",
    )


def run_model_resolution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_bedrock_default_matches_real_factory(),
        check_openai_default_matches_real_factory(),
        check_cli_model_id_wins_over_everything_for_both_providers(),
        check_bedrock_env_var_is_both_overlaid_and_read_at_resolution_time(),
    ]
    matrix = {
        "env_vars_checked": [CODESTRATA_BEDROCK_MODEL_ID_ENV, CODESTRATA_OPENAI_MODEL_ID_ENV]
    }
    return checks, matrix


__all__ = [
    "check_bedrock_default_matches_real_factory",
    "check_bedrock_env_var_is_both_overlaid_and_read_at_resolution_time",
    "check_cli_model_id_wins_over_everything_for_both_providers",
    "check_openai_default_matches_real_factory",
    "run_model_resolution_checks",
]
