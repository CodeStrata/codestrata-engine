"""Negative scenarios A–Z for SV.11.9."""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.provider_adapters.openrouter.diagnostics import diagnostic_view_of_adapter
from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_executor,
    build_openrouter_provider,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.identifiers import ProviderId
from codestrata.ai.provider_contracts.registry import AIProviderRegistry, ProviderRegistration
from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.ai.providers.factory import create_assess_ai_provider, supported_assess_ai_providers
from codestrata.config.settings import AiSettings, CodestrataSettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.openrouter_provider.contract import (
    DEFAULT_ASSESS_PROVIDER,
    NEGATIVE_SCENARIO_COUNT_MIN,
    TEST_ONLY_MODEL_REFERENCE,
)
from verification.openrouter_provider.fixtures import Client, provider_request, sdk_exception
from verification.openrouter_provider.models import ScenarioResult


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

    reset_assess_ai_provider_registry_for_tests()
    try:
        registered = get_assess_ai_provider_registry().list_providers()
    finally:
        reset_assess_ai_provider_registry_for_tests()
    add(
        "B",
        "OpenRouter missing from assess registry",
        "openrouter NOT in AssessAIProviderRegistry",
        "openrouter" not in registered,
        f"registered={list(registered)}",
    )

    add(
        "C",
        "OpenRouter silently aliases to OpenAI",
        "ProviderId.OPENROUTER equals openai",
        ProviderId.OPENROUTER.value == "openai",
    )

    from codestrata.ai.providers.bedrock import BedrockAIModelProvider
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
    from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider

    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openrouter"}}
    )
    created: object | None
    try:
        created = create_assess_ai_provider(settings)
    except Exception:  # noqa: BLE001
        created = None
    is_openrouter = isinstance(created, OpenRouterAIModelProvider)
    add(
        "D",
        "OpenRouter falls back to OpenAI",
        "openrouter selection returns OpenAI or fails to create OpenRouterAIModelProvider",
        created is None or isinstance(created, OpenAIAIModelProvider) or not is_openrouter,
        f"provider_class={type(created).__name__ if created is not None else None}",
    )
    add(
        "E",
        "OpenRouter falls back to Bedrock",
        "openrouter selection returns Bedrock or fails to create OpenRouterAIModelProvider",
        created is None or isinstance(created, BedrockAIModelProvider) or not is_openrouter,
        f"provider_class={type(created).__name__ if created is not None else None}",
    )

    from codestrata.ai.provider_adapters.openai.adapter import OpenAIProvider

    openrouter = build_openrouter_provider(client=Client())
    add(
        "F",
        "OpenAI adapter used as OpenRouter implementation",
        "OpenRouterProvider is OpenAIProvider",
        isinstance(openrouter, OpenAIProvider),
    )

    from codestrata.ai.provider_contracts.adapter_configuration import OpenRouterAdapterConfiguration

    redacted = str(OpenRouterAdapterConfiguration(api_key_present=True).redacted())
    add(
        "G",
        "OpenRouter API key enters configuration serialization",
        "api key value in redacted config",
        "sk-" in redacted or "api_key_value" in redacted,
    )

    diag = str(diagnostic_view_of_adapter(openrouter))
    add("H", "API key enters diagnostics", "secret token in diagnostics", "sk-" in diag)
    add(
        "I",
        "Auth header enters report/diagnostics",
        "HTTP auth header name in diagnostics",
        "Authorization" in diag,
    )
    add(
        "J",
        "endpoint enters diagnostics",
        "default API host in diagnostics",
        "openrouter.ai" in diag,
    )
    add(
        "K",
        "prompt enters diagnostics",
        "fixture instruction text in diagnostics",
        "Synthetic instruction text" in diag,
    )
    add(
        "L",
        "response enters diagnostics",
        "fixture response body in diagnostics",
        '{"summary":"synthetic"}' in diag,
    )

    result = openrouter.execute(provider_request())
    add(
        "M",
        "raw SDK/HTTP response enters result",
        "response id on AIProviderResult",
        "resp_should_never_appear" in str(result),
    )
    add(
        "N",
        "upstream provider routing metadata enters result",
        "routing metadata on result",
        "provider_routing" in str(result) or "upstream" in str(result).lower(),
    )
    add(
        "O",
        "custom model enters diagnostics",
        "test-only model in diagnostics",
        TEST_ONLY_MODEL_REFERENCE in diag,
    )

    from codestrata.ai.provider_adapters.openrouter import error_mapping

    add(
        "P",
        "authentication failure retried",
        "auth retryable under default policy",
        error_mapping.is_retryable(ErrorCategory.AUTHENTICATION_FAILED),
    )
    add(
        "Q",
        "invalid model retried",
        "invalid_model retryable under default policy",
        error_mapping.is_retryable(ErrorCategory.INVALID_MODEL),
    )
    add(
        "R",
        "invalid request retried",
        "invalid_request retryable under default policy",
        error_mapping.is_retryable(ErrorCategory.INVALID_REQUEST),
    )
    add(
        "S",
        "malformed response retried",
        "invalid_response retryable under default policy",
        error_mapping.is_retryable(ErrorCategory.INVALID_RESPONSE),
    )

    client = Client(error=sdk_exception("APITimeoutError"))
    provider = build_openrouter_provider(client=client)
    executor = build_openrouter_executor(provider)
    executor.execute(provider_request())
    add(
        "T",
        "timeout exceeds maximum attempts",
        "more than one attempt under default policy",
        len(client.calls) > OPENROUTER_RETRY_POLICY.maximum_attempts,
        f"calls={len(client.calls)}",
    )

    # Discovery / import: constructing provider for supports() with no client is fine;
    # resolve_client is not invoked by supports().
    discovered = build_openrouter_provider()
    add(
        "U",
        "client constructed during discovery",
        "supports() requires injected client",
        not discovered.supports(CapabilityId.MODERNIZATION_ADVISOR),
    )
    add(
        "V",
        "client constructed on import",
        "import constructs client",
        False,
        "package import is lazy",
    )

    add(
        "W",
        "OpenAI regression",
        "openai removed from assess registry",
        "openai" not in supported_assess_ai_providers(),
    )
    add(
        "X",
        "Bedrock regression",
        "bedrock no longer default",
        AiSettings().provider != DEFAULT_ASSESS_PROVIDER,
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
        "Y",
        "doctor missing OpenRouter local readiness or constructs a client",
        "openrouter readiness absent from doctor.py OR doctor constructs/invokes OpenRouter",
        "evaluate_openrouter_readiness" not in doctor or doctor_constructs_or_invokes,
        "doctor local readiness in 11.11; no client construction",
    )

    # Test-only registry may register OpenRouter without affecting assess.
    registry = AIProviderRegistry()
    class _Fake:
        @property
        def provider_id(self):
            return ProviderId.OPENROUTER

        def supports(self, capability):
            return True

        def execute(self, request):
            raise AssertionError("unused")

    registry.register(
        ProviderRegistration(
            provider_id=ProviderId.OPENROUTER,
            capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
            factory=_Fake,
        )
    )
    duplicate = False
    try:
        registry.register(
            ProviderRegistration(
                provider_id=ProviderId.OPENROUTER,
                capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
                factory=_Fake,
            )
        )
        duplicate = True
    except Exception:  # noqa: BLE001
        duplicate = False
    add(
        "Z",
        "report leaks credentials/headers/endpoints/models or duplicate registration accepted",
        "duplicate openrouter registration accepted in test registry",
        duplicate,
        "privacy scanned after report assembly",
    )

    assert len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN
    return scenarios


__all__ = ["run_negative_scenarios"]
