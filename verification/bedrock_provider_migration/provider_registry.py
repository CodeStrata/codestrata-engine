"""Provider registry and selection: same keys, same default, same precedence.

Slice 11.7 deliberately does **not** consolidate the two registries. The
assess path still resolves providers through ``AssessAIProviderRegistry``
(the legacy ``AIModelProvider`` seam ``AiEnrichmentService`` consumes), while
the contracts' own ``AIProviderRegistry`` remains available but not
authoritative. That deferral is recorded as the
``common_registry_consolidation_deferred`` limitation and is scheduled for
Slice 11.8.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.factory import (
    SUPPORTED_ASSESS_AI_PROVIDERS,
    create_assess_ai_provider,
    resolve_assess_model_id,
    supported_assess_ai_providers,
)
from codestrata.config.settings import CodestrataSettings
from verification.bedrock_provider_migration.contract import (
    BEDROCK_DEFAULT_MODEL_ID,
    BEDROCK_PROVIDER_NAME,
    DEFAULT_PROVIDER,
    EXPECTED_REGISTERED_PROVIDERS,
)
from verification.bedrock_provider_migration.models import CheckResult


def settings_for(provider: str | None = None) -> CodestrataSettings:
    payload: dict[str, Any] = {"repository": {"path": "."}, "ai": {}}
    if provider is not None:
        payload["ai"]["provider"] = provider
    return CodestrataSettings.model_validate(payload)


def check_the_registry_keys_are_unchanged() -> CheckResult:
    actual = tuple(sorted(supported_assess_ai_providers()))
    return CheckResult(
        name="the_assess_registry_still_exposes_exactly_bedrock_and_openai",
        category="provider_registry",
        ok=actual == EXPECTED_REGISTERED_PROVIDERS
        and tuple(sorted(SUPPORTED_ASSESS_AI_PROVIDERS)) == EXPECTED_REGISTERED_PROVIDERS,
        detail=f"registered_providers={list(actual)}",
    )


def check_the_default_selection_is_still_bedrock() -> CheckResult:
    provider = create_assess_ai_provider(settings_for())
    return CheckResult(
        name="an_unconfigured_run_still_resolves_the_bedrock_provider",
        category="provider_registry",
        ok=type(provider).__name__ == "BedrockAIModelProvider",
        detail=f"resolved={type(provider).__name__} default_provider={DEFAULT_PROVIDER}",
    )


def check_resolution_constructs_no_client() -> CheckResult:
    """Registry resolution must stay AWS-free now that construction is lazy."""

    from codestrata.ai.provider_adapters.bedrock import client as client_module

    calls: list[dict[str, Any]] = []

    class _Stub:
        AwsAuthenticationError = client_module.AwsAuthenticationError

        @staticmethod
        def create_bedrock_runtime_client(**kwargs: Any) -> Any:
            calls.append(kwargs)
            return object()

    real = client_module.aws_config
    client_module.aws_config = _Stub  # type: ignore[assignment]
    try:
        create_assess_ai_provider(settings_for())
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="resolving_the_bedrock_provider_from_the_registry_constructs_no_client",
        category="provider_registry",
        ok=not calls,
        detail=f"client_factory_calls={len(calls)}",
    )


def check_an_explicit_selection_is_honored() -> CheckResult:
    provider = create_assess_ai_provider(settings_for("openai"))
    return CheckResult(
        name="an_explicitly_configured_provider_is_still_honored",
        category="provider_registry",
        ok=type(provider).__name__ == "OpenAIAIModelProvider",
        detail=f"resolved={type(provider).__name__}",
    )


def check_an_unknown_provider_is_still_rejected() -> CheckResult:
    from codestrata.ai.providers.exceptions import AIProviderConfigurationError

    try:
        create_assess_ai_provider(settings_for("synthetic-unknown-provider"))
    except AIProviderConfigurationError:
        raised = True
    except Exception:  # noqa: BLE001 - the raised type is the subject
        raised = False
    else:
        raised = False
    return CheckResult(
        name="an_unknown_provider_name_is_still_rejected_with_a_configuration_error",
        category="provider_registry",
        ok=raised,
        detail=f"raised_configuration_error={raised}",
    )


def check_both_providers_resolve_from_one_registry() -> CheckResult:
    """Both migrated providers still present the same legacy seam."""

    offenders = sorted(
        name
        for name in EXPECTED_REGISTERED_PROVIDERS
        if not isinstance(create_assess_ai_provider(settings_for(name)), AIModelProvider)
    )
    return CheckResult(
        name="both_migrated_providers_still_resolve_through_the_one_legacy_registry",
        category="provider_registry",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_the_model_id_precedence_is_unchanged() -> CheckResult:
    cli_wins = resolve_assess_model_id(cli_model_id="  from-cli  ", settings=settings_for())
    default_used = resolve_assess_model_id(cli_model_id=None, settings=settings_for())
    return CheckResult(
        name="the_assess_model_id_precedence_and_bedrock_default_are_unchanged",
        category="provider_registry",
        ok=cli_wins == "from-cli" and default_used == BEDROCK_DEFAULT_MODEL_ID,
        detail=f"default_model_id={default_used}",
    )


def check_the_contract_registry_is_not_authoritative() -> CheckResult:
    """The consolidation deferral: the assess factory does not use the contracts."""

    from codestrata.ai.providers import factory as factory_module

    tree = ast.parse(inspect.getsource(factory_module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    uses_contract_registry = any(
        name.startswith("codestrata.ai.provider_contracts") for name in names
    )
    return CheckResult(
        name="the_common_provider_registry_is_available_but_not_yet_authoritative",
        category="provider_registry",
        ok=not uses_contract_registry,
        detail="consolidation deferred (Slice 11.8 Decision B)",
    )


def check_the_assess_extension_signature_is_unchanged() -> CheckResult:
    from codestrata.extensions import assess_ai

    source = inspect.getsource(assess_ai)
    return CheckResult(
        name="the_assess_extension_still_constructs_the_provider_with_settings_only",
        category="provider_registry",
        ok="BedrockAIModelProvider(settings=settings)" in source,
        detail="no provider construction API change was required",
    )


def run_provider_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_registry_keys_are_unchanged(),
        check_the_default_selection_is_still_bedrock(),
        check_resolution_constructs_no_client(),
        check_an_explicit_selection_is_honored(),
        check_an_unknown_provider_is_still_rejected(),
        check_both_providers_resolve_from_one_registry(),
        check_the_model_id_precedence_is_unchanged(),
        check_the_contract_registry_is_not_authoritative(),
        check_the_assess_extension_signature_is_unchanged(),
    ]
    matrix: dict[str, Any] = {
        "authoritative_registry": "AssessAIProviderRegistry",
        "common_registry_consolidation_decision": "B_compatibility_registry_retained",
        "common_registry_consolidation_deferred": True,
        "default_provider": DEFAULT_PROVIDER,
        "migrated_providers": list(EXPECTED_REGISTERED_PROVIDERS),
        "provider_name": BEDROCK_PROVIDER_NAME,
        "registered_providers": list(EXPECTED_REGISTERED_PROVIDERS),
    }
    return checks, matrix


__all__ = [
    "check_an_explicit_selection_is_honored",
    "check_an_unknown_provider_is_still_rejected",
    "check_both_providers_resolve_from_one_registry",
    "check_resolution_constructs_no_client",
    "check_the_assess_extension_signature_is_unchanged",
    "check_the_contract_registry_is_not_authoritative",
    "check_the_default_selection_is_still_bedrock",
    "check_the_model_id_precedence_is_unchanged",
    "check_the_registry_keys_are_unchanged",
    "run_provider_registry_checks",
    "settings_for",
]
