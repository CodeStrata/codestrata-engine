"""Provider registry and selection checks (Decision B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.registry import AIProviderRegistry, ProviderRegistration
from codestrata.ai.providers.factory import create_assess_ai_provider, supported_assess_ai_providers
from codestrata.config.settings import AiSettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.ai_provider_cross_provider.contract import (
    CANONICAL_PROVIDER_IDS,
    DEFAULT_PROVIDER,
    EXPECTED_REGISTERED_PROVIDERS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    REGISTRY_DECISION_RATIONALE,
)
from verification.ai_provider_cross_provider.fixtures import (
    default_settings,
    is_same_class,
    settings_for,
)
from verification.ai_provider_cross_provider.models import CheckResult


def check_assess_registry_lists_canonical_providers() -> CheckResult:
    reset_assess_ai_provider_registry_for_tests()
    try:
        names = get_assess_ai_provider_registry().list_providers()
        ok = names == EXPECTED_REGISTERED_PROVIDERS
    finally:
        reset_assess_ai_provider_registry_for_tests()
    return CheckResult(
        name="assess_registry_lists_bedrock_openai_and_openrouter_sorted",
        category="provider_registry",
        ok=ok,
        detail=f"registered={list(names)}",
    )


def check_contracts_registry_is_explicit_and_unwired() -> CheckResult:
    registry = AIProviderRegistry()
    empty = registry.list_provider_ids()
    return CheckResult(
        name="contracts_ai_provider_registry_starts_empty_and_is_explicit",
        category="provider_registry",
        ok=empty == (),
        detail="no process-wide default; assess does not bootstrap it",
    )


def check_contracts_registry_rejects_duplicates_and_unknown() -> CheckResult:
    registry = AIProviderRegistry()

    class _Fake:
        @property
        def provider_id(self) -> ProviderId:
            return ProviderId.OPENAI

        def supports(self, capability: CapabilityId) -> bool:
            return capability is CapabilityId.MODERNIZATION_ADVISOR

        def execute(self, request: object) -> object:  # pragma: no cover
            raise AssertionError("unused")

    registration = ProviderRegistration(
        provider_id=ProviderId.OPENAI,
        capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
        factory=_Fake,
    )
    registry.register(registration)
    duplicate_rejected = False
    try:
        registry.register(registration)
    except ProviderContractValidationError:
        duplicate_rejected = True
    unknown_rejected = False
    try:
        registry.resolve(ProviderId.BEDROCK)
    except ProviderContractValidationError:
        unknown_rejected = True
    return CheckResult(
        name="contracts_registry_rejects_duplicate_and_unknown_provider_ids",
        category="provider_registry",
        ok=duplicate_rejected and unknown_rejected,
        detail=f"duplicate_rejected={duplicate_rejected} unknown_rejected={unknown_rejected}",
    )


def check_registry_decision_is_explicit() -> CheckResult:
    return CheckResult(
        name="registry_decision_is_explicitly_b_compatibility_retained",
        category="provider_registry",
        ok=REGISTRY_DECISION == "B" and REGISTRY_DECISION_LABEL == "compatibility_registry_retained",
        detail=REGISTRY_DECISION_RATIONALE,
        evidence={
            "registry_decision": REGISTRY_DECISION,
            "registry_decision_label": REGISTRY_DECISION_LABEL,
        },
    )


def check_default_selection_is_bedrock() -> CheckResult:
    from codestrata.ai.providers import bedrock as bedrock_module

    settings = default_settings()
    provider = create_assess_ai_provider(settings)
    ok = settings.ai.provider == DEFAULT_PROVIDER and is_same_class(
        provider, bedrock_module.BedrockAIModelProvider
    )
    return CheckResult(
        name="default_provider_selection_resolves_bedrock",
        category="provider_selection",
        ok=ok,
        detail=f"settings_provider={settings.ai.provider} resolved={type(provider).__name__}",
    )


def check_explicit_openai_selection() -> CheckResult:
    from codestrata.ai.providers import openai_provider as openai_module

    provider = create_assess_ai_provider(settings_for("openai"))
    ok = is_same_class(provider, openai_module.OpenAIAIModelProvider)
    return CheckResult(
        name="explicit_openai_selection_resolves_openai_wrapper",
        category="provider_selection",
        ok=ok,
        detail=f"resolved={type(provider).__name__}",
    )


def check_explicit_bedrock_selection() -> CheckResult:
    from codestrata.ai.providers import bedrock as bedrock_module

    provider = create_assess_ai_provider(settings_for("bedrock"))
    ok = is_same_class(provider, bedrock_module.BedrockAIModelProvider)
    return CheckResult(
        name="explicit_bedrock_selection_resolves_bedrock_wrapper",
        category="provider_selection",
        ok=ok,
        detail=f"resolved={type(provider).__name__}",
    )


def check_unknown_provider_rejects() -> CheckResult:
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError

    raised = False
    try:
        create_assess_ai_provider(settings_for("synthetic-unknown-provider"))
    except AIProviderConfigurationError:
        raised = True
    except Exception:  # noqa: BLE001
        raised = False
    return CheckResult(
        name="unknown_provider_raises_configuration_error",
        category="provider_selection",
        ok=raised,
        detail="unknown names reject without fallback",
    )


def check_analytics_family_token_is_not_a_provider_id() -> CheckResult:
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError

    raised = False
    try:
        create_assess_ai_provider(settings_for("aws_bedrock"))
    except AIProviderConfigurationError:
        raised = True
    except Exception:  # noqa: BLE001
        raised = False
    return CheckResult(
        name="analytics_family_token_aws_bedrock_is_rejected_as_provider_id",
        category="provider_selection",
        ok=raised,
        detail="aws_bedrock remains analytics-only terminology",
    )


def check_ai_settings_default_provider_field() -> CheckResult:
    ok = AiSettings().provider == DEFAULT_PROVIDER
    return CheckResult(
        name="ai_settings_default_provider_remains_bedrock",
        category="provider_selection",
        ok=ok,
        detail=f"AiSettings().provider={AiSettings().provider!r}",
    )


def check_supported_providers_match_canonical_set() -> CheckResult:
    supported = set(supported_assess_ai_providers())
    ok = supported == set(CANONICAL_PROVIDER_IDS)
    return CheckResult(
        name="supported_assess_ai_providers_match_canonical_ids",
        category="provider_selection",
        ok=ok,
        detail=f"supported={sorted(supported)}",
    )


def check_no_client_construction_when_factory_mocked(engine_root: Path) -> CheckResult:
    """AI-disabled / selection path: factory may resolve wrappers without SDK clients."""

    del engine_root  # inventory uses engine_root elsewhere; selection is in-memory
    with patch(
        "codestrata.ai.provider_adapters.bedrock.client.resolve_client"
    ) as bedrock_resolve, patch(
        "codestrata.ai.provider_adapters.openai.client.resolve_client"
    ) as openai_resolve:
        create_assess_ai_provider(settings_for("bedrock"))
        create_assess_ai_provider(settings_for("openai"))
        ok = bedrock_resolve.call_count == 0 and openai_resolve.call_count == 0
    return CheckResult(
        name="provider_factory_resolution_does_not_construct_sdk_clients",
        category="provider_selection",
        ok=ok,
        detail="create_assess_ai_provider builds wrappers lazily without resolve_client",
    )


def run_provider_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_assess_registry_lists_canonical_providers(),
        check_contracts_registry_is_explicit_and_unwired(),
        check_contracts_registry_rejects_duplicates_and_unknown(),
        check_registry_decision_is_explicit(),
    ]
    matrix = {
        "registry_decision": REGISTRY_DECISION,
        "registry_decision_label": REGISTRY_DECISION_LABEL,
        "assess_authoritative": True,
        "contracts_registry_wired_to_assess": False,
    }
    return checks, matrix


def run_provider_selection_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_default_selection_is_bedrock(),
        check_explicit_openai_selection(),
        check_explicit_bedrock_selection(),
        check_unknown_provider_rejects(),
        check_analytics_family_token_is_not_a_provider_id(),
        check_ai_settings_default_provider_field(),
        check_supported_providers_match_canonical_set(),
        check_no_client_construction_when_factory_mocked(engine_root),
    ]
    matrix = {
        "default_provider": DEFAULT_PROVIDER,
        "registered_providers": list(EXPECTED_REGISTERED_PROVIDERS),
        "fallback_policy": "none",
    }
    return checks, matrix


__all__ = [
    "run_provider_registry_checks",
    "run_provider_selection_checks",
]
