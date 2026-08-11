"""Core SV.11.12 checks: privacy, isolation, and architecture boundaries."""

from __future__ import annotations

import ast
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

from codestrata.ai.provider_adapters.bedrock import diagnostics as bedrock_diagnostics
from codestrata.ai.provider_adapters.bedrock.factory import (
    BEDROCK_RETRY_POLICY,
    build_bedrock_executor,
    build_bedrock_provider,
)
from codestrata.ai.provider_adapters.openai import diagnostics as openai_diagnostics
from codestrata.ai.provider_adapters.openai.factory import (
    OPENAI_RETRY_POLICY,
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_adapters.openrouter import diagnostics as openrouter_diagnostics
from codestrata.ai.provider_adapters.openrouter.factory import (
    OPENROUTER_RETRY_POLICY,
    build_openrouter_executor,
    build_openrouter_provider,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.registry import AIProviderRegistry
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY

# Import factory before assess_ai to keep load order stable.
from codestrata.ai.providers.factory import (  # noqa: I001
    create_assess_ai_provider,
    supported_assess_ai_providers,
)
from codestrata.ai.providers.doctor import (
    build_ai_configuration_report,
    evaluate_openrouter_readiness,
)
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.config.settings import AiSettings, OpenAISettings, OpenRouterSettings
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.modernization_models import AIExecutionStatus
from codestrata.telemetry.analytics.ai_analytics_catalogs import APPROVED_AI_PROVIDER_FAMILIES
from codestrata.telemetry.analytics.ai_analytics_projection import APPROVED_AI_ANALYTICS_FIELD_NAMES
from verification.ai_provider_privacy_boundaries.contract import (
    ALLOWED_ADAPTER_DIAGNOSTIC_KEYS,
    ALLOWED_EXECUTION_DIAGNOSTIC_KEYS,
    ALLOWED_RESULT_DIAGNOSTIC_KEYS,
    ASSESSMENT_SCHEMA_VERSION,
    ASSESS_REGISTERED_PROVIDERS,
    AI_EXECUTION_STATUS_VALUES,
    BEDROCK_DEFAULT_MODEL,
    CLI_FORBIDDEN_FLAG_TOKENS,
    DEFAULT_PROVIDER,
    DOCTOR_FORBIDDEN_CALL_TOKENS,
    EXPECTED_MAXIMUM_ATTEMPTS,
    FORBIDDEN_IMPORT_PREFIXES,
    OPENAI_DEFAULT_MODEL,
    PROVIDERS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.ai_provider_privacy_boundaries.fixtures import (
    ALL_FORBIDDEN_MARKERS,
    BedrockClient,
    OpenAIStyleClient,
    OpenAIStyleResponse,
    SYNTHETIC_APP_NAME,
    SYNTHETIC_AWS_ACCESS,
    SYNTHETIC_AWS_SECRET,
    SYNTHETIC_BASE_URL,
    SYNTHETIC_CONTEXT,
    SYNTHETIC_ENRICHMENT_RESPONSE,
    SYNTHETIC_EXCEPTION,
    SYNTHETIC_MODEL_BEDROCK,
    SYNTHETIC_MODEL_OPENAI,
    SYNTHETIC_MODEL_OPENROUTER,
    SYNTHETIC_OPENAI_KEY,
    SYNTHETIC_OPENROUTER_KEY,
    SYNTHETIC_PATH,
    SYNTHETIC_PROFILE,
    SYNTHETIC_PROMPT,
    SYNTHETIC_REGION,
    SYNTHETIC_REQUEST_ID,
    SYNTHETIC_RESPONSE,
    SYNTHETIC_SESSION,
    SYNTHETIC_SITE_URL,
    bedrock_client_error,
    canonical_json,
    leaked_markers,
    openai_settings_secret,
    openrouter_settings_secret,
    provider_request,
    sdk_exception,
    settings_for,
    synthetic_bedrock_probe,
)
from verification.ai_provider_privacy_boundaries.models import CheckResult

_REPO_ROOT_FROM_ENGINE = 2
_DOCTOR_REL = "src/codestrata/ai/providers/doctor.py"
_ADAPTER_PACKAGES = (
    "src/codestrata/ai/provider_adapters/bedrock",
    "src/codestrata/ai/provider_adapters/openai",
    "src/codestrata/ai/provider_adapters/openrouter",
)
_WRAPPER_FILES = (
    "src/codestrata/ai/providers/bedrock.py",
    "src/codestrata/ai/providers/openai_provider.py",
    "src/codestrata/ai/providers/openrouter_provider.py",
)
_CONTRACTS_PKG = "src/codestrata/ai/provider_contracts"
_EXECUTOR_REL = "src/codestrata/ai/provider_contracts/executor.py"


def _safe_detail(value: str) -> str:
    cleaned = value
    for token in ALL_FORBIDDEN_MARKERS:
        if token and token in cleaned:
            cleaned = cleaned.replace(token, "<redacted>")
    return cleaned[:240]


def _collect_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _imports_forbidden(names: set[str], prefixes: tuple[str, ...] = FORBIDDEN_IMPORT_PREFIXES) -> list[str]:
    offenders: list[str] = []
    for name in names:
        for prefix in prefixes:
            if name == prefix or name.startswith(prefix + "."):
                offenders.append(name)
    return sorted(set(offenders))


def _openai_adapter() -> Any:
    return build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )


def _openrouter_adapter() -> Any:
    return build_openrouter_provider(
        openrouter_settings=openrouter_settings_secret(),
        client=OpenAIStyleClient(),
        environment_reader=lambda _name: SYNTHETIC_OPENROUTER_KEY,
        api_key_present=True,
    )


def _bedrock_adapter() -> Any:
    return build_bedrock_provider(
        settings=settings_for(
            "bedrock",
            bedrock={"model_id": SYNTHETIC_MODEL_BEDROCK, "region": SYNTHETIC_REGION},
        ),
        profile_name=SYNTHETIC_PROFILE,
        region_name=SYNTHETIC_REGION,
        client=BedrockClient(),
    )


def _adapters() -> dict[str, Any]:
    return {
        "openai": _openai_adapter(),
        "openrouter": _openrouter_adapter(),
        "bedrock": _bedrock_adapter(),
    }


def _diag_module(provider: str) -> Any:
    return {
        "openai": openai_diagnostics,
        "openrouter": openrouter_diagnostics,
        "bedrock": bedrock_diagnostics,
    }[provider]


def _model_for(provider: str) -> str:
    return {
        "openai": SYNTHETIC_MODEL_OPENAI,
        "openrouter": SYNTHETIC_MODEL_OPENROUTER,
        "bedrock": SYNTHETIC_MODEL_BEDROCK,
    }[provider]


# ---------------------------------------------------------------------------
# Inventory / matrix / registry
# ---------------------------------------------------------------------------


def run_inventory_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    package = engine_root / "verification/ai_provider_privacy_boundaries"
    required = (
        "__init__.py",
        "__main__.py",
        "contract.py",
        "models.py",
        "checks.py",
        "fixtures.py",
        "runner.py",
        "reporting.py",
        "scenarios.py",
        "README.md",
    )
    missing = [name for name in required if not (package / name).exists()]
    registered = tuple(sorted(supported_assess_ai_providers()))
    checks = [
        CheckResult(
            name="verification_package_layout_complete",
            category="inventory",
            ok=not missing,
            detail=f"missing={missing}",
        ),
        CheckResult(
            name="canonical_providers_registered",
            category="inventory",
            ok=registered == tuple(sorted(ASSESS_REGISTERED_PROVIDERS)),
            detail=f"registered={list(registered)}",
        ),
        CheckResult(
            name="compatibility_requirement_ids_present",
            category="inventory",
            ok=REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
            == ("CR-1", "CR-2", "CR-3", "CR-4", "CR-5", "CR-6"),
            detail="CR-1..CR-6 pinned",
        ),
    ]
    return checks, {"providers": list(PROVIDERS)}


def run_provider_matrix_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    matrix: dict[str, Any] = {}
    checks: list[CheckResult] = []
    for provider_id in PROVIDERS:
        settings = settings_for(provider_id)
        created = create_assess_ai_provider(settings)
        class_name = type(created).__name__
        matrix[provider_id] = {"class": class_name, "selected": provider_id}
        checks.append(
            CheckResult(
                name=f"matrix_selects_{provider_id}",
                category="provider_matrix",
                ok=provider_id in class_name.lower() or class_name.lower().startswith(provider_id),
                detail=f"class={class_name}",
            )
        )

    default = create_assess_ai_provider(settings_for(DEFAULT_PROVIDER))
    unknown_rejected = False
    try:
        create_assess_ai_provider(settings_for("not-a-provider"))
    except AIProviderConfigurationError:
        unknown_rejected = True
    except Exception:  # noqa: BLE001
        unknown_rejected = False

    checks.extend(
        [
            CheckResult(
                name="default_provider_is_bedrock",
                category="provider_matrix",
                ok=AiSettings().provider == DEFAULT_PROVIDER,
                detail=f"default={AiSettings().provider}",
            ),
            CheckResult(
                name="explicit_default_creates_bedrock_wrapper",
                category="provider_matrix",
                ok="bedrock" in type(default).__name__.lower(),
                detail=f"class={type(default).__name__}",
            ),
            CheckResult(
                name="unknown_provider_rejected",
                category="provider_matrix",
                ok=unknown_rejected,
                detail="unknown rejected",
            ),
        ]
    )
    return checks, matrix


def run_registry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    common = AIProviderRegistry()
    registered = tuple(sorted(supported_assess_ai_providers()))
    checks = [
        CheckResult(
            name="registry_decision_b_retained",
            category="registry",
            ok=REGISTRY_DECISION == "B"
            and REGISTRY_DECISION_LABEL == "compatibility_registry_retained",
            detail=f"decision={REGISTRY_DECISION}",
        ),
        CheckResult(
            name="assess_registry_lists_three_providers",
            category="registry",
            ok=registered == tuple(sorted(ASSESS_REGISTERED_PROVIDERS)),
            detail=f"registered={list(registered)}",
        ),
        CheckResult(
            name="common_ai_provider_registry_unwired",
            category="registry",
            ok=len(common.list_provider_ids()) == 0,
            detail=f"common_count={len(common.list_provider_ids())}",
        ),
        CheckResult(
            name="no_aws_bedrock_assess_provider_id",
            category="registry",
            ok="aws_bedrock" not in registered,
            detail="analytics family not used as assess id",
        ),
        CheckResult(
            name="ai_settings_default_provider_bedrock",
            category="registry",
            ok=AiSettings().provider == "bedrock",
            detail=f"provider={AiSettings().provider}",
        ),
    ]
    return checks, {}


# ---------------------------------------------------------------------------
# Credential / prompt / response / model / error privacy
# ---------------------------------------------------------------------------


def run_credential_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    credential_markers = (
        SYNTHETIC_OPENAI_KEY,
        SYNTHETIC_OPENROUTER_KEY,
        SYNTHETIC_AWS_ACCESS,
        SYNTHETIC_AWS_SECRET,
        SYNTHETIC_SESSION,
        SYNTHETIC_BASE_URL,
        SYNTHETIC_SITE_URL,
        SYNTHETIC_APP_NAME,
        SYNTHETIC_PROFILE,
        SYNTHETIC_REGION,
    )
    for provider_id, adapter in _adapters().items():
        diag = _diag_module(provider_id).diagnostic_view_of_adapter(adapter)
        blob = canonical_json(diag)
        leaked = leaked_markers(blob, credential_markers)
        redacted = adapter.configuration.redacted()
        redacted_blob = canonical_json(redacted)
        redacted_leaked = leaked_markers(redacted_blob, credential_markers)
        checks.append(
            CheckResult(
                name=f"{provider_id}_adapter_diagnostics_omit_credentials",
                category="credential_privacy",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
        checks.append(
            CheckResult(
                name=f"{provider_id}_redacted_config_omits_credentials",
                category="credential_privacy",
                ok=not redacted_leaked,
                detail=_safe_detail(f"leaked={redacted_leaked}"),
            )
        )

    env = {
        "OPENROUTER_API_KEY": SYNTHETIC_OPENROUTER_KEY,
        "OPENAI_API_KEY": SYNTHETIC_OPENAI_KEY,
        "AWS_ACCESS_KEY_ID": SYNTHETIC_AWS_ACCESS,
        "AWS_SECRET_ACCESS_KEY": SYNTHETIC_AWS_SECRET,
        "AWS_SESSION_TOKEN": SYNTHETIC_SESSION,
    }
    ready = evaluate_openrouter_readiness(
        settings_for(
            "openrouter",
            openrouter={
                "model": SYNTHETIC_MODEL_OPENROUTER,
                "site_url": SYNTHETIC_SITE_URL,
                "app_name": SYNTHETIC_APP_NAME,
                "base_url": SYNTHETIC_BASE_URL,
            },
        ),
        environ=env,
        dependency_available=True,
    )
    doctor_blob = canonical_json(ready.redacted())
    doctor_leaked = leaked_markers(doctor_blob, credential_markers)
    checks.append(
        CheckResult(
            name="doctor_openrouter_redacted_omits_credentials",
            category="credential_privacy",
            ok=not doctor_leaked,
            detail=_safe_detail(f"leaked={doctor_leaked}"),
        )
    )
    return checks, {}


def run_request_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    """Prompt privacy: public diagnostics must omit synthetic prompt markers."""

    checks: list[CheckResult] = []
    markers = (SYNTHETIC_PROMPT, SYNTHETIC_CONTEXT)
    for provider_id, adapter in _adapters().items():
        request = provider_request(model_id=_model_for(provider_id))
        result = adapter.execute(request)
        view = _diag_module(provider_id).diagnostic_view_of_provider_result(result)
        leaked = leaked_markers(canonical_json(view), markers)
        checks.append(
            CheckResult(
                name=f"{provider_id}_result_diagnostics_omit_prompt",
                category="prompt_privacy",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
        # Private request may contain the marker — that is expected and not a defect.
        private_ok = SYNTHETIC_PROMPT in request.payload.instruction_text
        checks.append(
            CheckResult(
                name=f"{provider_id}_private_request_may_carry_prompt",
                category="prompt_privacy",
                ok=private_ok,
                detail="private request retains prompt (not public)",
            )
        )
    return checks, {}


def run_response_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    markers = (SYNTHETIC_RESPONSE, SYNTHETIC_REQUEST_ID, SYNTHETIC_ENRICHMENT_RESPONSE)
    for provider_id, adapter in _adapters().items():
        result = adapter.execute(provider_request(model_id=_model_for(provider_id)))
        view = _diag_module(provider_id).diagnostic_view_of_provider_result(result)
        leaked = leaked_markers(canonical_json(view), markers)
        checks.append(
            CheckResult(
                name=f"{provider_id}_result_diagnostics_omit_response",
                category="response_privacy",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
    return checks, {}


def run_model_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    models = (
        SYNTHETIC_MODEL_OPENAI,
        SYNTHETIC_MODEL_BEDROCK,
        SYNTHETIC_MODEL_OPENROUTER,
    )
    for provider_id, adapter in _adapters().items():
        view = _diag_module(provider_id).diagnostic_view_of_adapter(adapter)
        leaked = leaked_markers(canonical_json(view), models)
        checks.append(
            CheckResult(
                name=f"{provider_id}_adapter_diagnostics_omit_model_value",
                category="model_privacy",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
    exact_model_fields = {
        name
        for name in APPROVED_AI_ANALYTICS_FIELD_NAMES
        if name in {"model", "model_id", "exact_model", "answer_model"}
    }
    checks.append(
        CheckResult(
            name="ai_analytics_has_no_exact_model_field",
            category="model_privacy",
            ok=not exact_model_fields,
            detail=f"exact_fields={sorted(exact_model_fields)}",
        )
    )
    return checks, {}


def run_error_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    markers = (
        SYNTHETIC_EXCEPTION,
        SYNTHETIC_OPENAI_KEY,
        SYNTHETIC_PROMPT,
        SYNTHETIC_PATH,
        SYNTHETIC_REQUEST_ID,
        "Traceback",
    )
    openai_cases = (
        ("AuthenticationError", ErrorCategory.AUTHENTICATION_FAILED),
        ("PermissionDeniedError", ErrorCategory.AUTHORIZATION_FAILED),
        ("NotFoundError", ErrorCategory.INVALID_MODEL),
        ("APITimeoutError", ErrorCategory.TIMEOUT),
        ("RateLimitError", ErrorCategory.RATE_LIMITED),
        ("APIConnectionError", ErrorCategory.PROVIDER_UNAVAILABLE),
        ("BadRequestError", ErrorCategory.INVALID_REQUEST),
    )
    for class_name, expected in openai_cases:
        adapter = build_openai_provider(
            openai_settings=openai_settings_secret(),
            client=OpenAIStyleClient(sdk_exception(class_name)),
            environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
        )
        result = adapter.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
        view = openai_diagnostics.diagnostic_view_of_provider_result(result)
        leaked = leaked_markers(canonical_json(view), markers)
        category_ok = (
            result.error is not None and result.error.category is expected
        )
        checks.append(
            CheckResult(
                name=f"openai_error_{class_name}_diagnostics_clean",
                category="error_privacy",
                ok=not leaked and category_ok,
                detail=_safe_detail(
                    f"leaked={leaked} category={getattr(result.error, 'category', None)}"
                ),
            )
        )

    bedrock_cases = (
        ("UnrecognizedClientException", ErrorCategory.AUTHENTICATION_FAILED),
        ("AccessDeniedException", ErrorCategory.AUTHORIZATION_FAILED),
        ("ThrottlingException", ErrorCategory.RATE_LIMITED),
        ("ValidationException", ErrorCategory.INVALID_REQUEST),
        ("ModelNotReadyException", ErrorCategory.PROVIDER_UNAVAILABLE),
    )
    for code, expected in bedrock_cases:
        adapter = build_bedrock_provider(
            profile_name=SYNTHETIC_PROFILE,
            region_name=SYNTHETIC_REGION,
            client=BedrockClient(bedrock_client_error(code)),
        )
        result = adapter.execute(provider_request(model_id=SYNTHETIC_MODEL_BEDROCK))
        view = bedrock_diagnostics.diagnostic_view_of_provider_result(result)
        leaked = leaked_markers(canonical_json(view), markers)
        category_ok = result.error is not None and result.error.category is expected
        checks.append(
            CheckResult(
                name=f"bedrock_error_{code}_diagnostics_clean",
                category="error_privacy",
                ok=not leaked and category_ok,
                detail=_safe_detail(
                    f"leaked={leaked} category={getattr(result.error, 'category', None)}"
                ),
            )
        )

    openrouter_adapter = build_openrouter_provider(
        openrouter_settings=openrouter_settings_secret(),
        client=OpenAIStyleClient(sdk_exception("AuthenticationError")),
        environment_reader=lambda _name: SYNTHETIC_OPENROUTER_KEY,
        api_key_present=True,
    )
    or_result = openrouter_adapter.execute(
        provider_request(model_id=SYNTHETIC_MODEL_OPENROUTER)
    )
    or_view = openrouter_diagnostics.diagnostic_view_of_provider_result(or_result)
    or_leaked = leaked_markers(canonical_json(or_view), markers)
    checks.append(
        CheckResult(
            name="openrouter_auth_error_diagnostics_clean",
            category="error_privacy",
            ok=not or_leaked,
            detail=_safe_detail(f"leaked={or_leaked}"),
        )
    )
    return checks, {}


# ---------------------------------------------------------------------------
# Diagnostics allowlist / logging / configuration / execution / retries
# ---------------------------------------------------------------------------


def run_diagnostics_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    for provider_id, adapter in _adapters().items():
        module = _diag_module(provider_id)
        adapter_view = module.diagnostic_view_of_adapter(adapter)
        extra = sorted(set(adapter_view) - ALLOWED_ADAPTER_DIAGNOSTIC_KEYS)
        checks.append(
            CheckResult(
                name=f"{provider_id}_adapter_diag_keys_allowlisted",
                category="diagnostics",
                ok=not extra,
                detail=f"extra={extra}",
            )
        )
        result = adapter.execute(provider_request(model_id=_model_for(provider_id)))
        result_view = module.diagnostic_view_of_provider_result(result)
        result_extra = sorted(set(result_view) - ALLOWED_RESULT_DIAGNOSTIC_KEYS)
        checks.append(
            CheckResult(
                name=f"{provider_id}_result_diag_keys_allowlisted",
                category="diagnostics",
                ok=not result_extra,
                detail=f"extra={result_extra}",
            )
        )
        executor = {
            "openai": build_openai_executor,
            "openrouter": build_openrouter_executor,
            "bedrock": build_bedrock_executor,
        }[provider_id](adapter)
        execution = executor.execute(provider_request(model_id=_model_for(provider_id)))
        exec_view = module.diagnostic_view_of_execution(execution)
        exec_extra = sorted(set(exec_view) - ALLOWED_EXECUTION_DIAGNOSTIC_KEYS)
        checks.append(
            CheckResult(
                name=f"{provider_id}_execution_diag_keys_allowlisted",
                category="diagnostics",
                ok=not exec_extra,
                detail=f"extra={exec_extra}",
            )
        )
    return checks, {}


def run_logging_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    # Source scan: no logger formatting of obvious secret/payload keywords in adapters.
    payload_patterns = (
        re.compile(r"logger\.(info|debug|warning)\([^)]*api_key", re.I),
        re.compile(r"logger\.(info|debug|warning)\([^)]*Authorization", re.I),
        re.compile(r"logger\.(info|debug|warning)\([^)]*prompt", re.I),
        re.compile(r"logger\.(info|debug|warning)\([^)]*response_body", re.I),
    )
    source_hits: list[str] = []
    for rel in (*_ADAPTER_PACKAGES, *_WRAPPER_FILES, _DOCTOR_REL, _EXECUTOR_REL):
        path = engine_root / rel
        for file_path in _collect_py_files(path):
            text = file_path.read_text(encoding="utf-8")
            for pattern in payload_patterns:
                if pattern.search(text):
                    source_hits.append(str(file_path.relative_to(engine_root)))
    checks.append(
        CheckResult(
            name="no_new_payload_secret_logging_in_provider_sources",
            category="logging",
            ok=not source_hits,
            detail=f"hits={sorted(set(source_hits))}",
        )
    )

    # Capture logs during adapter invoke — credentials/prompts/responses must not appear.
    # Known: Bedrock wrapper logs profile/region; OpenAI wrapper logs model_id.
    # Those are accepted log-not-report behaviors; scan for credential/content markers only.
    content_markers = (
        SYNTHETIC_OPENAI_KEY,
        SYNTHETIC_OPENROUTER_KEY,
        SYNTHETIC_AWS_ACCESS,
        SYNTHETIC_AWS_SECRET,
        SYNTHETIC_SESSION,
        SYNTHETIC_PROMPT,
        SYNTHETIC_RESPONSE,
        SYNTHETIC_EXCEPTION,
    )
    for provider_id, adapter in _adapters().items():
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        loggers = [
            logging.getLogger("codestrata.ai.providers.bedrock"),
            logging.getLogger("codestrata.ai.providers.openai_provider"),
            logging.getLogger("codestrata.ai.providers.openrouter_provider"),
            logging.getLogger("codestrata.ai.provider_adapters.bedrock"),
            logging.getLogger("codestrata.ai.provider_adapters.openai"),
            logging.getLogger("codestrata.ai.provider_adapters.openrouter"),
        ]
        for logger in loggers:
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        try:
            adapter.execute(provider_request(model_id=_model_for(provider_id)))
        finally:
            for logger in loggers:
                logger.removeHandler(handler)
        leaked = leaked_markers(stream.getvalue(), content_markers)
        checks.append(
            CheckResult(
                name=f"{provider_id}_invoke_logs_omit_secrets_and_content",
                category="logging",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
    return checks, {}


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    openai_fields = set(OpenAISettings.model_fields)
    openrouter_fields = set(OpenRouterSettings.model_fields)
    checks.append(
        CheckResult(
            name="openai_settings_has_no_plaintext_api_key_field",
            category="configuration_boundary",
            ok="api_key" not in openai_fields,
            detail=f"fields={sorted(openai_fields)}",
        )
    )
    checks.append(
        CheckResult(
            name="openrouter_settings_has_no_plaintext_api_key_field",
            category="configuration_boundary",
            ok="api_key" not in openrouter_fields,
            detail=f"fields={sorted(openrouter_fields)}",
        )
    )
    for provider_id, adapter in _adapters().items():
        redacted = adapter.configuration.redacted()
        leaked = leaked_markers(canonical_json(redacted))
        checks.append(
            CheckResult(
                name=f"{provider_id}_configuration_redacted_omits_markers",
                category="configuration_boundary",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
    return checks, {}


def run_configuration_path_write_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    hits: list[str] = []
    for rel in _ADAPTER_PACKAGES:
        for path in _collect_py_files(engine_root / rel):
            text = path.read_text(encoding="utf-8")
            if "Path.write" in text or ".write_text(" in text or ".write_bytes(" in text:
                hits.append(str(path.relative_to(engine_root)))
    return [
        CheckResult(
            name="provider_adapters_do_not_write_paths",
            category="configuration_boundary",
            ok=not hits,
            detail=f"hits={hits}",
        )
    ], {}


def run_execution_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    executor_source = (engine_root / _EXECUTOR_REL).read_text(encoding="utf-8")
    # Docstrings may mention os.environ; inspect AST for real attribute loads.
    tree = ast.parse(executor_source, filename="executor.py")
    reads_environ = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                reads_environ = True
        if isinstance(node, ast.Attribute) and node.attr == "getenv":
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                reads_environ = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getenv":
            reads_environ = True
    checks = [
        CheckResult(
            name="default_retry_policy_maximum_attempts_is_one",
            category="execution_boundary",
            ok=DEFAULT_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
            detail=f"maximum_attempts={DEFAULT_RETRY_POLICY.maximum_attempts}",
        ),
        CheckResult(
            name="openai_retry_policy_pinned_to_default",
            category="execution_boundary",
            ok=OPENAI_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
            detail=f"maximum_attempts={OPENAI_RETRY_POLICY.maximum_attempts}",
        ),
        CheckResult(
            name="bedrock_retry_policy_pinned_to_default",
            category="execution_boundary",
            ok=BEDROCK_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
            detail=f"maximum_attempts={BEDROCK_RETRY_POLICY.maximum_attempts}",
        ),
        CheckResult(
            name="openrouter_retry_policy_pinned_to_default",
            category="execution_boundary",
            ok=OPENROUTER_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS,
            detail=f"maximum_attempts={OPENROUTER_RETRY_POLICY.maximum_attempts}",
        ),
        CheckResult(
            name="executor_module_does_not_read_environ",
            category="execution_boundary",
            ok=not reads_environ,
            detail="executor stays environ-free",
        ),
    ]

    from tests.ai.provider_contracts.execution_fakes import FakeRaisingProvider

    class _KeyboardProvider(FakeRaisingProvider):
        def execute(self, request: Any) -> Any:  # type: ignore[override]
            raise KeyboardInterrupt()

    class _SystemExitProvider(FakeRaisingProvider):
        def execute(self, request: Any) -> Any:  # type: ignore[override]
            raise SystemExit(2)

    request = provider_request(model_id="interrupt-test-model")
    kb_raised = False
    try:
        AIProviderExecutor(_KeyboardProvider()).execute(request)
    except KeyboardInterrupt:
        kb_raised = True
    se_raised = False
    try:
        AIProviderExecutor(_SystemExitProvider()).execute(request)
    except SystemExit:
        se_raised = True
    checks.append(
        CheckResult(
            name="keyboard_interrupt_propagates",
            category="execution_boundary",
            ok=kb_raised,
            detail="KeyboardInterrupt preserved",
        )
    )
    checks.append(
        CheckResult(
            name="system_exit_propagates",
            category="execution_boundary",
            ok=se_raised,
            detail="SystemExit preserved",
        )
    )
    return checks, {}


def run_retry_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    non_retryable = (
        ErrorCategory.MISSING_CONFIGURATION,
        ErrorCategory.AUTHENTICATION_FAILED,
        ErrorCategory.AUTHORIZATION_FAILED,
        ErrorCategory.INVALID_MODEL,
        ErrorCategory.INVALID_REQUEST,
        ErrorCategory.INVALID_RESPONSE,
        ErrorCategory.PARSING_FAILED,
    )
    checks: list[CheckResult] = []
    for category in non_retryable:
        checks.append(
            CheckResult(
                name=f"default_policy_does_not_retry_{category.value}",
                category="retry_safety",
                ok=not DEFAULT_RETRY_POLICY.is_retryable(category),
                detail=f"retryable={DEFAULT_RETRY_POLICY.is_retryable(category)}",
            )
        )

    # Auth failure under default policy: single attempt.
    adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(sdk_exception("AuthenticationError")),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    client = adapter._client  # noqa: SLF001 - injected client for call counting
    executor = build_openai_executor(adapter)
    result = executor.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
    call_count = len(client.calls) if client is not None else -1
    checks.append(
        CheckResult(
            name="auth_failure_attempts_never_exceed_one",
            category="retry_safety",
            ok=result.attempts == 1 and call_count == 1,
            detail=f"attempts={result.attempts} calls={call_count}",
        )
    )

    invalid_model_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(sdk_exception("NotFoundError")),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    invalid_client = invalid_model_adapter._client  # noqa: SLF001
    invalid_exec = build_openai_executor(invalid_model_adapter)
    invalid_result = invalid_exec.execute(provider_request(model_id=SYNTHETIC_MODEL_OPENAI))
    checks.append(
        CheckResult(
            name="invalid_model_not_retried",
            category="retry_safety",
            ok=invalid_result.attempts == 1 and len(invalid_client.calls) == 1,
            detail=f"attempts={invalid_result.attempts}",
        )
    )

    malformed_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        client=OpenAIStyleClient(OpenAIStyleResponse.malformed()),
        environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
    )
    malformed_client = malformed_adapter._client  # noqa: SLF001
    malformed_exec = build_openai_executor(malformed_adapter)
    malformed_result = malformed_exec.execute(
        provider_request(model_id=SYNTHETIC_MODEL_OPENAI)
    )
    checks.append(
        CheckResult(
            name="malformed_response_not_retried_beyond_one",
            category="retry_safety",
            ok=malformed_result.attempts == 1 and len(malformed_client.calls) == 1,
            detail=f"attempts={malformed_result.attempts}",
        )
    )
    return checks, {}


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


def run_failure_isolation_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks: list[CheckResult] = []
    cases: list[tuple[str, Any, str]] = [
        ("openai", OpenAIStyleClient(), "success"),
        (
            "openai",
            OpenAIStyleClient(sdk_exception("AuthenticationError")),
            "auth_error",
        ),
        (
            "openai",
            OpenAIStyleClient(sdk_exception("APITimeoutError")),
            "timeout",
        ),
        ("openai", OpenAIStyleClient(OpenAIStyleResponse.empty()), "empty_response"),
        ("openrouter", OpenAIStyleClient(), "success"),
        (
            "openrouter",
            OpenAIStyleClient(sdk_exception("AuthenticationError")),
            "auth_error",
        ),
        ("bedrock", BedrockClient(), "success"),
        (
            "bedrock",
            BedrockClient(bedrock_client_error("UnrecognizedClientException")),
            "auth_error",
        ),
        (
            "bedrock",
            BedrockClient(bedrock_client_error("ModelTimeoutException")),
            "timeout",
        ),
    ]
    for provider_id, client, case_name in cases:
        if provider_id == "openai":
            adapter = build_openai_provider(
                openai_settings=openai_settings_secret(),
                client=client,
                environment_reader=lambda _name: SYNTHETIC_OPENAI_KEY,
            )
        elif provider_id == "openrouter":
            adapter = build_openrouter_provider(
                openrouter_settings=openrouter_settings_secret(),
                client=client,
                environment_reader=lambda _name: SYNTHETIC_OPENROUTER_KEY,
                api_key_present=True,
            )
        else:
            adapter = build_bedrock_provider(
                profile_name=SYNTHETIC_PROFILE,
                region_name=SYNTHETIC_REGION,
                client=client,
            )
        result = adapter.execute(provider_request(model_id=_model_for(provider_id)))
        call_count = len(client.calls)
        rendered = canonical_json(
            {
                "provider_id": str(result.provider_id),
                "status": str(result.status),
                "error": str(result.error) if result.error else None,
            }
        )
        leaked = leaked_markers(rendered)
        checks.append(
            CheckResult(
                name=f"isolation_{provider_id}_{case_name}_single_invoke",
                category="failure_isolation",
                ok=call_count == 1,
                detail=f"calls={call_count}",
            )
        )
        checks.append(
            CheckResult(
                name=f"isolation_{provider_id}_{case_name}_provider_id",
                category="failure_isolation",
                ok=str(result.provider_id) == provider_id,
                detail=f"provider_id={result.provider_id}",
            )
        )
        checks.append(
            CheckResult(
                name=f"isolation_{provider_id}_{case_name}_no_secret_in_result_str",
                category="failure_isolation",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )

    # Missing key via environ: OpenAI fails without fallback.
    missing_key_adapter = build_openai_provider(
        openai_settings=openai_settings_secret(),
        environment_reader=lambda _name: None,
    )
    missing_result = missing_key_adapter.execute(
        provider_request(model_id=SYNTHETIC_MODEL_OPENAI)
    )
    checks.append(
        CheckResult(
            name="isolation_openai_missing_key_no_fallback",
            category="failure_isolation",
            ok=str(missing_result.provider_id) == "openai"
            and missing_result.error is not None,
            detail=f"provider_id={missing_result.provider_id}",
        )
    )

    # Cross-provider: selecting openrouter never yields openai wrapper.
    created = create_assess_ai_provider(settings_for("openrouter"))
    checks.append(
        CheckResult(
            name="isolation_no_cross_provider_fallback_openrouter",
            category="failure_isolation",
            ok="openrouter" in type(created).__name__.lower(),
            detail=f"class={type(created).__name__}",
        )
    )
    return checks, {}


# ---------------------------------------------------------------------------
# Assessment / reporting / doctor / CLI
# ---------------------------------------------------------------------------


def run_assessment_authority_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    status_values = tuple(sorted(item.value for item in AIExecutionStatus))
    checks = [
        CheckResult(
            name="assessment_schema_version_is_1_2",
            category="assessment_authority",
            ok=ASSESSMENT_JSON_SCHEMA_VERSION == ASSESSMENT_SCHEMA_VERSION,
            detail=f"schema={ASSESSMENT_JSON_SCHEMA_VERSION}",
        ),
        CheckResult(
            name="ai_execution_status_values_unchanged",
            category="assessment_authority",
            ok=status_values == AI_EXECUTION_STATUS_VALUES,
            detail=f"values={list(status_values)}",
        ),
    ]
    return checks, {}


def run_reporting_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    from codestrata.reporting import modernization_models
    from codestrata.reporting.contract import constants as report_constants

    report_names = set(dir(modernization_models)) | set(dir(report_constants))
    forbidden_report_tokens = {
        "api_key",
        "authorization",
        "base_url",
        "http_referer",
        "x_title",
        "profile_name",
        "region_name",
        "request_id",
        "prompt_text",
        "response_text",
        "doctor_ready",
        "openrouter_readiness",
    }
    offenders = sorted(report_names & forbidden_report_tokens)
    # Scan assessment report field names on ModernizationAssessment-like models.
    field_offenders: list[str] = []
    # Approved existing fields may include prompt_hash / prompt_template_version.
    # Fail only on secret/credential/endpoint diagnostic field names.
    leak_field_tokens = (
        "api_key",
        "authorization",
        "base_url",
        "http_referer",
        "x_title",
        "request_id",
        "doctor_ready",
        "openrouter_readiness",
        "profile_name",
        "region_name",
        "prompt_text",
        "response_text",
    )
    for name in ("ModernizationAssessmentResult", "AIExecutionRecord", "AIAttemptInfo"):
        model = getattr(modernization_models, name, None)
        if model is None or not hasattr(model, "model_fields"):
            continue
        for field_name in model.model_fields:
            if field_name in forbidden_report_tokens or field_name in leak_field_tokens:
                field_offenders.append(field_name)
            if any(
                token in field_name
                for token in ("api_key", "authorization", "request_id", "base_url")
            ):
                field_offenders.append(field_name)
    checks = [
        CheckResult(
            name="assessment_schema_remains_1_2",
            category="reporting_boundary",
            ok=ASSESSMENT_JSON_SCHEMA_VERSION == "1.2",
            detail=f"schema={ASSESSMENT_JSON_SCHEMA_VERSION}",
        ),
        CheckResult(
            name="doctor_tokens_absent_from_report_contract_exports",
            category="reporting_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        ),
        CheckResult(
            name="provider_diagnostic_keys_absent_from_assessment_fields",
            category="reporting_boundary",
            ok=not field_offenders,
            detail=f"offenders={sorted(set(field_offenders))}",
        ),
        CheckResult(
            name="default_models_unchanged",
            category="reporting_boundary",
            ok=OpenAISettings().answer_model == OPENAI_DEFAULT_MODEL,
            detail=f"openai_default={OpenAISettings().answer_model}",
        ),
    ]
    from codestrata.config.settings import DEFAULT_BEDROCK_MODEL_ID

    checks.append(
        CheckResult(
            name="bedrock_default_model_unchanged",
            category="reporting_boundary",
            ok=DEFAULT_BEDROCK_MODEL_ID == BEDROCK_DEFAULT_MODEL,
            detail=f"default={DEFAULT_BEDROCK_MODEL_ID}",
        )
    )
    return checks, {}


def run_doctor_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    doctor_source = (engine_root / _DOCTOR_REL).read_text(encoding="utf-8")
    token_hits = [token for token in DOCTOR_FORBIDDEN_CALL_TOKENS if token in doctor_source]
    imports = _module_imports(engine_root / _DOCTOR_REL)
    adapter_import = any("provider_adapters" in name for name in imports)
    with patch(
        "codestrata.ai.providers.doctor.probe_aws_session_for_bedrock",
        synthetic_bedrock_probe,
    ):
        report = build_ai_configuration_report(
            settings_for(
                "openrouter",
                openrouter={
                    "model": SYNTHETIC_MODEL_OPENROUTER,
                    "site_url": SYNTHETIC_SITE_URL,
                    "app_name": SYNTHETIC_APP_NAME,
                },
            ),
            environ={"OPENROUTER_API_KEY": SYNTHETIC_OPENROUTER_KEY},
            openrouter_dependency_available=True,
        )
    overview = canonical_json(
        {
            "details": [item.detail for item in report.providers],
            "checks": [check.detail for check in report.checks],
            "model_id": report.model_id,
        }
    )
    leaked = leaked_markers(
        overview,
        (
            SYNTHETIC_OPENROUTER_KEY,
            SYNTHETIC_MODEL_OPENROUTER,
            SYNTHETIC_SITE_URL,
            SYNTHETIC_APP_NAME,
            SYNTHETIC_BASE_URL,
        ),
    )
    checks = [
        CheckResult(
            name="doctor_source_forbids_client_construction_tokens",
            category="doctor_boundary",
            ok=not token_hits,
            detail=f"hits={token_hits}",
        ),
        CheckResult(
            name="doctor_does_not_import_provider_adapters",
            category="doctor_boundary",
            ok=not adapter_import,
            detail=f"imports_adapters={adapter_import}",
        ),
        CheckResult(
            name="doctor_report_overview_omits_privacy_markers",
            category="doctor_boundary",
            ok=not leaked,
            detail=_safe_detail(f"leaked={leaked}"),
        ),
    ]
    return checks, {}


def run_cli_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    paths = (
        engine_root / "src/codestrata/cli/assess.py",
        engine_root / "src/codestrata/cli/ai_cmd.py",
    )
    checks: list[CheckResult] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        hits = [token for token in CLI_FORBIDDEN_FLAG_TOKENS if token in text]
        checks.append(
            CheckResult(
                name=f"cli_{path.stem}_has_no_secret_flags",
                category="cli_boundary",
                ok=not hits,
                detail=f"hits={hits}",
            )
        )
    return checks, {}


# ---------------------------------------------------------------------------
# Telemetry / analytics / platform / data lake / vscode / cursor
# ---------------------------------------------------------------------------


def run_telemetry_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    offenders: list[str] = []
    for rel in _ADAPTER_PACKAGES:
        for path in _collect_py_files(engine_root / rel):
            names = _module_imports(path)
            hits = _imports_forbidden(
                names, ("codestrata.telemetry", "codestrata.analytics")
            )
            if hits:
                offenders.append(f"{path.relative_to(engine_root)}:{hits}")
    return [
        CheckResult(
            name="provider_adapters_do_not_import_telemetry_or_analytics",
            category="telemetry_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        )
    ], {}


def run_analytics_boundary_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    openrouter_in_families = "openrouter" in APPROVED_AI_PROVIDER_FAMILIES
    exact_fields = {
        name
        for name in APPROVED_AI_ANALYTICS_FIELD_NAMES
        if "model_id" in name or name in {"model", "exact_model", "prompt", "response"}
    }
    checks = [
        CheckResult(
            name="openrouter_present_as_bounded_provider_family",
            category="analytics_boundary",
            ok=openrouter_in_families,
            detail=f"families={sorted(APPROVED_AI_PROVIDER_FAMILIES)}",
        ),
        CheckResult(
            name="approved_ai_analytics_fields_omit_exact_model_and_content",
            category="analytics_boundary",
            ok=not exact_fields,
            detail=f"exact_fields={sorted(exact_fields)}",
        ),
    ]
    return checks, {}


def run_platform_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    offenders: list[str] = []
    scan_roots = [
        *[(engine_root / rel) for rel in _ADAPTER_PACKAGES],
        engine_root / _CONTRACTS_PKG,
        *[(engine_root / rel) for rel in _WRAPPER_FILES],
    ]
    for root in scan_roots:
        for path in _collect_py_files(root):
            hits = _imports_forbidden(
                _module_imports(path),
                ("codestrata.platform", "codestrata_platform", "codestrata.datalake", "codestrata_datalake"),
            )
            if hits:
                offenders.append(f"{path.relative_to(engine_root)}:{hits}")
    return [
        CheckResult(
            name="provider_stack_imports_no_platform_or_datalake",
            category="platform_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        )
    ], {}


def run_data_lake_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    # Same import scan, separate status field.
    offenders: list[str] = []
    for rel in (*_ADAPTER_PACKAGES, _CONTRACTS_PKG, *_WRAPPER_FILES):
        for path in _collect_py_files(engine_root / rel):
            hits = _imports_forbidden(
                _module_imports(path), ("codestrata.datalake", "codestrata_datalake")
            )
            if hits:
                offenders.append(str(path.relative_to(engine_root)))
    return [
        CheckResult(
            name="provider_stack_imports_no_datalake",
            category="data_lake_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        )
    ], {}


def run_vscode_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    repo_root = engine_root.parents[_REPO_ROOT_FROM_ENGINE - 2] if False else engine_root.parent
    # engine_root is .../engine; repo root is parent.
    repo_root = engine_root.parent
    vscode = repo_root / "vscode-plugin"
    package_json = vscode / "package.json"
    checks = [
        CheckResult(
            name="vscode_plugin_package_json_exists",
            category="vscode_boundary",
            ok=package_json.is_file(),
            detail=f"exists={package_json.is_file()}",
        )
    ]
    hits: list[str] = []
    src = vscode / "src"
    if src.is_dir():
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ts", ".js", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "openrouter" in text.lower() or "OPENROUTER" in text:
                hits.append(str(path.relative_to(repo_root)))
    checks.append(
        CheckResult(
            name="vscode_src_has_no_openrouter_config",
            category="vscode_boundary",
            ok=not hits,
            detail=f"hits={hits}",
        )
    )
    return checks, {}


def run_cursor_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    """Slice 12.1+: Cursor product source must be absent (no OpenRouter surface)."""

    repo_root = engine_root.parent
    cursor = repo_root / "cursor-plugin"
    package_json = cursor / "package.json"
    absent = not cursor.exists()
    checks = [
        CheckResult(
            name="cursor_plugin_directory_absent",
            category="cursor_boundary",
            ok=absent,
            detail=f"absent={absent}",
        ),
        CheckResult(
            name="cursor_plugin_package_json_absent",
            category="cursor_boundary",
            ok=not package_json.is_file(),
            detail=f"package_json_present={package_json.is_file()}",
        ),
    ]
    hits: list[str] = []
    src = cursor / "src"
    if src.is_dir():
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ts", ".js", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "openrouter" in text.lower() or "OPENROUTER" in text:
                hits.append(str(path.relative_to(repo_root)))
    checks.append(
        CheckResult(
            name="cursor_src_has_no_openrouter_config",
            category="cursor_boundary",
            ok=not hits,
            detail=f"hits={hits};src_present={src.is_dir()}",
        )
    )
    return checks, {}


# ---------------------------------------------------------------------------
# Dependency / packaging / public export / safety / determinism / privacy report
# ---------------------------------------------------------------------------


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    offenders: list[str] = []
    # Adapters must not import each other.
    pairs = (
        ("bedrock", "openai"),
        ("bedrock", "openrouter"),
        ("openai", "bedrock"),
        ("openai", "openrouter"),
        ("openrouter", "bedrock"),
        ("openrouter", "openai"),
    )
    for src, dst in pairs:
        package = engine_root / f"src/codestrata/ai/provider_adapters/{src}"
        for path in _collect_py_files(package):
            for name in _module_imports(path):
                if name.startswith(f"codestrata.ai.provider_adapters.{dst}"):
                    offenders.append(f"{src}->{dst}:{path.name}")

    # SDK imports only inside client modules (lazy).
    sdk_outside_client: list[str] = []
    for provider in ("openai", "openrouter", "bedrock"):
        package = engine_root / f"src/codestrata/ai/provider_adapters/{provider}"
        for path in _collect_py_files(package):
            if path.name == "client.py":
                continue
            names = _module_imports(path)
            for name in names:
                if name in {"openai", "boto3", "botocore"} or name.startswith(
                    ("openai.", "boto3.", "botocore.")
                ):
                    sdk_outside_client.append(str(path.relative_to(engine_root)))

    # Contracts stay SDK-free.
    contracts_sdk: list[str] = []
    for path in _collect_py_files(engine_root / _CONTRACTS_PKG):
        for name in _module_imports(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                contracts_sdk.append(path.name)

    checks = [
        CheckResult(
            name="adapters_do_not_import_one_another",
            category="dependency_boundary",
            ok=not offenders,
            detail=f"offenders={offenders}",
        ),
        CheckResult(
            name="sdk_imports_confined_to_client_modules",
            category="dependency_boundary",
            ok=not sdk_outside_client,
            detail=f"offenders={sdk_outside_client}",
        ),
        CheckResult(
            name="common_contracts_remain_sdk_free",
            category="dependency_boundary",
            ok=not contracts_sdk,
            detail=f"offenders={contracts_sdk}",
        ),
    ]
    return checks, {}


def run_packaging_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    import yaml

    manifest_path = engine_root.parent / "public-export-manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    engine_export = None
    for item in manifest.get("exports", []):
        if item.get("name") == "codestrata-engine":
            engine_export = item
            break
    includes = list((engine_export or {}).get("include", []))
    checks = [
        CheckResult(
            name="public_export_manifest_includes_verification_glob",
            category="packaging",
            ok="verification/**" in includes,
            detail=f"has_verification_glob={'verification/**' in includes}",
        ),
        CheckResult(
            name="public_export_manifest_exists",
            category="packaging",
            ok=manifest_path.is_file(),
            detail="manifest present",
        ),
    ]
    return checks, {}


def run_public_export_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    # Alias category for report status field.
    packaging_checks, matrix = run_packaging_checks(engine_root)
    remapped = [
        CheckResult(
            name=check.name.replace("packaging", "public_export")
            if "packaging" in check.name
            else check.name,
            category="public_export",
            ok=check.ok,
            detail=check.detail,
            evidence=check.evidence,
        )
        for check in packaging_checks
    ]
    remapped.append(
        CheckResult(
            name="privacy_boundary_package_covered_by_verification_glob",
            category="public_export",
            ok=True,
            detail="verification/** covers ai_provider_privacy_boundaries",
        )
    )
    return remapped, matrix


def run_safety_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        CheckResult(
            name="no_live_network_markers_in_fixtures",
            category="safety",
            ok="example.invalid" in SYNTHETIC_BASE_URL,
            detail="synthetic base URL uses .invalid",
        ),
        CheckResult(
            name="synthetic_keys_are_not_real_shaped_production_defaults",
            category="safety",
            ok="never-real" in SYNTHETIC_OPENAI_KEY and "privacy-1112" in SYNTHETIC_OPENROUTER_KEY,
            detail="distinctive synthetic markers",
        ),
    ]
    return checks, {}


def run_determinism_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    first = canonical_json(
        openai_diagnostics.diagnostic_view_of_adapter(_openai_adapter())
    )
    second = canonical_json(
        openai_diagnostics.diagnostic_view_of_adapter(_openai_adapter())
    )
    checks = [
        CheckResult(
            name="adapter_diagnostic_views_are_deterministic",
            category="determinism",
            ok=first == second,
            detail="identical diagnostic views",
        )
    ]
    return checks, {}


def run_privacy_checks(
    report_payload: dict[str, Any] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    """Local adapter scan always; report scan when payload is assembled."""

    checks: list[CheckResult] = []
    for provider_id, adapter in _adapters().items():
        leaked = leaked_markers(
            canonical_json(_diag_module(provider_id).diagnostic_view_of_adapter(adapter))
        )
        checks.append(
            CheckResult(
                name=f"privacy_scan_{provider_id}_adapter_diagnostics",
                category="credential_privacy",
                ok=not leaked,
                detail=_safe_detail(f"leaked={leaked}"),
            )
        )
    if report_payload is None:
        checks.append(
            CheckResult(
                name="privacy_scan_deferred_until_report_assembled",
                category="credential_privacy",
                ok=True,
                detail="report scanned after assembly",
            )
        )
        return checks, {}

    blob = json.dumps(report_payload, sort_keys=True)
    # Report must omit distinctive synthetic markers. Env *names* and presence
    # booleans may appear; values must not.
    report_markers = (
        SYNTHETIC_OPENAI_KEY,
        SYNTHETIC_OPENROUTER_KEY,
        SYNTHETIC_AWS_ACCESS,
        SYNTHETIC_AWS_SECRET,
        SYNTHETIC_SESSION,
        SYNTHETIC_PROMPT,
        SYNTHETIC_RESPONSE,
        SYNTHETIC_MODEL_OPENAI,
        SYNTHETIC_MODEL_BEDROCK,
        SYNTHETIC_MODEL_OPENROUTER,
        SYNTHETIC_REQUEST_ID,
        SYNTHETIC_BASE_URL,
        SYNTHETIC_SITE_URL,
        SYNTHETIC_APP_NAME,
        SYNTHETIC_PATH,
        SYNTHETIC_PROFILE,
        SYNTHETIC_REGION,
        SYNTHETIC_EXCEPTION,
        "Traceback",
        "/Users/synthetic-privacy-1112",
    )
    offenders = leaked_markers(blob, report_markers)
    checks.append(
        CheckResult(
            name="verification_report_omits_privacy_markers",
            category="credential_privacy",
            ok=not offenders,
            detail=_safe_detail(f"offenders={offenders}"),
        )
    )
    return checks, {}


__all__ = [
    "run_analytics_boundary_checks",
    "run_assessment_authority_checks",
    "run_cli_boundary_checks",
    "run_configuration_checks",
    "run_configuration_path_write_checks",
    "run_credential_checks",
    "run_cursor_boundary_checks",
    "run_data_lake_boundary_checks",
    "run_dependency_boundary_checks",
    "run_determinism_checks",
    "run_diagnostics_checks",
    "run_doctor_boundary_checks",
    "run_error_privacy_checks",
    "run_execution_checks",
    "run_failure_isolation_checks",
    "run_inventory_checks",
    "run_logging_checks",
    "run_model_privacy_checks",
    "run_packaging_checks",
    "run_platform_boundary_checks",
    "run_privacy_checks",
    "run_provider_matrix_checks",
    "run_public_export_checks",
    "run_registry_checks",
    "run_reporting_boundary_checks",
    "run_request_privacy_checks",
    "run_response_privacy_checks",
    "run_retry_checks",
    "run_safety_checks",
    "run_telemetry_boundary_checks",
    "run_vscode_boundary_checks",
]
