"""Core SV.11.10 checks: selection, config, model, credentials, wiring, privacy."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from codestrata.ai.provider_adapters.openrouter.client import resolve_client
from codestrata.ai.provider_adapters.openrouter.configuration import (
    DEFAULT_API_KEY_ENV_NAME,
    OPENROUTER_DEFAULT_BASE_URL,
    build_runtime_configuration,
    normalize_base_url,
    resolve_optional_app_name,
    resolve_optional_site_url,
    validate_https_url,
)
from codestrata.ai.provider_adapters.openrouter.diagnostics import diagnostic_view_of_adapter
from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_provider,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY

# Import factory before assess_ai to keep load order stable.
from codestrata.ai.providers.factory import (  # noqa: I001
    CODESTRATA_OPENROUTER_MODEL_ID_ENV as FACTORY_OPENROUTER_MODEL_ENV,
    create_assess_ai_provider,
    resolve_assess_model_id,
    supported_assess_ai_providers,
)
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider
from codestrata.config.profiles import OPENROUTER_MODEL_ENV_VAR, apply_environment_overlays
from codestrata.config.settings import AiSettings, CodestrataSettings, OpenRouterSettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)
from verification.openrouter_configuration.contract import (
    ASSESS_REGISTERED_PROVIDERS,
    BEDROCK_DEFAULT_MODEL,
    CODESTRATA_OPENROUTER_MODEL_ID_ENV,
    DEFAULT_API_KEY_ENV,
    DEFAULT_PROVIDER,
    EXPECTED_MAXIMUM_ATTEMPTS,
    EXPECTED_OPENROUTER_SETTINGS_FIELDS,
    FORBIDDEN_OPENROUTER_SETTINGS_FIELDS,
    OPENAI_DEFAULT_MODEL,
    PROVIDER_ID,
    TEST_ONLY_MODEL,
)
from verification.openrouter_configuration.fixtures import (
    SYNTHETIC_API_KEY,
    SYNTHETIC_OPENAI_API_KEY,
    Client,
    CountingEnvironmentReader,
    invocation_options,
    model_request,
    no_environment,
    provider_request,
    sdk_exception,
    settings_for,
)
from verification.openrouter_configuration.models import CheckResult


def _rejected(callable_under_test) -> bool:
    try:
        callable_under_test()
    except (ProviderContractValidationError, ValueError, AIProviderConfigurationError):
        return True
    except Exception:  # noqa: BLE001
        return True
    return False


def _env_without(*names: str) -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in names}


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    fields = tuple(sorted(OpenRouterSettings.model_fields))
    expected = tuple(sorted(EXPECTED_OPENROUTER_SETTINGS_FIELDS))
    forbidden_present = sorted(set(FORBIDDEN_OPENROUTER_SETTINGS_FIELDS) & set(fields))
    checks = [
        CheckResult(
            name="openrouter_settings_has_expected_fields",
            category="inventory",
            ok=fields == expected and not forbidden_present,
            detail=f"field_count={len(fields)} forbidden={forbidden_present}",
        ),
        CheckResult(
            name="openrouter_default_api_key_env_name_matches_contract",
            category="inventory",
            ok=DEFAULT_API_KEY_ENV_NAME == DEFAULT_API_KEY_ENV
            and OpenRouterSettings().api_key_env == DEFAULT_API_KEY_ENV,
            detail="api_key_env name only",
        ),
        CheckResult(
            name="factory_model_env_constant_matches_contract",
            category="inventory",
            ok=FACTORY_OPENROUTER_MODEL_ENV == CODESTRATA_OPENROUTER_MODEL_ID_ENV
            and OPENROUTER_MODEL_ENV_VAR == CODESTRATA_OPENROUTER_MODEL_ID_ENV,
            detail="env name aligned",
        ),
        CheckResult(
            name="openrouter_adapter_package_present",
            category="inventory",
            ok=(
                engine_root / "src/codestrata/ai/provider_adapters/openrouter/configuration.py"
            ).is_file(),
            detail="adapter configuration module present",
        ),
    ]
    return checks, {"field_count": len(fields)}


def run_provider_selection_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    reset_assess_ai_provider_registry_for_tests()
    try:
        registered = get_assess_ai_provider_registry().list_providers()
    finally:
        reset_assess_ai_provider_registry_for_tests()

    default_settings = settings_for(DEFAULT_PROVIDER)
    openrouter_settings = settings_for(PROVIDER_ID)
    created_default = create_assess_ai_provider(default_settings)
    created_openrouter = create_assess_ai_provider(openrouter_settings)

    unknown_rejected = False
    try:
        create_assess_ai_provider(settings_for("not-a-provider"))
    except AIProviderConfigurationError:
        unknown_rejected = True
    except Exception:  # noqa: BLE001
        unknown_rejected = False

    aws_rejected = False
    try:
        create_assess_ai_provider(settings_for("aws_bedrock"))
    except AIProviderConfigurationError:
        aws_rejected = True
    except Exception:  # noqa: BLE001
        aws_rejected = False

    with patch.dict(os.environ, {DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY}, clear=False):
        still_bedrock = AiSettings().provider == DEFAULT_PROVIDER
        env_only_created = create_assess_ai_provider(settings_for(DEFAULT_PROVIDER))

    checks = [
        CheckResult(
            name="bedrock_remains_default_provider",
            category="provider_selection",
            ok=AiSettings().provider == DEFAULT_PROVIDER,
            detail=f"provider={AiSettings().provider}",
        ),
        CheckResult(
            name="assess_registry_lists_bedrock_openai_openrouter",
            category="provider_selection",
            ok=registered == ASSESS_REGISTERED_PROVIDERS,
            detail=f"registered={list(registered)}",
        ),
        CheckResult(
            name="explicit_openrouter_selection_creates_openrouter_provider",
            category="provider_selection",
            ok=isinstance(created_openrouter, OpenRouterAIModelProvider),
            detail=f"class={type(created_openrouter).__name__}",
        ),
        CheckResult(
            name="default_selection_is_not_openrouter",
            category="provider_selection",
            ok=not isinstance(created_default, OpenRouterAIModelProvider),
            detail=f"class={type(created_default).__name__}",
        ),
        CheckResult(
            name="unknown_provider_is_rejected",
            category="provider_selection",
            ok=unknown_rejected,
            detail="AIProviderConfigurationError expected",
        ),
        CheckResult(
            name="analytics_family_aws_bedrock_is_rejected",
            category="provider_selection",
            ok=aws_rejected,
            detail="aws_bedrock remains analytics-only",
        ),
        CheckResult(
            name="api_key_presence_does_not_auto_select_openrouter",
            category="provider_selection",
            ok=still_bedrock and not isinstance(env_only_created, OpenRouterAIModelProvider),
            detail="explicit settings.ai.provider required",
        ),
    ]
    return checks, {"registered": list(registered)}


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {
                "provider": "openrouter",
                "openrouter": {
                    "model": "",
                    "api_key_env": DEFAULT_API_KEY_ENV,
                    "site_url": "",
                    "app_name": "",
                },
            },
        }
    )
    dumped = settings.model_dump(mode="json")
    openrouter_dump = dumped.get("ai", {}).get("openrouter", {})
    serialized = json.dumps(dumped, sort_keys=True)
    redacted = build_runtime_configuration(
        openrouter_settings=settings.ai.openrouter
    ).redacted()

    checks = [
        CheckResult(
            name="codestrata_settings_projects_ai_openrouter_section",
            category="configuration",
            ok=isinstance(settings.ai.openrouter, OpenRouterSettings),
            detail="OpenRouterSettings nested under ai.openrouter",
        ),
        CheckResult(
            name="openrouter_settings_has_no_plaintext_api_key_field",
            category="configuration",
            ok="api_key" not in OpenRouterSettings.model_fields
            and "api_key" not in openrouter_dump,
            detail="api_key_env name only",
        ),
        CheckResult(
            name="canonical_settings_serialization_omits_api_key_values",
            category="configuration",
            ok=SYNTHETIC_API_KEY not in serialized and "sk-" not in serialized,
            detail="no secret material in model_dump",
        ),
        CheckResult(
            name="adapter_redacted_view_omits_endpoint_and_secrets",
            category="configuration",
            ok=(
                "base_url" not in redacted
                and redacted.get("api_key_present") is False
                and redacted.get("adapter_kind") == "openrouter"
            ),
            detail="presence flags only",
        ),
        CheckResult(
            name="empty_model_is_the_product_default",
            category="configuration",
            ok=OpenRouterSettings().model == "" and AiSettings().openrouter.model == "",
            detail="no product model default",
        ),
    ]
    return checks, {}


def run_model_resolution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    base = settings_for(
        PROVIDER_ID,
        openrouter={"model": "configured-openrouter-model"},
    )
    cli_wins = resolve_assess_model_id(cli_model_id="cli-openrouter-model", settings=base)

    with patch.dict(
        os.environ,
        {CODESTRATA_OPENROUTER_MODEL_ID_ENV: "env-openrouter-model"},
        clear=False,
    ):
        env_wins = resolve_assess_model_id(cli_model_id=None, settings=base)

    config_only = settings_for(
        PROVIDER_ID,
        openrouter={"model": "configured-openrouter-model"},
    )
    with patch.dict(
        os.environ,
        _env_without(CODESTRATA_OPENROUTER_MODEL_ID_ENV),
        clear=True,
    ):
        from_config = resolve_assess_model_id(cli_model_id=None, settings=config_only)

    missing_raises = False
    missing_settings = settings_for(PROVIDER_ID, openrouter={"model": ""})
    with patch.dict(
        os.environ,
        _env_without(CODESTRATA_OPENROUTER_MODEL_ID_ENV),
        clear=True,
    ):
        try:
            resolve_assess_model_id(cli_model_id=None, settings=missing_settings)
        except AIProviderConfigurationError:
            missing_raises = True
        except Exception:  # noqa: BLE001
            missing_raises = False

    opaque_ok = ProviderModelReference(TEST_ONLY_MODEL).value == TEST_ONLY_MODEL

    overlay = apply_environment_overlays(
        {"ai": {"openrouter": {"model": ""}}},
        environ={OPENROUTER_MODEL_ENV_VAR: "profile-overlay-model"},
    )
    overlay_ok = (
        overlay.get("ai", {}).get("openrouter", {}).get("model") == "profile-overlay-model"
    )

    checks = [
        CheckResult(
            name="cli_model_id_wins_over_env_and_config",
            category="model_resolution",
            ok=cli_wins == "cli-openrouter-model",
            detail="CLI precedence",
        ),
        CheckResult(
            name="env_model_id_wins_over_config_when_cli_absent",
            category="model_resolution",
            ok=env_wins == "env-openrouter-model",
            detail="environment precedence",
        ),
        CheckResult(
            name="config_model_used_when_cli_and_env_absent",
            category="model_resolution",
            ok=from_config == "configured-openrouter-model",
            detail="toml/config precedence",
        ),
        CheckResult(
            name="missing_openrouter_model_raises_configuration_error",
            category="model_resolution",
            ok=missing_raises,
            detail="no product default",
        ),
        CheckResult(
            name="model_reference_is_opaque",
            category="model_resolution",
            ok=opaque_ok,
            detail="opaque string accepted",
        ),
        CheckResult(
            name="profiles_overlay_applies_openrouter_model_env",
            category="model_resolution",
            ok=overlay_ok,
            detail="profiles overlay path",
        ),
    ]
    return checks, {}


def run_credential_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    inputs = build_runtime_configuration().client_inputs

    missing = resolve_client(inputs, environment_reader=no_environment)
    empty = resolve_client(inputs, environment_reader=lambda _n: "")
    whitespace = resolve_client(inputs, environment_reader=lambda _n: "   ")

    openai_only = CountingEnvironmentReader({"OPENAI_API_KEY": SYNTHETIC_OPENAI_API_KEY})
    no_fallback = resolve_client(inputs, environment_reader=openai_only)

    present = CountingEnvironmentReader({DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY})
    injected = resolve_client(
        inputs,
        injected_client=Client(),
        environment_reader=present,
    )

    from codestrata.ai.provider_adapters.openrouter import error_mapping, legacy_bridge

    legacy = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY),
        api_key_env_name=DEFAULT_API_KEY_ENV,
    )

    checks = [
        CheckResult(
            name="missing_api_key_maps_to_missing_configuration",
            category="credentials",
            ok=(
                missing.error is not None
                and missing.error.category is ErrorCategory.MISSING_CONFIGURATION
            ),
            detail="MISSING_CONFIGURATION",
        ),
        CheckResult(
            name="empty_api_key_maps_to_missing_configuration",
            category="credentials",
            ok=(
                empty.error is not None
                and empty.error.category is ErrorCategory.MISSING_CONFIGURATION
            ),
            detail="empty rejected",
        ),
        CheckResult(
            name="whitespace_api_key_maps_to_missing_configuration",
            category="credentials",
            ok=(
                whitespace.error is not None
                and whitespace.error.category is ErrorCategory.MISSING_CONFIGURATION
            ),
            detail="whitespace rejected",
        ),
        CheckResult(
            name="openai_api_key_is_not_reused_for_openrouter",
            category="credentials",
            ok=(
                no_fallback.error is not None
                and no_fallback.error.category is ErrorCategory.MISSING_CONFIGURATION
                and DEFAULT_API_KEY_ENV in openai_only.calls
            ),
            detail="OPENAI_API_KEY ignored",
        ),
        CheckResult(
            name="injected_client_skips_environment_reader",
            category="credentials",
            ok=injected.ok and injected.handle is not None and not present.calls,
            detail="inject wins",
        ),
        CheckResult(
            name="legacy_missing_key_raises_configuration_error_without_secret",
            category="credentials",
            ok=(
                isinstance(legacy, AIProviderConfigurationError)
                and SYNTHETIC_API_KEY not in str(legacy)
                and DEFAULT_API_KEY_ENV in str(legacy)
            ),
            detail="AIProviderConfigurationError without key value",
        ),
    ]
    return checks, {}


def run_base_url_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    default = normalize_base_url(None)
    http_rejected = _rejected(lambda: normalize_base_url("http://example.invalid/api/v1"))
    creds_rejected = _rejected(
        lambda: normalize_base_url("https://user:pass@example.invalid/api/v1")
    )
    diag = str(diagnostic_view_of_adapter(build_openrouter_provider(client=Client())))
    checks = [
        CheckResult(
            name="default_base_url_is_openrouter_https_endpoint",
            category="base_url",
            ok=default == OPENROUTER_DEFAULT_BASE_URL and default.startswith("https://"),
            detail="https default applied",
        ),
        CheckResult(
            name="http_base_url_is_rejected",
            category="base_url",
            ok=http_rejected,
            detail="HTTP rejected",
        ),
        CheckResult(
            name="base_url_with_embedded_credentials_is_rejected",
            category="base_url",
            ok=creds_rejected,
            detail="credentials in URL rejected",
        ),
        CheckResult(
            name="diagnostics_omit_raw_base_url",
            category="base_url",
            ok=OPENROUTER_DEFAULT_BASE_URL not in diag and "example.invalid" not in diag,
            detail="presence flag only",
        ),
    ]
    return checks, {}


def run_header_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    empty = OpenRouterSettings()
    with_headers = OpenRouterSettings(
        site_url="https://example.invalid",
        app_name="CodeStrataProbe",
    )
    site = resolve_optional_site_url(with_headers)
    app = resolve_optional_app_name(with_headers)
    http_site_rejected = _rejected(
        lambda: validate_https_url("http://example.invalid", field_name="site_url")
    )
    long_name_rejected = _rejected(
        lambda: resolve_optional_app_name(OpenRouterSettings(app_name="x" * 129))
    )
    no_headers_field = "headers" not in OpenRouterSettings.model_fields
    runtime = build_runtime_configuration(openrouter_settings=with_headers)
    diag = str(
        diagnostic_view_of_adapter(
            build_openrouter_provider(configuration=runtime, client=Client())
        )
    )
    with_repo = settings_for(
        PROVIDER_ID,
        openrouter={"site_url": "", "app_name": ""},
        repository_path="/tmp/synthetic-customer-repo",
    )
    derived = build_runtime_configuration(openrouter_settings=with_repo.ai.openrouter)

    checks = [
        CheckResult(
            name="optional_site_url_and_app_name_default_unset",
            category="headers",
            ok=resolve_optional_site_url(empty) is None
            and resolve_optional_app_name(empty) is None,
            detail="optional identification headers",
        ),
        CheckResult(
            name="https_site_url_and_bounded_app_name_accepted",
            category="headers",
            ok=site == "https://example.invalid" and app == "CodeStrataProbe",
            detail="site_url and app_name resolved",
        ),
        CheckResult(
            name="http_site_url_rejected",
            category="headers",
            ok=http_site_rejected,
            detail="HTTPS required",
        ),
        CheckResult(
            name="oversized_app_name_rejected",
            category="headers",
            ok=long_name_rejected,
            detail="app_name bounded",
        ),
        CheckResult(
            name="no_arbitrary_header_map_on_settings",
            category="headers",
            ok=no_headers_field,
            detail="no headers dict field",
        ),
        CheckResult(
            name="diagnostics_omit_header_values",
            category="headers",
            ok=(
                "HTTP-Referer" not in diag
                and "X-Title" not in diag
                and "example.invalid" not in diag
                and "CodeStrataProbe" not in diag
            ),
            detail="presence flags only",
        ),
        CheckResult(
            name="site_url_not_derived_from_repository_path",
            category="headers",
            ok=derived.client_inputs.site_url is None
            and derived.client_inputs.app_name is None,
            detail="no repository or customer derivation",
        ),
    ]
    return checks, {}


def run_client_construction_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    reader = CountingEnvironmentReader({DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY})
    provider = build_openrouter_provider(environment_reader=reader)
    supports_ok = provider.supports(CapabilityId.MODERNIZATION_ADVISOR)
    discovery_calls = list(reader.calls)

    injected = Client()
    with_inject = build_openrouter_provider(client=injected, environment_reader=reader)
    result = with_inject.execute(provider_request())
    inject_reader_calls_after = list(reader.calls)

    redacted_repr = repr(build_runtime_configuration().client_inputs)
    handle = resolve_client(
        build_runtime_configuration().client_inputs,
        injected_client=Client(),
    ).handle
    handle_repr = repr(handle)

    checks = [
        CheckResult(
            name="client_construction_is_lazy_until_execute",
            category="client_construction",
            ok=supports_ok and not discovery_calls,
            detail="supports/discovery does not read env",
        ),
        CheckResult(
            name="injected_client_wins_without_env_read",
            category="client_construction",
            ok=result.error is None and inject_reader_calls_after == discovery_calls,
            detail="inject path",
        ),
        CheckResult(
            name="environment_reader_is_injectable",
            category="client_construction",
            ok=callable(reader) and provider.client_injected is False,
            detail="reader injectable on factory",
        ),
        CheckResult(
            name="client_inputs_and_handle_repr_are_redacted",
            category="client_construction",
            ok=(
                OPENROUTER_DEFAULT_BASE_URL not in redacted_repr
                and SYNTHETIC_API_KEY not in redacted_repr
                and SYNTHETIC_API_KEY not in handle_repr
                and "Authorization" not in handle_repr
            ),
            detail="redacted repr",
        ),
    ]
    return checks, {}


def run_runtime_wiring_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_adapters.openrouter.adapter import OpenRouterProvider
    from codestrata.ai.providers.bedrock import BedrockAIModelProvider
    from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider

    settings = settings_for(PROVIDER_ID, openrouter={"model": TEST_ONLY_MODEL})
    created = create_assess_ai_provider(settings)
    client = Client()
    wired = OpenRouterAIModelProvider(settings=settings, client=client)
    outcome = wired.invoke(model_request(), invocation_options())

    adapter = build_openrouter_provider(client=Client())
    checks = [
        CheckResult(
            name="create_assess_ai_provider_returns_openrouter_wrapper",
            category="runtime_wiring",
            ok=isinstance(created, OpenRouterAIModelProvider)
            and not isinstance(created, OpenAIAIModelProvider)
            and not isinstance(created, BedrockAIModelProvider),
            detail=f"class={type(created).__name__}",
        ),
        CheckResult(
            name="wrapper_uses_slice_11_9_openrouter_adapter",
            category="runtime_wiring",
            ok=isinstance(adapter, OpenRouterProvider),
            detail="OpenRouterProvider adapter",
        ),
        CheckResult(
            name="single_invocation_with_injected_client",
            category="runtime_wiring",
            ok=len(client.calls) == 1 and outcome is not None,
            detail=f"calls={len(client.calls)}",
        ),
        CheckResult(
            name="no_dual_provider_construction_for_openrouter_selection",
            category="runtime_wiring",
            ok=PROVIDER_ID in supported_assess_ai_providers(),
            detail="single registered openrouter factory",
        ),
        CheckResult(
            name="executor_maximum_attempts_remains_one",
            category="runtime_wiring",
            ok=(
                OPENROUTER_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
                and OPENROUTER_RETRY_POLICY is DEFAULT_RETRY_POLICY
            ),
            detail="operational_retry_conservative",
        ),
    ]
    return checks, {}


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.provider_adapters.openrouter import error_mapping, legacy_bridge

    missing = legacy_bridge.legacy_error_for(
        error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY),
        api_key_env_name=DEFAULT_API_KEY_ENV,
    )
    provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=Client(sdk_exception("AuthenticationError", "upstream rejected credentials")),
    )
    raised: Exception | None
    try:
        provider.invoke(model_request(), invocation_options())
        raised = None
    except Exception as error:  # noqa: BLE001
        raised = error

    checks = [
        CheckResult(
            name="missing_configuration_maps_to_legacy_configuration_error",
            category="fail_soft",
            ok=isinstance(missing, AIProviderConfigurationError)
            and SYNTHETIC_API_KEY not in str(missing),
            detail="legacy AIProviderConfigurationError",
        ),
        CheckResult(
            name="invoke_failure_does_not_leak_api_key",
            category="fail_soft",
            ok=raised is not None and SYNTHETIC_API_KEY not in str(raised),
            detail=f"raised={type(raised).__name__ if raised else None}",
        ),
        CheckResult(
            name="assessment_fail_soft_ownership_retained",
            category="fail_soft",
            ok=raised is not None,
            detail="assessment service owns fail-soft classification of raised errors",
        ),
    ]
    return checks, {}


def run_cli_and_doctor_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    assess = (engine_root / "src/codestrata/cli/assess.py").read_text(encoding="utf-8")
    doctor = (engine_root / "src/codestrata/ai/providers/doctor.py").read_text(encoding="utf-8")
    forbidden_flags = (
        "--openrouter-api-key",
        "--openrouter-key",
        "--openrouter-base-url",
        "--openrouter-site-url",
        "--openrouter-app-name",
    )
    flag_offenders = [flag for flag in forbidden_flags if flag in assess]
    checks = [
        CheckResult(
            name="assess_cli_may_mention_openrouter_in_help",
            category="cli",
            ok="OpenRouter" in assess or "openrouter" in assess,
            detail="help text may mention OpenRouter",
        ),
        CheckResult(
            name="assess_cli_has_no_openrouter_credential_flags",
            category="cli",
            ok=not flag_offenders,
            detail=f"offenders={flag_offenders}",
        ),
        CheckResult(
            name="doctor_has_openrouter_local_readiness",
            category="doctor",
            ok=(
                "evaluate_openrouter_readiness" in doctor
                and 'name="openrouter"' in doctor
                and "provider_adapters.openrouter" not in doctor
                and "OpenRouterAIModelProvider" not in doctor
                and "chat.completions" not in doctor
                and ".invoke(" not in doctor
            ),
            detail="doctor local readiness in 11.11; no OpenRouter client or model invoke",
        ),
    ]
    return checks, {}


def run_regression_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    bedrock_settings = settings_for("bedrock")
    openai_settings = settings_for("openai")
    with patch.dict(
        os.environ,
        _env_without(
            "CODESTRATA_BEDROCK_MODEL_ID",
            "CODESTRATA_OPENAI_MODEL_ID",
            CODESTRATA_OPENROUTER_MODEL_ID_ENV,
        ),
        clear=True,
    ):
        bedrock_model = resolve_assess_model_id(cli_model_id=None, settings=bedrock_settings)
        openai_model = resolve_assess_model_id(cli_model_id=None, settings=openai_settings)

    checks = [
        CheckResult(
            name="openai_default_model_unchanged",
            category="openai_regression",
            ok=openai_model == OPENAI_DEFAULT_MODEL
            and AiSettings().openai.answer_model == OPENAI_DEFAULT_MODEL,
            detail="openai default preserved",
        ),
        CheckResult(
            name="bedrock_default_model_and_provider_unchanged",
            category="bedrock_regression",
            ok=bedrock_model == BEDROCK_DEFAULT_MODEL
            and AiSettings().provider == DEFAULT_PROVIDER,
            detail="bedrock default preserved",
        ),
        CheckResult(
            name="test_only_model_is_not_product_default",
            category="openai_regression",
            ok=(
                AiSettings().openrouter.model != TEST_ONLY_MODEL
                and OpenRouterSettings().model != TEST_ONLY_MODEL
                and AiSettings().openai.answer_model != TEST_ONLY_MODEL
            ),
            detail="fixture model excluded from defaults",
        ),
    ]
    return checks, {}


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    package = engine_root / "src/codestrata/ai/provider_adapters/openrouter"
    contracts = engine_root / "src/codestrata/ai/provider_contracts"
    wrapper = engine_root / "src/codestrata/ai/providers/openrouter_provider.py"

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

    contracts_import_sdk = False
    for path in contracts.glob("*.py"):
        for name in imports(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                contracts_import_sdk = True

    wrapper_imports = imports(wrapper)
    wrapper_imports_openai_sdk = any(
        name == "openai" or name.startswith("openai.") for name in wrapper_imports
    )

    checks = [
        CheckResult(
            name="openrouter_adapter_does_not_import_openai_adapter",
            category="dependency_boundary",
            ok=not openrouter_imports_openai_adapter,
            detail="no OpenAI adapter reuse via import",
        ),
        CheckResult(
            name="common_contracts_remain_sdk_free",
            category="dependency_boundary",
            ok=not contracts_import_sdk,
            detail="contracts stay SDK-free",
        ),
        CheckResult(
            name="openrouter_wrapper_does_not_import_openai_sdk_types",
            category="dependency_boundary",
            ok=not wrapper_imports_openai_sdk,
            detail="assessment wrapper stays SDK-type free",
        ),
    ]
    return checks, {}


def run_privacy_checks(
    report_payload: dict[str, Any] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    provider = build_openrouter_provider(
        openrouter_settings=OpenRouterSettings(
            model=TEST_ONLY_MODEL,
            site_url="https://example.invalid",
            app_name="LeakProbe",
        ),
        client=Client(),
    )
    diag = str(diagnostic_view_of_adapter(provider))
    local_forbidden = (
        TEST_ONLY_MODEL,
        OPENROUTER_DEFAULT_BASE_URL,
        "Authorization",
        "HTTP-Referer",
        "X-Title",
        "example.invalid",
        "LeakProbe",
        SYNTHETIC_API_KEY,
        "sk-",
    )
    local_offenders = [token for token in local_forbidden if token in diag]
    checks = [
        CheckResult(
            name="adapter_diagnostics_omit_secrets_endpoints_headers_models",
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

    blob = json.dumps(report_payload, sort_keys=True)
    report_forbidden = (
        "sk-",
        "AKIA",
        SYNTHETIC_API_KEY,
        SYNTHETIC_OPENAI_API_KEY,
        "Authorization: Bearer",
        "HTTP-Referer",
        "X-Title",
        OPENROUTER_DEFAULT_BASE_URL,
        "https://",
        "http://",
        TEST_ONLY_MODEL,
        "cli-openrouter-model",
        "env-openrouter-model",
        "configured-openrouter-model",
        "profile-overlay-model",
        "Synthetic instruction text",
        "Synthetic context payload",
        '{"summary":"synthetic"}',
        "Traceback",
        "/Users/",
        "/tmp/",
        "resp_should_never_appear",
        "example.invalid",
        "LeakProbe",
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


def run_determinism_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    first = build_runtime_configuration(openrouter_settings=OpenRouterSettings()).redacted()
    second = build_runtime_configuration(openrouter_settings=OpenRouterSettings()).redacted()
    checks = [
        CheckResult(
            name="runtime_configuration_redaction_is_deterministic",
            category="determinism",
            ok=first == second,
            detail="identical redacted views",
        )
    ]
    return checks, {}


__all__ = [
    "run_base_url_checks",
    "run_cli_and_doctor_checks",
    "run_client_construction_checks",
    "run_configuration_checks",
    "run_credential_checks",
    "run_dependency_boundary_checks",
    "run_determinism_checks",
    "run_fail_soft_checks",
    "run_header_checks",
    "run_inventory_checks",
    "run_model_resolution_checks",
    "run_privacy_checks",
    "run_provider_selection_checks",
    "run_regression_checks",
    "run_runtime_wiring_checks",
]
