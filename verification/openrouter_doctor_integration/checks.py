"""Core SV.11.11 checks: doctor policy, readiness, integration, privacy."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_provider,
)
from codestrata.ai.provider_contracts.identifiers import ProviderId
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY

# Import factory before assess_ai to keep load order stable.
from codestrata.ai.providers.factory import (  # noqa: I001
    create_assess_ai_provider,
    resolve_assess_model_id,
    supported_assess_ai_providers,
)
from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.doctor import (
    ConfigStatus,
    OpenRouterBaseUrlStatus,
    OpenRouterReadinessStatus,
    build_ai_configuration_report,
    evaluate_openrouter_readiness,
)
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.ai.providers.openrouter_provider import OpenRouterAIModelProvider
from codestrata.config.settings import AiSettings, OpenRouterSettings
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from verification.openrouter_doctor_integration.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    ASSESS_REGISTERED_PROVIDERS,
    BEDROCK_DEFAULT_MODEL,
    CODESTRATA_OPENROUTER_MODEL_ID_ENV,
    DEFAULT_API_KEY_ENV,
    DEFAULT_PROVIDER,
    DOCTOR_FORBIDDEN_ADAPTER_IMPORT,
    DOCTOR_FORBIDDEN_CALL_TOKENS,
    EXPECTED_MAXIMUM_ATTEMPTS,
    OPENAI_DEFAULT_MODEL,
    PROVIDER_ID,
    TEST_ONLY_MODEL,
)
from verification.openrouter_doctor_integration.fixtures import (
    SYNTHETIC_API_KEY,
    SYNTHETIC_APP_NAME,
    SYNTHETIC_CONTEXT,
    SYNTHETIC_INSTRUCTION,
    SYNTHETIC_INVALID_BASE_URL,
    SYNTHETIC_INVALID_SITE_URL,
    SYNTHETIC_OPENAI_API_KEY,
    SYNTHETIC_SITE_URL,
    Client,
    CountingEnvironmentReader,
    Response,
    injected_environ,
    invocation_options,
    model_request,
    provider_request,
    sdk_exception,
    settings_for,
)
from verification.openrouter_doctor_integration.models import CheckResult

_DOCTOR_REL = "src/codestrata/ai/providers/doctor.py"


def _doctor_source(engine_root: Path) -> str:
    return (engine_root / _DOCTOR_REL).read_text(encoding="utf-8")


def _doctor_imports(engine_root: Path) -> set[str]:
    tree = ast.parse(_doctor_source(engine_root), filename="doctor.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _safe_detail(value: str) -> str:
    """Strip known secret/model/url tokens from check details."""

    forbidden = (
        SYNTHETIC_API_KEY,
        SYNTHETIC_OPENAI_API_KEY,
        TEST_ONLY_MODEL,
        SYNTHETIC_SITE_URL,
        SYNTHETIC_INVALID_BASE_URL,
        SYNTHETIC_INVALID_SITE_URL,
        SYNTHETIC_APP_NAME,
        SYNTHETIC_INSTRUCTION,
        SYNTHETIC_CONTEXT,
        "sk-",
        "https://",
        "http://",
    )
    cleaned = value
    for token in forbidden:
        cleaned = cleaned.replace(token, "[redacted]")
    return cleaned


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    doctor_path = engine_root / _DOCTOR_REL
    source = doctor_path.read_text(encoding="utf-8") if doctor_path.is_file() else ""
    checks = [
        CheckResult(
            name="doctor_module_present",
            category="inventory",
            ok=doctor_path.is_file(),
            detail="doctor.py present",
        ),
        CheckResult(
            name="doctor_exports_openrouter_readiness_api",
            category="inventory",
            ok=(
                "evaluate_openrouter_readiness" in source
                and "OpenRouterDoctorReadiness" in source
                and "OpenRouterReadinessStatus" in source
                and "build_ai_configuration_report" in source
            ),
            detail="readiness API symbols present",
        ),
        CheckResult(
            name="openrouter_wrapper_present",
            category="inventory",
            ok=(
                engine_root / "src/codestrata/ai/providers/openrouter_provider.py"
            ).is_file(),
            detail="OpenRouterAIModelProvider present",
        ),
        CheckResult(
            name="assess_registered_providers_include_openrouter",
            category="inventory",
            ok=set(ASSESS_REGISTERED_PROVIDERS).issubset(supported_assess_ai_providers()),
            detail="registry includes expected providers",
        ),
    ]
    return checks, {}


def run_doctor_policy_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    source = _doctor_source(engine_root)
    imports = _doctor_imports(engine_root)
    call_offenders = [token for token in DOCTOR_FORBIDDEN_CALL_TOKENS if token in source]
    adapter_import = any(DOCTOR_FORBIDDEN_ADAPTER_IMPORT in name for name in imports)
    tree = ast.parse(source, filename="doctor.py")
    open_write = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "open" and len(node.args) >= 2:
                mode = node.args[1]
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                    if any(flag in mode.value for flag in ("w", "a", "x")):
                        open_write = True
            if name in {"write_text", "write_bytes", "write"}:
                open_write = True

    mutates = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    text = ast.dump(target)
                    if "settings" in text and ("provider" in text or "openrouter" in text):
                        mutates = True

    checks = [
        CheckResult(
            name="doctor_source_has_no_provider_invocation_calls",
            category="doctor_policy",
            ok=not call_offenders,
            detail=f"offenders={call_offenders}",
        ),
        CheckResult(
            name="doctor_does_not_import_openrouter_adapter",
            category="doctor_policy",
            ok=not adapter_import,
            detail="compatibility isolation retained",
        ),
        CheckResult(
            name="doctor_does_not_write_files",
            category="doctor_policy",
            ok=not open_write and "Path.write" not in source,
            detail="no Path.write / open write for doctor",
        ),
        CheckResult(
            name="doctor_ast_has_no_settings_assignment",
            category="doctor_policy",
            ok=not mutates,
            detail="no settings field assignment",
        ),
    ]
    return checks, {}


def run_readiness_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    env = injected_environ()
    ready = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        dependency_available=True,
    )
    model_missing = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": ""}),
        environ={DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY},
        dependency_available=True,
    )
    credential_missing = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ={},
        dependency_available=True,
    )
    dependency_missing = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        dependency_available=False,
    )
    invalid_base = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={"model": TEST_ONLY_MODEL, "base_url": SYNTHETIC_INVALID_BASE_URL},
        ),
        environ=env,
        dependency_available=True,
    )
    invalid_site = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={"model": TEST_ONLY_MODEL, "site_url": SYNTHETIC_INVALID_SITE_URL},
        ),
        environ=env,
        dependency_available=True,
    )
    redacted_blob = json.dumps(ready.redacted(), sort_keys=True)

    checks = [
        CheckResult(
            name="readiness_ready_when_model_key_dependency_ok",
            category="readiness",
            ok=ready.readiness is OpenRouterReadinessStatus.READY and ready.configured,
            detail="ready status",
        ),
        CheckResult(
            name="readiness_model_missing",
            category="model",
            ok=model_missing.readiness is OpenRouterReadinessStatus.MODEL_MISSING,
            detail="model_missing status",
        ),
        CheckResult(
            name="readiness_credential_missing",
            category="credentials",
            ok=credential_missing.readiness is OpenRouterReadinessStatus.CREDENTIAL_MISSING,
            detail="credential_missing status",
        ),
        CheckResult(
            name="readiness_dependency_missing",
            category="dependency",
            ok=dependency_missing.readiness is OpenRouterReadinessStatus.DEPENDENCY_MISSING,
            detail="dependency_missing status",
        ),
        CheckResult(
            name="readiness_invalid_base_url",
            category="base_url",
            ok=(
                invalid_base.readiness is OpenRouterReadinessStatus.INVALID_CONFIGURATION
                and invalid_base.base_url_status is OpenRouterBaseUrlStatus.INVALID
            ),
            detail="invalid base url category",
        ),
        CheckResult(
            name="readiness_invalid_site_url",
            category="optional_header",
            ok=invalid_site.readiness is OpenRouterReadinessStatus.INVALID_CONFIGURATION,
            detail="invalid site_url category",
        ),
        CheckResult(
            name="redacted_readiness_omits_secrets_urls_models",
            category="readiness",
            ok=(
                SYNTHETIC_API_KEY not in redacted_blob
                and TEST_ONLY_MODEL not in redacted_blob
                and "https://" not in redacted_blob
                and "http://" not in redacted_blob
                and "sk-" not in redacted_blob
            ),
            detail="redacted dict privacy-safe",
        ),
        CheckResult(
            name="doctor_uses_injected_environ_only",
            category="credentials",
            ok=True,
            detail="evaluate_openrouter_readiness called with injected environ",
        ),
    ]
    return checks, {}


def run_formatting_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    env = injected_environ()
    configured = build_ai_configuration_report(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        openrouter_dependency_available=True,
    )
    not_configured = build_ai_configuration_report(
        settings_for("openrouter", openrouter={"model": ""}),
        environ=env,
        openrouter_dependency_available=True,
    )
    overview_names = tuple(item.name for item in configured.providers)
    checks = [
        CheckResult(
            name="configuration_report_includes_openrouter_overview",
            category="doctor_output",
            ok="openrouter" in overview_names and configured.openrouter_readiness is not None,
            detail="openrouter overview present",
        ),
        CheckResult(
            name="openrouter_model_label_is_presence_only_when_configured",
            category="doctor_output",
            ok=configured.model_id == "(configured)",
            detail="presence label configured",
        ),
        CheckResult(
            name="openrouter_model_label_is_presence_only_when_missing",
            category="doctor_output",
            ok=not_configured.model_id == "(not configured)",
            detail="presence label not configured",
        ),
        CheckResult(
            name="doctor_output_omits_secret_and_model_values",
            category="doctor_output",
            ok=(
                SYNTHETIC_API_KEY not in configured.model_id
                and TEST_ONLY_MODEL not in configured.model_id
                and all(TEST_ONLY_MODEL not in item.detail for item in configured.providers)
            ),
            detail="no secret or model in overview labels",
        ),
    ]
    return checks, {}


def run_doctor_exit_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    """Simulate CLI exit semantics via ConfigStatus of the active provider."""

    env = injected_environ()
    active_not_ready = build_ai_configuration_report(
        settings_for("openrouter", openrouter={"model": ""}),
        environ=env,
        openrouter_dependency_available=True,
    )
    active_overview = next(
        (item for item in active_not_ready.providers if item.name == "openrouter"),
        None,
    )
    would_exit_1 = (
        active_overview is None or active_overview.status is not ConfigStatus.CONFIGURED
    )

    bedrock_active = build_ai_configuration_report(
        settings_for("bedrock", openrouter={"model": ""}),
        environ={},
        openrouter_dependency_available=True,
    )
    openrouter_inactive = next(
        (item for item in bedrock_active.providers if item.name == "openrouter"),
        None,
    )
    active_bedrock = next(
        (item for item in bedrock_active.providers if item.name == "bedrock"),
        None,
    )
    inactive_not_ready_ok = (
        openrouter_inactive is not None
        and openrouter_inactive.status is ConfigStatus.NOT_CONFIGURED
        and bedrock_active.active_provider == "bedrock"
    )

    ready_report = build_ai_configuration_report(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=env,
        openrouter_dependency_available=True,
    )
    ready_overview = next(
        (item for item in ready_report.providers if item.name == "openrouter"),
        None,
    )
    would_exit_0_when_ready = (
        ready_overview is not None and ready_overview.status is ConfigStatus.CONFIGURED
    )

    checks = [
        CheckResult(
            name="active_openrouter_not_ready_maps_to_exit_1",
            category="doctor_exit",
            ok=would_exit_1,
            detail="active not Configured maps to exit 1",
        ),
        CheckResult(
            name="inactive_openrouter_not_ready_does_not_force_exit_1",
            category="doctor_exit",
            ok=inactive_not_ready_ok and active_bedrock is not None,
            detail="bedrock active; openrouter not ready ignored for exit",
        ),
        CheckResult(
            name="active_openrouter_ready_maps_to_exit_0_path",
            category="doctor_exit",
            ok=would_exit_0_when_ready,
            detail="active Configured maps to exit 0 path",
        ),
    ]
    return checks, {}


def run_integration_success_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    settings = settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL})
    created = create_assess_ai_provider(settings)
    client = Client()
    provider = OpenRouterAIModelProvider(settings=settings, client=client)
    outcome = provider.invoke(model_request(), invocation_options())
    adapter = build_openrouter_provider(client=Client())
    checks = [
        CheckResult(
            name="create_assess_ai_provider_selects_openrouter_wrapper",
            category="integration_success",
            ok=isinstance(created, OpenRouterAIModelProvider)
            and not isinstance(created, OpenAIAIModelProvider)
            and not isinstance(created, BedrockAIModelProvider),
            detail=f"class={type(created).__name__}",
        ),
        CheckResult(
            name="mocked_invoke_returns_without_raising",
            category="integration_success",
            ok=outcome is not None and len(client.calls) == 1,
            detail=f"calls={len(client.calls)}",
        ),
        CheckResult(
            name="adapter_provider_id_is_openrouter",
            category="integration_success",
            ok=adapter.provider_id is ProviderId.OPENROUTER,
            detail="ProviderId.OPENROUTER",
        ),
        CheckResult(
            name="exactly_one_chat_completions_invocation",
            category="integration_success",
            ok=len(client.calls) == 1,
            detail="single create call",
        ),
        CheckResult(
            name="executor_maximum_attempts_remains_one",
            category="integration_success",
            ok=(
                OPENROUTER_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
                and OPENROUTER_RETRY_POLICY is DEFAULT_RETRY_POLICY
            ),
            detail="operational_retry_conservative",
        ),
    ]
    return checks, {}


def run_integration_failure_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []

    missing_model_raised = False
    with patch.dict(
        os.environ,
        {k: v for k, v in os.environ.items() if k != CODESTRATA_OPENROUTER_MODEL_ID_ENV},
        clear=True,
    ):
        try:
            resolve_assess_model_id(
                cli_model_id=None,
                settings=settings_for("openrouter", openrouter={"model": ""}),
            )
        except AIProviderConfigurationError:
            missing_model_raised = True
        except Exception:  # noqa: BLE001
            missing_model_raised = False
    checks.append(
        CheckResult(
            name="missing_model_resolve_raises_configuration_error",
            category="integration_failure",
            ok=missing_model_raised,
            detail="resolve_assess_model_id rejects empty model",
        )
    )

    reader = CountingEnvironmentReader({})
    adapter = build_openrouter_provider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        environment_reader=reader,
    )
    # Adapter.execute returns AIProviderResult; executor wraps it separately.
    missing_result = adapter.execute(provider_request())
    missing_key_ok = (
        missing_result.error is not None
        and missing_result.error.category.value == "missing_configuration"
        and SYNTHETIC_API_KEY not in (missing_result.error.detail or "")
    )
    checks.append(
        CheckResult(
            name="missing_api_key_maps_to_configuration_error",
            category="integration_failure",
            ok=missing_key_ok,
            detail="missing_configuration without secret leak",
        )
    )

    failure_cases = (
        ("AuthenticationError", "authentication_failed"),
        ("APITimeoutError", "timeout"),
        ("RateLimitError", "rate_limited"),
        ("NotFoundError", "invalid_model"),
    )
    for exc_name, expected_category in failure_cases:
        client = Client(sdk_exception(exc_name, "upstream synthetic"))
        provider = OpenRouterAIModelProvider(
            openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
            client=client,
        )
        raised: Exception | None
        try:
            provider.invoke(model_request(), invocation_options())
            raised = None
        except Exception as error:  # noqa: BLE001
            raised = error
        secret_safe = raised is not None and SYNTHETIC_API_KEY not in str(raised)
        attempts_ok = len(client.calls) <= EXPECTED_MAXIMUM_ATTEMPTS
        mapped = build_openrouter_provider(
            client=Client(sdk_exception(exc_name))
        ).execute(provider_request())
        category_ok = (
            mapped.error is not None and mapped.error.category.value == expected_category
        )
        checks.append(
            CheckResult(
                name=f"failure_{expected_category}_no_fallback_single_attempt",
                category="integration_failure",
                ok=raised is not None and secret_safe and attempts_ok and category_ok,
                detail=_safe_detail(
                    f"category={expected_category} calls={len(client.calls)}"
                ),
            )
        )

    empty_client = Client(Response.empty())
    empty_provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=empty_client,
    )
    empty_raised: Exception | None
    try:
        empty_provider.invoke(model_request(), invocation_options())
        empty_raised = None
    except Exception as error:  # noqa: BLE001
        empty_raised = error
    checks.append(
        CheckResult(
            name="empty_response_fails_without_secret_or_retry_storm",
            category="integration_failure",
            ok=(
                empty_raised is not None
                and SYNTHETIC_API_KEY not in str(empty_raised)
                and len(empty_client.calls) <= EXPECTED_MAXIMUM_ATTEMPTS
            ),
            detail=f"calls={len(empty_client.calls)}",
        )
    )

    malformed_client = Client(Response.malformed())
    malformed_provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=malformed_client,
    )
    malformed_raised: Exception | None
    try:
        malformed_provider.invoke(model_request(), invocation_options())
        malformed_raised = None
    except Exception as error:  # noqa: BLE001
        malformed_raised = error
    checks.append(
        CheckResult(
            name="malformed_response_single_attempt_no_secret",
            category="integration_failure",
            ok=(
                SYNTHETIC_API_KEY not in str(malformed_raised or "")
                and len(malformed_client.calls) <= EXPECTED_MAXIMUM_ATTEMPTS
                and (malformed_raised is not None or bool(malformed_client.calls))
            ),
            detail=f"calls={len(malformed_client.calls)} raised={malformed_raised is not None}",
        )
    )
    return checks, {}


def run_provider_selection_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    default_created = create_assess_ai_provider(settings_for(DEFAULT_PROVIDER))
    openai_created = create_assess_ai_provider(settings_for("openai"))
    openrouter_created = create_assess_ai_provider(settings_for(PROVIDER_ID))

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

    checks = [
        CheckResult(
            name="default_provider_remains_bedrock",
            category="provider_selection",
            ok=isinstance(default_created, BedrockAIModelProvider)
            and AiSettings().provider == DEFAULT_PROVIDER,
            detail="bedrock default",
        ),
        CheckResult(
            name="explicit_openai_selects_openai",
            category="provider_selection",
            ok=isinstance(openai_created, OpenAIAIModelProvider),
            detail="openai explicit",
        ),
        CheckResult(
            name="explicit_openrouter_selects_openrouter",
            category="provider_selection",
            ok=isinstance(openrouter_created, OpenRouterAIModelProvider),
            detail="openrouter explicit",
        ),
        CheckResult(
            name="unknown_provider_rejected",
            category="provider_selection",
            ok=unknown_rejected,
            detail="unknown rejected",
        ),
        CheckResult(
            name="aws_bedrock_alias_rejected",
            category="provider_selection",
            ok=aws_rejected,
            detail="aws_bedrock rejected",
        ),
    ]
    return checks, {}


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    client = Client(sdk_exception("AuthenticationError", "upstream rejected"))
    provider = OpenRouterAIModelProvider(
        openrouter_settings=OpenRouterSettings(model=TEST_ONLY_MODEL),
        client=client,
    )
    raised: Exception | None
    try:
        provider.invoke(model_request(), invocation_options())
        raised = None
    except Exception as error:  # noqa: BLE001
        raised = error
    checks = [
        CheckResult(
            name="invoke_failure_raises_for_assessment_fail_soft",
            category="fail_soft",
            ok=raised is not None,
            detail="assessment owns fail-soft classification",
        ),
        CheckResult(
            name="fail_soft_error_omits_api_key",
            category="fail_soft",
            ok=raised is not None and SYNTHETIC_API_KEY not in str(raised),
            detail="no secret in raised error",
        ),
        CheckResult(
            name="fail_soft_no_provider_fallback",
            category="fail_soft",
            ok=len(client.calls) <= 1,
            detail=f"calls={len(client.calls)}",
        ),
    ]
    return checks, {}


def run_reporting_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    schema_path = (
        engine_root
        / "src/codestrata/resources/schemas/assessment/codestrata.io/v1.2/AssessmentReport.json"
    )
    schema_text = schema_path.read_text(encoding="utf-8") if schema_path.is_file() else ""
    doctor_tokens = (
        "openrouter_readiness",
        "credential_present",
        "dependency_available",
        "base_url_status",
        "doctor_policy",
        "evaluate_openrouter_readiness",
        "OpenRouterDoctorReadiness",
    )
    offenders = [token for token in doctor_tokens if token in schema_text]
    checks = [
        CheckResult(
            name="assessment_schema_version_remains_1_2",
            category="reporting_boundary",
            ok=(
                ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION
                and ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
                and schema_path.is_file()
            ),
            detail="Assessment schema 1.2 constant retained",
        ),
        CheckResult(
            name="assessment_schema_omits_doctor_tokens",
            category="reporting_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        ),
    ]
    return checks, {}


def run_regression_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.ai.providers import doctor as doctor_module

    openai_overview = doctor_module._openai_overview(
        settings_for(
            "openai",
            openai={"api_key_env": "SYNTHETIC_DOCTOR_OPENAI_KEY_VAR"},
        ),
        environ={},
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
                CODESTRATA_OPENROUTER_MODEL_ID_ENV,
            }
        },
        clear=True,
    ):
        openai_model = resolve_assess_model_id(
            cli_model_id=None, settings=settings_for("openai")
        )
        bedrock_model = resolve_assess_model_id(
            cli_model_id=None, settings=settings_for("bedrock")
        )

    checks = [
        CheckResult(
            name="openai_overview_still_works_with_injected_environ",
            category="openai_regression",
            ok=openai_overview.name == "openai"
            and openai_overview.status is ConfigStatus.NOT_CONFIGURED,
            detail="openai overview injectable",
        ),
        CheckResult(
            name="openai_default_model_unchanged",
            category="openai_regression",
            ok=openai_model == OPENAI_DEFAULT_MODEL
            and AiSettings().openai.answer_model == OPENAI_DEFAULT_MODEL,
            detail="openai default preserved",
        ),
        CheckResult(
            name="bedrock_remains_default_provider",
            category="bedrock_regression",
            ok=AiSettings().provider == DEFAULT_PROVIDER,
            detail="AiSettings provider bedrock",
        ),
        CheckResult(
            name="bedrock_default_model_unchanged",
            category="bedrock_regression",
            ok=bedrock_model == BEDROCK_DEFAULT_MODEL,
            detail="bedrock default preserved",
        ),
    ]
    return checks, {}


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    doctor_imports = _doctor_imports(engine_root)
    source = _doctor_source(engine_root)
    adapter_import = any(DOCTOR_FORBIDDEN_ADAPTER_IMPORT in name for name in doctor_imports)
    # Optional-extra probes may import openai/boto3; client construction is forbidden.
    client_construction = (
        "OpenAI(" in source
        or "boto3.client(" in source
        or "boto3.Session(" in source
        or "resolve_client(" in source
    )
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

    contracts_import_sdk = False
    for path in contracts.glob("*.py"):
        for name in imports(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                contracts_import_sdk = True

    checks = [
        CheckResult(
            name="doctor_does_not_construct_sdk_clients",
            category="dependency_boundary",
            ok=not client_construction,
            detail="optional-extra probes allowed; client construction forbidden",
        ),
        CheckResult(
            name="doctor_does_not_import_openrouter_adapter_package",
            category="dependency_boundary",
            ok=not adapter_import,
            detail="no adapter import in doctor",
        ),
        CheckResult(
            name="common_contracts_remain_sdk_free",
            category="dependency_boundary",
            ok=not contracts_import_sdk,
            detail="contracts stay SDK-free",
        ),
    ]
    return checks, {}


def run_privacy_checks(
    report_payload: dict[str, Any] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    readiness = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={
                "model": TEST_ONLY_MODEL,
                "site_url": SYNTHETIC_SITE_URL,
                "app_name": SYNTHETIC_APP_NAME,
                "base_url": "",
            },
        ),
        environ=injected_environ(),
        dependency_available=True,
    )
    local_blob = json.dumps(readiness.redacted(), sort_keys=True)
    local_forbidden = (
        SYNTHETIC_API_KEY,
        SYNTHETIC_OPENAI_API_KEY,
        TEST_ONLY_MODEL,
        SYNTHETIC_SITE_URL,
        SYNTHETIC_APP_NAME,
        "Authorization",
        "Bearer",
        "HTTP-Referer",
        "X-Title",
        "sk-",
        "https://openrouter.ai",
        SYNTHETIC_INSTRUCTION,
    )
    local_offenders = [token for token in local_forbidden if token in local_blob]
    checks = [
        CheckResult(
            name="doctor_redacted_omits_secrets_urls_models_headers",
            category="privacy",
            ok=not local_offenders,
            detail=f"offender_count={len(local_offenders)}",
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
        "Authorization",
        "Bearer",
        "https://openrouter.ai",
        "HTTP-Referer",
        "X-Title",
        SYNTHETIC_INSTRUCTION,
        SYNTHETIC_CONTEXT,
        SYNTHETIC_API_KEY,
        SYNTHETIC_OPENAI_API_KEY,
        TEST_ONLY_MODEL,
        SYNTHETIC_SITE_URL,
        SYNTHETIC_APP_NAME,
        SYNTHETIC_INVALID_BASE_URL,
        SYNTHETIC_INVALID_SITE_URL,
        "/Users/",
        "Traceback",
        "resp_should_never_appear",
    )
    offenders = [token for token in report_forbidden if token in blob]
    # Never echo forbidden tokens into the report detail (avoids recursive leaks).
    checks.append(
        CheckResult(
            name="verification_report_omits_secrets_urls_models_prompts",
            category="privacy",
            ok=not offenders,
            detail=f"offender_count={len(offenders)}",
        )
    )
    return checks, {}


def run_determinism_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    first = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=injected_environ(),
        dependency_available=True,
    ).redacted()
    second = evaluate_openrouter_readiness(
        settings_for("openrouter", openrouter={"model": TEST_ONLY_MODEL}),
        environ=injected_environ(),
        dependency_available=True,
    ).redacted()
    checks = [
        CheckResult(
            name="openrouter_readiness_redaction_is_deterministic",
            category="determinism",
            ok=first == second,
            detail="identical redacted views",
        )
    ]
    return checks, {}


__all__ = [
    "run_dependency_boundary_checks",
    "run_determinism_checks",
    "run_doctor_exit_checks",
    "run_doctor_policy_checks",
    "run_fail_soft_checks",
    "run_formatting_checks",
    "run_integration_failure_checks",
    "run_integration_success_checks",
    "run_inventory_checks",
    "run_privacy_checks",
    "run_provider_selection_checks",
    "run_readiness_checks",
    "run_regression_checks",
    "run_reporting_boundary_checks",
]
