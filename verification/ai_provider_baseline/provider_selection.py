"""Characterize assess AI provider selection (no client construction).

Exercises the real Engine selection logic (``AssessAIProviderRegistry`` and
``resolve_assess_model_id``) but never instantiates a live provider — the
registry raises before touching credentials for unsupported names, and model
ID resolution is pure string logic.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.factory import (
    CODESTRATA_BEDROCK_MODEL_ID_ENV,
    CODESTRATA_OPENAI_MODEL_ID_ENV,
    resolve_assess_model_id,
    supported_assess_ai_providers,
)
from codestrata.config.settings import CodestrataSettings, RepositorySettings
from codestrata.extensions.assess_ai import get_assess_ai_provider_registry
from verification.ai_provider_baseline.contract import (
    DEFAULT_ASSESS_PROVIDER,
    DEFAULT_MODEL_IDS,
    ENGINE_PROVIDER_IDS,
)
from verification.ai_provider_baseline.models import CheckResult


def _settings(*, provider: str = "bedrock", path: str = ".") -> CodestrataSettings:
    settings = CodestrataSettings(repository=RepositorySettings(path=path))
    settings.ai.provider = provider
    return settings


def check_default_provider(_source_root: Path) -> CheckResult:
    settings = _settings()
    ok = settings.ai.provider == DEFAULT_ASSESS_PROVIDER
    return CheckResult(
        name="default_assess_provider_is_bedrock",
        category="provider_selection",
        ok=ok,
        detail=f"CodestrataSettings().ai.provider == {settings.ai.provider!r}",
    )


def check_supported_providers(_source_root: Path) -> CheckResult:
    supported = frozenset(supported_assess_ai_providers())
    ok = supported == frozenset(ENGINE_PROVIDER_IDS)
    return CheckResult(
        name="supported_providers_are_bedrock_openai_and_openrouter",
        category="provider_selection",
        ok=ok,
        detail=f"registered={sorted(supported)}",
    )


def check_unsupported_provider_raises_before_credentials(_source_root: Path) -> CheckResult:
    registry = get_assess_ai_provider_registry()
    settings = _settings(provider="not-a-real-provider")
    try:
        registry.create("not-a-real-provider", settings)
    except AIProviderConfigurationError:
        # Detail records exception *type* only — never raw exception text
        # (Slice 11.1 report must not leak provider/user-facing error messages).
        return CheckResult(
            name="unsupported_provider_raises_configuration_error",
            category="provider_selection",
            ok=True,
            detail="raised AIProviderConfigurationError for unregistered provider",
        )
    except Exception as error:  # noqa: BLE001 - characterization boundary
        return CheckResult(
            name="unsupported_provider_raises_configuration_error",
            category="provider_selection",
            ok=False,
            detail=f"unexpected exception type {type(error).__name__}",
        )
    return CheckResult(
        name="unsupported_provider_raises_configuration_error",
        category="provider_selection",
        ok=False,
        detail="registry.create() did not raise for an unregistered provider name",
    )


def build_model_id_resolution_matrix(
    monkeypatch_env: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Deterministic matrix of resolve_assess_model_id() precedence scenarios.

    ``monkeypatch_env`` is accepted for test injection but this function does
    not itself mutate ``os.environ`` — callers control environment isolation.
    """

    del monkeypatch_env
    scenarios: list[dict[str, object]] = []

    # OpenRouter has no product default model — only bedrock/openai participate
    # in the default-model resolution matrix.
    for provider in ("bedrock", "openai"):
        settings = _settings(provider=provider)
        resolved_default = resolve_assess_model_id(cli_model_id=None, settings=settings)
        scenarios.append(
            {
                "cli_model_id": None,
                "expected_source": "hardcoded_default",
                "provider": provider,
                "resolved_model_id": resolved_default,
            }
        )
        scenarios.append(
            {
                "cli_model_id": "explicit-cli-model-id",
                "expected_source": "cli_argument",
                "provider": provider,
                "resolved_model_id": resolve_assess_model_id(
                    cli_model_id="explicit-cli-model-id", settings=settings
                ),
            }
        )
        configured_settings = _settings(provider=provider)
        if provider == "bedrock":
            configured_settings.ai.bedrock.model_id = "configured-bedrock-model"
        else:
            configured_settings.ai.openai.answer_model = "configured-openai-model"
        scenarios.append(
            {
                "cli_model_id": None,
                "expected_source": "codestrata_toml_setting",
                "provider": provider,
                "resolved_model_id": resolve_assess_model_id(
                    cli_model_id=None, settings=configured_settings
                ),
            }
        )

    scenarios.sort(key=lambda item: (str(item["provider"]), str(item["expected_source"])))
    return scenarios


def env_override_names() -> dict[str, str]:
    return {
        "bedrock": CODESTRATA_BEDROCK_MODEL_ID_ENV,
        "openai": CODESTRATA_OPENAI_MODEL_ID_ENV,
    }


def check_default_model_ids_match_ground_truth(_source_root: Path) -> CheckResult:
    settings_bedrock = _settings(provider="bedrock")
    settings_openai = _settings(provider="openai")
    resolved = {
        "bedrock": resolve_assess_model_id(cli_model_id=None, settings=settings_bedrock),
        "openai": resolve_assess_model_id(cli_model_id=None, settings=settings_openai),
    }
    ok = resolved == DEFAULT_MODEL_IDS
    return CheckResult(
        name="default_model_ids_match_ground_truth",
        category="provider_selection",
        ok=ok,
        detail=f"resolved={resolved} expected={DEFAULT_MODEL_IDS}",
    )


def run_provider_selection_checks(
    source_root: Path,
) -> tuple[list[CheckResult], list[dict[str, object]]]:
    checks = [
        check_default_provider(source_root),
        check_supported_providers(source_root),
        check_unsupported_provider_raises_before_credentials(source_root),
        check_default_model_ids_match_ground_truth(source_root),
    ]
    matrix = build_model_id_resolution_matrix()
    return checks, matrix


__all__ = [
    "build_model_id_resolution_matrix",
    "check_default_model_ids_match_ground_truth",
    "check_default_provider",
    "check_supported_providers",
    "check_unsupported_provider_raises_before_credentials",
    "env_override_names",
    "run_provider_selection_checks",
]
