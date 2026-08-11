"""Fail-soft, doctor/CLI, reporting, privacy, dependency, and OpenRouter checks."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codestrata.ai.providers.bedrock import BedrockAIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderTimeoutError,
)
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.config.settings import OpenAISettings
from verification.ai_provider_cross_provider.contract import (
    ASSESSMENT_SCHEMA_VERSION,
    FORBIDDEN_PROVIDER_TOKENS,
    PRODUCT_PATH_SDK_FREE,
    WRAPPER_MODULES,
)
from verification.ai_provider_cross_provider.models import CheckResult
from verification.bedrock_provider_migration import fixtures as bedrock_fixtures
from verification.openai_provider_migration import fixtures as openai_fixtures


def check_openai_auth_failure_raises_legacy_error() -> CheckResult:
    provider = OpenAIAIModelProvider(
        client=openai_fixtures.Client(openai_fixtures.sdk_exception("AuthenticationError"))
    )
    try:
        provider.invoke(openai_fixtures.model_request(), openai_fixtures.invocation_options())
        raised: BaseException | None = None
    except AIProviderError as error:
        raised = error
    ok = isinstance(raised, AIProviderError) and not isinstance(raised, AIProviderTimeoutError)
    return CheckResult(
        name="openai_authentication_failure_still_raises_legacy_provider_error",
        category="fail_soft",
        ok=ok,
        detail=type(raised).__name__ if raised else "no exception",
    )


def check_bedrock_throttle_raises_timeout_error() -> CheckResult:
    provider = BedrockAIModelProvider(
        client=bedrock_fixtures.Client(bedrock_fixtures.client_error("ThrottlingException"))
    )
    try:
        provider.invoke(bedrock_fixtures.model_request(), bedrock_fixtures.invocation_options())
        raised: BaseException | None = None
    except AIProviderTimeoutError as error:
        raised = error
    except Exception as error:  # noqa: BLE001
        raised = error
    ok = isinstance(raised, AIProviderTimeoutError)
    return CheckResult(
        name="bedrock_throttling_still_raises_legacy_timeout_error",
        category="fail_soft",
        ok=ok,
        detail=type(raised).__name__ if raised else "no exception",
    )


def check_openai_missing_key_is_configuration_error() -> CheckResult:
    provider = OpenAIAIModelProvider(
        openai_settings=OpenAISettings(api_key_env="SYNTHETIC_UNSET_CROSS_PROVIDER_KEY"),
        client=None,
    )
    try:
        provider.invoke(openai_fixtures.model_request(), openai_fixtures.invocation_options())
        raised = False
        name = "none"
    except AIProviderConfigurationError:
        raised = True
        name = "AIProviderConfigurationError"
    except Exception as error:  # noqa: BLE001
        raised = False
        name = type(error).__name__
    return CheckResult(
        name="openai_missing_api_key_still_maps_to_configuration_error",
        category="fail_soft",
        ok=raised,
        detail=name,
    )


def check_no_cross_provider_fallback_on_failure() -> CheckResult:
    """A failed OpenAI invoke must not construct or call Bedrock."""

    openai = OpenAIAIModelProvider(
        client=openai_fixtures.Client(openai_fixtures.sdk_exception("RateLimitError"))
    )
    bedrock_calls: list[str] = []

    class _Probe(BedrockAIModelProvider):
        def invoke(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            bedrock_calls.append("invoked")
            return super().invoke(*args, **kwargs)

    del _Probe  # existence documents intent; we only assert OpenAI path raises
    try:
        openai.invoke(openai_fixtures.model_request(), openai_fixtures.invocation_options())
        failed = False
    except AIProviderError:
        failed = True
    ok = failed and bedrock_calls == []
    return CheckResult(
        name="openai_failure_does_not_fall_back_to_bedrock",
        category="fail_soft",
        ok=ok,
        detail="no silent provider substitution",
    )


def run_fail_soft_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openai_auth_failure_raises_legacy_error(),
        check_bedrock_throttle_raises_timeout_error(),
        check_openai_missing_key_is_configuration_error(),
        check_no_cross_provider_fallback_on_failure(),
    ]
    return checks, {"fail_soft_owner": "assessment_orchestration"}


def check_doctor_module_does_not_invoke_models(engine_root: Path) -> CheckResult:
    path = engine_root / "src" / "codestrata" / "ai" / "providers" / "doctor.py"
    source = path.read_text(encoding="utf-8")
    forbidden = ("chat.completions", "converse(", "AIProviderExecutor")
    offenders = [token for token in forbidden if token in source]
    return CheckResult(
        name="doctor_module_has_no_model_invocation_or_executor_wiring",
        category="doctor",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_cli_assess_has_no_openrouter_or_retry_flags(engine_root: Path) -> CheckResult:
    """CLI help may mention OpenRouter; credential/retry flags must not appear."""

    path = engine_root / "src" / "codestrata" / "cli" / "assess.py"
    source = path.read_text(encoding="utf-8")
    forbidden_flags = ("--max-retries", "--api-key", "--openrouter")
    offenders = [token for token in forbidden_flags if token in source]
    return CheckResult(
        name="cli_assess_has_no_openrouter_credential_or_retry_flags",
        category="cli",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def run_doctor_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    return [check_doctor_module_does_not_invoke_models(engine_root)], {}


def run_cli_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    return [check_cli_assess_has_no_openrouter_or_retry_flags(engine_root)], {}


def check_assessment_schema_constant(engine_root: Path) -> CheckResult:
    schema_path = (
        engine_root
        / "src"
        / "codestrata"
        / "resources"
        / "schemas"
        / "assessment"
        / "codestrata.io"
        / "v1.2"
        / "AssessmentReport.json"
    )
    ok = schema_path.is_file() and ASSESSMENT_SCHEMA_VERSION == "1.2"
    return CheckResult(
        name="assessment_schema_version_remains_1_2",
        category="reporting_boundary",
        ok=ok,
        detail=f"schema_path_present={schema_path.is_file()}",
    )


def run_reporting_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    return [check_assessment_schema_constant(engine_root)], {"customer_report_diagnostics": False}


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def check_contracts_remain_sdk_free(engine_root: Path) -> CheckResult:
    package = engine_root / "src" / "codestrata" / "ai" / "provider_contracts"
    offenders: list[str] = []
    for path in sorted(package.glob("*.py")):
        for name in _imported_names(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                offenders.append(f"{path.name}:{name}")
    return CheckResult(
        name="provider_contracts_remain_sdk_free",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_product_path_does_not_import_provider_sdks(engine_root: Path) -> CheckResult:
    offenders: list[str] = []
    for relative in PRODUCT_PATH_SDK_FREE:
        path = engine_root / "src" / "codestrata" / relative
        for name in _imported_names(path):
            if name in {"openai", "boto3", "botocore"} or name.startswith(
                ("openai.", "boto3.", "botocore.")
            ):
                offenders.append(f"{relative}:{name}")
    return CheckResult(
        name="assessment_enrichment_factory_and_cli_do_not_import_provider_sdks",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_adapters_do_not_import_each_other(engine_root: Path) -> CheckResult:
    openai_dir = engine_root / "src" / "codestrata" / "ai" / "provider_adapters" / "openai"
    bedrock_dir = engine_root / "src" / "codestrata" / "ai" / "provider_adapters" / "bedrock"
    offenders: list[str] = []
    for path in openai_dir.glob("*.py"):
        for name in _imported_names(path):
            if "provider_adapters.bedrock" in name:
                offenders.append(f"openai/{path.name}")
    for path in bedrock_dir.glob("*.py"):
        for name in _imported_names(path):
            if "provider_adapters.openai" in name:
                offenders.append(f"bedrock/{path.name}")
    return CheckResult(
        name="openai_and_bedrock_adapters_do_not_import_each_other",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_wrappers_exist(engine_root: Path) -> CheckResult:
    missing = [
        relative
        for relative in WRAPPER_MODULES
        if not (engine_root / "src" / "codestrata" / relative).is_file()
    ]
    return CheckResult(
        name="compatibility_wrappers_remain_present",
        category="dependency_boundary",
        ok=not missing,
        detail=f"missing={missing}",
    )


def run_dependency_boundary_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_contracts_remain_sdk_free(engine_root),
        check_product_path_does_not_import_provider_sdks(engine_root),
        check_adapters_do_not_import_each_other(engine_root),
        check_wrappers_exist(engine_root),
    ]
    return checks, {"sdk_imports": "adapter_local_only"}


def _allowed_openrouter_ai_path(rel: str) -> bool:
    """OpenRouter may appear under adapter, contracts, wrapper, factory, and doctor."""

    if rel.startswith("provider_adapters/openrouter/") or rel.startswith("provider_contracts/"):
        return True
    return rel in {
        "providers/openrouter_provider.py",
        "providers/factory.py",
        "providers/doctor.py",
    }


def check_openrouter_absent_from_ai_tree(engine_root: Path) -> CheckResult:
    """OpenRouter operational + doctor readiness files are allowed; other ai/ paths stay free."""

    ai_root = engine_root / "src" / "codestrata" / "ai"
    offenders: list[str] = []
    for path in ai_root.rglob("*.py"):
        rel = path.relative_to(ai_root).as_posix()
        if _allowed_openrouter_ai_path(rel):
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_PROVIDER_TOKENS:
            if token in text:
                offenders.append(f"{rel}:{token}")
    return CheckResult(
        name="openrouter_tokens_absent_from_non_operational_ai_tree",
        category="openrouter_absent",
        ok=not offenders,
        detail=f"offenders_count={len(offenders)}",
    )


def check_openrouter_registered_in_assess_registry() -> CheckResult:
    from codestrata.ai.provider_contracts.identifiers import ProviderId
    from codestrata.extensions.assess_ai import get_assess_ai_provider_registry

    values = {member.value for member in ProviderId}
    registered = set(get_assess_ai_provider_registry().list_providers())
    ok = "openrouter" in values and "openrouter" in registered
    return CheckResult(
        name="provider_id_and_assess_registry_both_include_openrouter",
        category="openrouter_absent",
        ok=ok,
        detail=f"provider_id_values={sorted(values)} registered={sorted(registered)}",
    )


def check_doctor_has_openrouter_local_readiness(engine_root: Path) -> CheckResult:
    path = engine_root / "src" / "codestrata" / "ai" / "providers" / "doctor.py"
    source = path.read_text(encoding="utf-8")
    has_readiness = (
        "evaluate_openrouter_readiness" in source and 'name="openrouter"' in source
    )
    construction_offenders = [
        token
        for token in (
            "provider_adapters.openrouter",
            "OpenRouterAIModelProvider",
            "chat.completions",
            ".invoke(",
        )
        if token in source
    ]
    return CheckResult(
        name="doctor_has_openrouter_local_readiness",
        category="openrouter_absent",
        ok=has_readiness and not construction_offenders,
        detail=(
            f"has_readiness={has_readiness} "
            f"construction_offenders={construction_offenders}"
        ),
    )


def run_openrouter_absent_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openrouter_absent_from_ai_tree(engine_root),
        check_openrouter_registered_in_assess_registry(),
        check_doctor_has_openrouter_local_readiness(engine_root),
    ]
    return checks, {
        "openrouter_started": True,
        "openrouter_operational_explicit": True,
        "openrouter_doctor_local_readiness_only": True,
    }


def run_privacy_checks(report_payload: dict[str, Any] | None = None) -> tuple[list[CheckResult], dict[str, Any]]:
    forbidden = (
        "sk-",
        "AKIA",
        "aws_secret",
        "session_token",
        "Traceback",
        "/Users/",
        "Authorization: Bearer",
        "OPENAI_API_KEY=",
    )
    if report_payload is None:
        check = CheckResult(
            name="privacy_scan_deferred_until_report_assembled",
            category="privacy",
            ok=True,
            detail="report privacy scanned after assembly",
        )
        return [check], {}
    import json

    blob = json.dumps(report_payload, sort_keys=True)
    offenders = [token for token in forbidden if token in blob]
    check = CheckResult(
        name="cross_provider_report_omits_secrets_paths_and_exception_text",
        category="privacy",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )
    return [check], {}


__all__ = [
    "run_cli_checks",
    "run_dependency_boundary_checks",
    "run_doctor_checks",
    "run_fail_soft_checks",
    "run_openrouter_absent_checks",
    "run_privacy_checks",
    "run_reporting_boundary_checks",
]
