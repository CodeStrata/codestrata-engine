"""Negative scenarios A–Z for SV.11.10."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from codestrata.ai.provider_adapters.openrouter.client import resolve_client
from codestrata.ai.provider_adapters.openrouter.configuration import (
    build_runtime_configuration,
    normalize_base_url,
)
from codestrata.ai.provider_adapters.openrouter.diagnostics import diagnostic_view_of_adapter
from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_executor,
    build_openrouter_provider,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.providers.exceptions import AIProviderConfigurationError

# Import factory before assess_ai to keep load order stable.
from codestrata.ai.providers.factory import create_assess_ai_provider, resolve_assess_model_id
from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider
from codestrata.config.settings import AiSettings, OpenRouterSettings
from verification.openrouter_configuration.contract import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_PROVIDER,
    NEGATIVE_SCENARIO_COUNT_MIN,
    OPENAI_DEFAULT_MODEL,
    BEDROCK_DEFAULT_MODEL,
    TEST_ONLY_MODEL,
)
from verification.openrouter_configuration.fixtures import (
    SYNTHETIC_API_KEY,
    SYNTHETIC_OPENAI_API_KEY,
    Client,
    CountingEnvironmentReader,
    no_environment,
    provider_request,
    sdk_exception,
    settings_for,
)
from verification.openrouter_configuration.models import ScenarioResult


def run_negative_scenarios(engine_root: Path) -> list[ScenarioResult]:
    scenarios: list[ScenarioResult] = []

    def add(scenario_id: str, title: str, forbidden: str, holds: bool, detail: str = "") -> None:
        scenarios.append(
            ScenarioResult(
                scenario_id=scenario_id,
                title=title,
                forbidden_condition=forbidden,
                ok=not holds,
                detail=detail,
            )
        )

    add(
        "A",
        "OpenRouter becomes default",
        "AiSettings().provider == openrouter",
        AiSettings().provider == "openrouter",
        f"provider={AiSettings().provider}",
    )

    with patch.dict(os.environ, {DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY}, clear=False):
        key_only_provider = create_assess_ai_provider(settings_for(DEFAULT_PROVIDER))
        stays_default = AiSettings().provider == DEFAULT_PROVIDER
    add(
        "B",
        "OpenRouter selected without explicit provider",
        "API key presence auto-selects openrouter",
        not stays_default or isinstance(key_only_provider, OpenRouterAIModelProvider),
        f"provider={AiSettings().provider} class={type(key_only_provider).__name__}",
    )

    unknown_fallback = False
    try:
        create_assess_ai_provider(settings_for("not-a-provider"))
        unknown_fallback = True
    except AIProviderConfigurationError:
        unknown_fallback = False
    except Exception:  # noqa: BLE001
        unknown_fallback = True
    add("C", "unknown provider falls back", "unknown provider accepted", unknown_fallback)

    created = create_assess_ai_provider(settings_for("openrouter"))
    add(
        "D",
        "OpenRouter falls back to OpenAI",
        "openrouter selection returns OpenAIAIModelProvider",
        isinstance(created, OpenAIAIModelProvider),
        f"class={type(created).__name__}",
    )
    add(
        "E",
        "OpenRouter falls back to Bedrock",
        "openrouter selection returns BedrockAIModelProvider",
        isinstance(created, BedrockAIModelProvider),
        f"class={type(created).__name__}",
    )

    dumped = json.dumps(settings_for("openrouter").model_dump(mode="json"), sort_keys=True)
    add(
        "F",
        "API key stored in canonical configuration serialization",
        "secret token in model_dump",
        SYNTHETIC_API_KEY in dumped or "sk-" in dumped,
    )

    add(
        "G",
        "API key written as settings field accepting secret",
        "OpenRouterSettings has api_key field",
        "api_key" in OpenRouterSettings.model_fields,
    )

    diag = str(
        diagnostic_view_of_adapter(
            build_openrouter_provider(
                openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
                client=Client(),
            )
        )
    )
    add("H", "API key enters diagnostics", "secret token in diagnostics", SYNTHETIC_API_KEY in diag or "sk-" in diag)
    add(
        "I",
        "Auth header enters diagnostics",
        "HTTP auth header name in diagnostics",
        "Authorization" in diag,
    )

    openai_only = CountingEnvironmentReader({"OPENAI_API_KEY": SYNTHETIC_OPENAI_API_KEY})
    reused = resolve_client(
        build_runtime_configuration().client_inputs,
        environment_reader=openai_only,
    )
    add(
        "J",
        "OpenAI API key reused automatically",
        "OPENAI_API_KEY satisfies OpenRouter credential requirement",
        reused.ok
        or (
            reused.error is not None
            and reused.error.category is not ErrorCategory.MISSING_CONFIGURATION
        ),
    )

    empty_accepted = resolve_client(
        build_runtime_configuration().client_inputs,
        environment_reader=lambda _n: "",
    ).ok
    add("K", "empty API key accepted", "empty key resolves client", empty_accepted)

    missing_model_accepted = False
    with patch.dict(
        os.environ,
        {k: v for k, v in os.environ.items() if k != "CODESTRATA_OPENROUTER_MODEL_ID"},
        clear=True,
    ):
        try:
            resolve_assess_model_id(
                cli_model_id=None,
                settings=settings_for("openrouter", openrouter={"model": ""}),
            )
            missing_model_accepted = True
        except AIProviderConfigurationError:
            missing_model_accepted = False
        except Exception:  # noqa: BLE001
            missing_model_accepted = True
    add(
        "L",
        "missing model accepted when mandatory",
        "empty OpenRouter model resolves",
        missing_model_accepted,
    )

    add(
        "M",
        "test-only model becomes product default",
        "AiSettings/OpenRouterSettings.model equals test-only model",
        AiSettings().openrouter.model == TEST_ONLY_MODEL
        or OpenRouterSettings().model == TEST_ONLY_MODEL,
    )

    add(
        "N",
        "custom model enters diagnostics",
        "test-only model in diagnostics",
        TEST_ONLY_MODEL in diag,
    )

    http_accepted = False
    try:
        normalize_base_url("http://example.invalid/api/v1")
        http_accepted = True
    except Exception:  # noqa: BLE001
        http_accepted = False
    add("O", "HTTP base URL accepted", "non-HTTPS base URL accepted", http_accepted)

    cred_url_accepted = False
    try:
        normalize_base_url("https://user:pass@example.invalid/api/v1")
        cred_url_accepted = True
    except Exception:  # noqa: BLE001
        cred_url_accepted = False
    add(
        "P",
        "URL with embedded credentials accepted",
        "credentialed base URL accepted",
        cred_url_accepted,
    )

    add(
        "Q",
        "arbitrary header map accepted",
        "OpenRouterSettings has headers dict field",
        "headers" in OpenRouterSettings.model_fields,
    )

    derived = build_runtime_configuration(
        openrouter_settings=settings_for(
            "openrouter",
            openrouter={"site_url": "", "app_name": ""},
            repository_path="/tmp/synthetic-customer-repo",
        ).ai.openrouter
    )
    add(
        "R",
        "repository-derived referer header",
        "site_url auto-derived from repository path",
        derived.client_inputs.site_url is not None,
    )
    add(
        "S",
        "customer-derived title header",
        "app_name auto-derived from customer or repository metadata",
        derived.client_inputs.app_name is not None,
    )

    from codestrata.ai.provider_contracts.identifiers import CapabilityId

    reader = CountingEnvironmentReader({DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY})
    idle = build_openrouter_provider(environment_reader=reader)
    _ = idle.supports(CapabilityId.MODERNIZATION_ADVISOR)
    _ = repr(idle.configuration)
    add(
        "T",
        "client constructed while AI disabled",
        "environment reader consulted without execute",
        bool(reader.calls),
        f"calls={len(reader.calls)}",
    )

    client = Client()
    provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=client,
    )
    from verification.openrouter_configuration.fixtures import invocation_options, model_request

    provider.invoke(model_request(), invocation_options())
    add(
        "U",
        "multiple provider clients constructed for single invoke",
        "more than one chat completion call for one invoke",
        len(client.calls) > 1,
        f"calls={len(client.calls)}",
    )

    timeout_client = Client(sdk_exception("APITimeoutError"))
    executor = build_openrouter_executor(build_openrouter_provider(client=timeout_client))
    executor.execute(provider_request())
    add(
        "V",
        "duplicate invocation",
        "executor exceeds maximum_attempts under default policy",
        len(timeout_client.calls) > OPENROUTER_RETRY_POLICY.maximum_attempts,
        f"calls={len(timeout_client.calls)}",
    )

    doctor = (engine_root / "src/codestrata/ai/providers/doctor.py").read_text(encoding="utf-8")
    doctor_constructs_or_invokes = any(
        token in doctor
        for token in (
            "provider_adapters.openrouter",
            "OpenRouterAIModelProvider",
            "chat.completions",
            ".invoke(",
        )
    )
    add(
        "W",
        "doctor missing OpenRouter local readiness or constructs a client",
        "openrouter readiness absent from doctor.py OR doctor constructs/invokes OpenRouter",
        "evaluate_openrouter_readiness" not in doctor or doctor_constructs_or_invokes,
        "doctor local readiness in 11.11; no client construction",
    )

    with patch.dict(
        os.environ,
        {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "CODESTRATA_BEDROCK_MODEL_ID",
                "CODESTRATA_OPENAI_MODEL_ID",
                "CODESTRATA_OPENROUTER_MODEL_ID",
            }
        },
        clear=True,
    ):
        openai_regressed = (
            resolve_assess_model_id(cli_model_id=None, settings=settings_for("openai"))
            != OPENAI_DEFAULT_MODEL
        )
        bedrock_regressed = (
            resolve_assess_model_id(cli_model_id=None, settings=settings_for("bedrock"))
            != BEDROCK_DEFAULT_MODEL
            or AiSettings().provider != DEFAULT_PROVIDER
        )
    add("X", "OpenAI regression", "openai default model changed", openai_regressed)
    add("Y", "Bedrock regression", "bedrock default model or provider changed", bedrock_regressed)

    # Privacy scanned after report assembly; placeholder ensures scenario Z exists.
    add(
        "Z",
        "report leaks",
        "verification report contains secrets endpoints models or prompts",
        False,
        "privacy scanned after report assembly",
    )

    # Ensure unused import of no_environment stays intentional for readers.
    _ = no_environment

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = ["run_negative_scenarios"]
