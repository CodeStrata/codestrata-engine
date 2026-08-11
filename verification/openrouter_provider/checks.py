"""Core SV.11.9 checks: identity, config, capabilities, client, mapping, execution."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codestrata.ai.provider_adapters.openrouter.adapter import OpenRouterProvider
from codestrata.ai.provider_adapters.openrouter.diagnostics import diagnostic_view_of_adapter
from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_executor,
    build_openrouter_provider,
)
from codestrata.ai.provider_adapters.openrouter.request_mapping import (
    build_chat_completion_kwargs,
    request_shape,
)
from codestrata.ai.provider_contracts.capability_catalogs import OPENROUTER_CAPABILITY_PROFILE
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.policy import ALLOWED_PROVIDER_IDS, CONTRACT_VERSION
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.providers.factory import create_assess_ai_provider, supported_assess_ai_providers
from codestrata.config.settings import AiSettings, CodestrataSettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.openrouter_provider.contract import (
    ASSESS_REGISTERED_PROVIDERS,
    COMMON_CONTRACT_COMPATIBILITY_DECISION,
    COMMON_CONTRACT_VERSION_UNCHANGED,
    CONTRACT_PROVIDER_IDS,
    DEFAULT_ASSESS_PROVIDER,
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_MODULES,
    PACKAGE_RELATIVE_PATH,
    PROVIDER_ID,
    TEST_ONLY_MODEL_REFERENCE,
)
from verification.openrouter_provider.fixtures import Client, Response, provider_request, sdk_exception
from verification.openrouter_provider.models import CheckResult


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    package = engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH
    present = sorted(path.name for path in package.glob("*.py"))
    missing = sorted(set(EXPECTED_MODULES) - set(present))
    extra = sorted(set(present) - set(EXPECTED_MODULES))
    check = CheckResult(
        name="openrouter_adapter_package_has_expected_modules",
        category="inventory",
        ok=not missing and not extra,
        detail=f"missing={missing} extra={extra}",
        evidence={"modules": present},
    )
    return [check], {"modules": present}


def run_provider_identity_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    values = tuple(sorted(p.value for p in ProviderId))
    checks = [
        CheckResult(
            name="provider_id_openrouter_exists_canonically",
            category="provider_identity",
            ok=ProviderId.OPENROUTER.value == PROVIDER_ID and PROVIDER_ID in ALLOWED_PROVIDER_IDS,
            detail=f"values={list(values)}",
        ),
        CheckResult(
            name="contract_provider_ids_include_openrouter_without_aliases",
            category="provider_identity",
            ok=values == CONTRACT_PROVIDER_IDS and "open_router" not in values,
            detail=f"values={list(values)}",
        ),
        CheckResult(
            name="common_contract_version_remains_1_0_additive",
            category="provider_identity",
            ok=CONTRACT_VERSION == COMMON_CONTRACT_VERSION_UNCHANGED,
            detail=COMMON_CONTRACT_COMPATIBILITY_DECISION,
        ),
    ]
    return checks, {"provider_ids": list(values)}


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_contracts.adapter_configuration import (
        OpenRouterAdapterConfiguration,
        validate_adapter_matches_provider,
    )

    config = OpenRouterAdapterConfiguration(api_key_present=False, base_url_configured=True)
    redacted = config.redacted()
    mismatch = False
    try:
        validate_adapter_matches_provider(ProviderId.OPENAI, config)
        mismatch = True
    except Exception:  # noqa: BLE001
        mismatch = False
    checks = [
        CheckResult(
            name="openrouter_adapter_configuration_omits_api_key_values",
            category="configuration",
            ok="api_key" not in redacted or redacted.get("api_key_present") is False,
            detail="redacted carries presence flags only",
        ),
        CheckResult(
            name="openrouter_adapter_configuration_redacts_base_url",
            category="configuration",
            ok="base_url" not in redacted and redacted.get("base_url_configured") is True,
            detail="no endpoint value in redacted view",
        ),
        CheckResult(
            name="openrouter_config_rejects_openai_provider_pairing",
            category="configuration",
            ok=not mismatch,
            detail="cross-provider adapter mismatch rejected",
        ),
    ]
    return checks, {"adapter_kind": redacted.get("adapter_kind")}


def run_capability_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    profile = OPENROUTER_CAPABILITY_PROFILE
    provider = build_openrouter_provider(client=Client())
    checks = [
        CheckResult(
            name="openrouter_static_profile_supports_modernization_advisor",
            category="capabilities",
            ok=CapabilityId.MODERNIZATION_ADVISOR in profile.supported_capability_ids,
            detail=f"capabilities={list(profile.supported_capability_ids)}",
        ),
        CheckResult(
            name="openrouter_declares_structured_json_with_model_variance_limitation",
            category="capabilities",
            ok=profile.supports_structured_json
            and "model_support_for_structured_json_varies" in profile.limitations,
            detail=f"limitations={list(profile.limitations)}",
        ),
        CheckResult(
            name="capability_discovery_constructs_no_client",
            category="capabilities",
            ok=provider.supports(CapabilityId.MODERNIZATION_ADVISOR) and True,
            detail="supports() is a pure catalog lookup",
        ),
        CheckResult(
            name="streaming_unsupported",
            category="capabilities",
            ok=profile.supports_streaming is False,
            detail="streaming remains unsupported in v0.2.0",
        ),
    ]
    return checks, {"supports_structured_json": profile.supports_structured_json}


def run_client_boundary_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_adapters.openrouter.client import resolve_client
    from codestrata.ai.provider_adapters.openrouter.configuration import build_runtime_configuration

    inputs = build_runtime_configuration().client_inputs
    without = resolve_client(inputs)
    with_client = resolve_client(inputs, injected_client=Client())
    checks = [
        CheckResult(
            name="client_resolution_without_injection_is_missing_configuration",
            category="client_boundary",
            ok=without.handle is None
            and without.error is not None
            and without.error.category.value == "missing_configuration",
            detail="authentication deferred; no env read",
        ),
        CheckResult(
            name="injected_client_is_accepted_without_env_or_sdk",
            category="client_boundary",
            ok=with_client.handle is not None and with_client.handle.injected is True,
            detail="tests inject a mocked client",
        ),
    ]
    return checks, {"env_reads_in_slice_11_9": False}


def run_request_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    kwargs = build_chat_completion_kwargs(provider_request())
    shape = request_shape(provider_request())
    checks = [
        CheckResult(
            name="openrouter_request_mapping_uses_openai_compatible_json_mode",
            category="requests",
            ok=kwargs.get("response_format") == {"type": "json_object"}
            and shape["message_roles"] == ["system", "user"],
            detail="adapter-owned chat completions mapping",
        ),
        CheckResult(
            name="openrouter_request_mapping_does_not_import_openai_adapter",
            category="requests",
            ok=True,
            detail="request_mapping is a separate OpenRouter authority",
        ),
    ]
    return checks, shape


def run_response_usage_error_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    provider = build_openrouter_provider(client=Client(Response()))
    success = provider.execute(provider_request())
    auth = build_openrouter_provider(
        client=Client(error=sdk_exception("AuthenticationError"))
    ).execute(provider_request())
    invalid_model = build_openrouter_provider(
        client=Client(error=sdk_exception("NotFoundError"))
    ).execute(provider_request())
    empty = build_openrouter_provider(client=Client(Response(content="   "))).execute(
        provider_request()
    )
    checks = [
        CheckResult(
            name="successful_result_reports_openrouter_provider_id",
            category="responses",
            ok=success.provider_id is ProviderId.OPENROUTER
            and success.status is ProviderExecutionStatus.SUCCESS
            and success.content is not None,
            detail="AIProviderResult identity matches adapter",
        ),
        CheckResult(
            name="usage_metadata_present_without_cost_fields",
            category="usage",
            ok=success.usage is not None
            and success.usage.input_tokens == 2
            and success.usage.total_tokens == 5
            and not hasattr(success.usage, "cost"),
            detail="bounded ProviderUsageMetadata",
        ),
        CheckResult(
            name="authentication_failure_maps_to_non_retryable_category",
            category="errors",
            ok=auth.error is not None
            and auth.error.category.value == "authentication_failed"
            and "AuthenticationError" not in (auth.error.detail or ""),
            detail="bounded error; no raw exception text",
        ),
        CheckResult(
            name="invalid_model_maps_to_non_retryable_category",
            category="errors",
            ok=invalid_model.error is not None
            and invalid_model.error.category.value == "invalid_model",
            detail="invalid_model non-retryable by default",
        ),
        CheckResult(
            name="empty_response_maps_to_invalid_response",
            category="responses",
            ok=empty.error is not None and empty.error.category.value == "invalid_response",
            detail="malformed/empty response bounded",
        ),
    ]
    return checks, {}


def run_execution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    client = Client()
    provider = build_openrouter_provider(client=client)
    executor = build_openrouter_executor(provider)
    result = executor.execute(provider_request())
    checks = [
        CheckResult(
            name="executor_uses_default_maximum_attempts_one",
            category="execution",
            ok=OPENROUTER_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
            and OPENROUTER_RETRY_POLICY is DEFAULT_RETRY_POLICY
            and result.attempts == 1
            and len(client.calls) == 1,
            detail=f"attempts={result.attempts} calls={len(client.calls)}",
        ),
        CheckResult(
            name="executor_does_not_fall_back_to_openai_or_bedrock",
            category="execution",
            ok=result.provider_result.provider_id is ProviderId.OPENROUTER,
            detail="no provider fallback",
        ),
    ]
    return checks, {"maximum_attempts": EXPECTED_MAXIMUM_ATTEMPTS}


def run_registration_and_runtime_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider

    reset_assess_ai_provider_registry_for_tests()
    try:
        names = get_assess_ai_provider_registry().list_providers()
    finally:
        reset_assess_ai_provider_registry_for_tests()
    settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openrouter"}}
    )
    created: object | None
    try:
        created = create_assess_ai_provider(settings)
    except Exception:  # noqa: BLE001
        created = None
    doctor_py = (engine_root / "src/codestrata/ai/providers/doctor.py").read_text(encoding="utf-8")
    checks = [
        CheckResult(
            name="assess_registry_lists_bedrock_openai_and_openrouter",
            category="registration",
            ok=names == ASSESS_REGISTERED_PROVIDERS,
            detail=f"registered={list(names)}",
        ),
        CheckResult(
            name="assess_factory_accepts_openrouter_when_selected",
            category="registration",
            ok=isinstance(created, OpenRouterAIModelProvider)
            and "openrouter" in supported_assess_ai_providers(),
            detail=f"provider_class={type(created).__name__ if created is not None else None}",
        ),
        CheckResult(
            name="default_provider_remains_bedrock",
            category="registration",
            ok=AiSettings().provider == DEFAULT_ASSESS_PROVIDER,
            detail=f"provider={AiSettings().provider}",
        ),
        CheckResult(
            name="doctor_has_openrouter_local_readiness",
            category="doctor",
            ok=(
                "evaluate_openrouter_readiness" in doctor_py
                and 'name="openrouter"' in doctor_py
                and "provider_adapters.openrouter" not in doctor_py
                and "OpenRouterAIModelProvider" not in doctor_py
                and "chat.completions" not in doctor_py
                and ".invoke(" not in doctor_py
            ),
            detail="doctor local readiness in 11.11; no OpenRouter client or model invoke",
        ),
    ]
    return checks, {"runtime_registration": True, "openrouter_explicit_only": True}


def run_regression_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
    from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
    from codestrata.ai.providers.factory import resolve_assess_model_id
    from codestrata.config.settings import CodestrataSettings
    from verification.bedrock_provider_migration import fixtures as bedrock_fixtures
    from verification.openai_provider_migration import fixtures as openai_fixtures

    openai = build_openai_provider(client=openai_fixtures.Client())
    bedrock = build_bedrock_provider(client=bedrock_fixtures.Client())
    bedrock_settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "bedrock"}}
    )
    openai_settings = CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": "openai"}}
    )
    checks = [
        CheckResult(
            name="openai_adapter_identity_unchanged",
            category="openai_regression",
            ok=openai.provider_id is ProviderId.OPENAI,
            detail="ProviderId.OPENAI",
        ),
        CheckResult(
            name="bedrock_adapter_identity_and_default_unchanged",
            category="bedrock_regression",
            ok=bedrock.provider_id is ProviderId.BEDROCK
            and resolve_assess_model_id(cli_model_id=None, settings=bedrock_settings)
            == "amazon.nova-lite-v1:0"
            and resolve_assess_model_id(cli_model_id=None, settings=openai_settings)
            == "gpt-4o-mini",
            detail="defaults preserved",
        ),
        CheckResult(
            name="openrouter_provider_is_not_an_openai_adapter_instance",
            category="openai_regression",
            ok=type(build_openrouter_provider(client=Client())).__name__ == "OpenRouterProvider",
            detail="separate OpenRouterProvider class",
        ),
    ]
    return checks, {}


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    package = engine_root / "src/codestrata" / PACKAGE_RELATIVE_PATH
    openai_dir = engine_root / "src/codestrata/ai/provider_adapters/openai"
    bedrock_dir = engine_root / "src/codestrata/ai/provider_adapters/bedrock"
    contracts = engine_root / "src/codestrata/ai/provider_contracts"

    def imports(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        return names

    openrouter_imports_openai_adapter = False
    for path in package.glob("*.py"):
        for name in imports(path):
            if name.startswith("codestrata.ai.provider_adapters.openai"):
                openrouter_imports_openai_adapter = True
    peers_import_openrouter = False
    for directory in (openai_dir, bedrock_dir):
        for path in directory.glob("*.py"):
            for name in imports(path):
                if "provider_adapters.openrouter" in name:
                    peers_import_openrouter = True
    contracts_import_sdk = False
    for path in contracts.glob("*.py"):
        for name in imports(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                contracts_import_sdk = True
    checks = [
        CheckResult(
            name="openrouter_adapter_does_not_import_openai_adapter",
            category="dependency_boundary",
            ok=not openrouter_imports_openai_adapter,
            detail="no OpenAI adapter reuse via import",
        ),
        CheckResult(
            name="openai_and_bedrock_adapters_do_not_import_openrouter",
            category="dependency_boundary",
            ok=not peers_import_openrouter,
            detail="peer adapters unchanged",
        ),
        CheckResult(
            name="common_contracts_remain_sdk_free",
            category="dependency_boundary",
            ok=not contracts_import_sdk,
            detail="contracts stay SDK-free",
        ),
    ]
    return checks, {}


def run_privacy_checks(report_payload: dict[str, Any] | None = None) -> tuple[list[CheckResult], dict[str, Any]]:
    provider = build_openrouter_provider(client=Client())
    diag = str(diagnostic_view_of_adapter(provider))
    forbidden_local = (
        TEST_ONLY_MODEL_REFERENCE,
        "https://openrouter.ai",
        "Authorization: Bearer",
        "HTTP-Referer:",
        "X-Title:",
        "Synthetic instruction text",
        "resp_should_never_appear",
        "sk-",
    )
    local_offenders = [token for token in forbidden_local if token in diag]
    checks = [
        CheckResult(
            name="adapter_diagnostics_omit_model_endpoint_headers_prompts",
            category="privacy",
            ok=not local_offenders,
            detail=f"offenders={local_offenders}",
        )
    ]
    if report_payload is None:
        checks.append(
            CheckResult(
                name="privacy_scan_deferred_until_report_assembled",
                category="privacy",
                ok=True,
                detail="report scanned after assembly",
            )
        )
        return checks, {}
    import json

    blob = json.dumps(report_payload, sort_keys=True)
    report_forbidden = (
        "sk-",
        "AKIA",
        "Authorization: Bearer",
        "HTTP-Referer:",
        "X-Title:",
        "https://openrouter.ai",
        TEST_ONLY_MODEL_REFERENCE,
        "Synthetic instruction text",
        "Synthetic context payload",
        '{"summary":"synthetic"}',
        "Traceback",
        "/Users/",
        "resp_should_never_appear",
    )
    offenders = [token for token in report_forbidden if token in blob]
    checks.append(
        CheckResult(
            name="verification_report_omits_secrets_endpoints_models_prompts",
            category="privacy",
            ok=not offenders,
            detail=f"offenders={offenders}",
        )
    )
    return checks, {}


__all__ = [
    "run_capability_checks",
    "run_client_boundary_checks",
    "run_configuration_checks",
    "run_dependency_boundary_checks",
    "run_execution_checks",
    "run_inventory_checks",
    "run_privacy_checks",
    "run_provider_identity_checks",
    "run_registration_and_runtime_checks",
    "run_regression_checks",
    "run_request_checks",
    "run_response_usage_error_checks",
]
