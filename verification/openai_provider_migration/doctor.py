"""Doctor: unchanged by this slice, and still secret-free for the OpenAI provider.

``ai/providers/doctor.py`` is deliberately *not* migrated. It keeps reading
``[ai.openai].api_key_env`` and the optional extras directly rather than asking
the new adapter, which is recorded as the ``doctor_uses_compatibility_path``
limitation. These checks pin that it stayed on the legacy path, that it never
constructs a provider or invokes a model, and that its OpenAI output remains
secret-free now that a migrated provider sits behind it.

The full ``build_ai_configuration_report`` is deliberately *not* called here:
its Bedrock branch probes a real AWS session, which would mean real credential
resolution and network access. Only the OpenAI-side overview — which reads one
synthetic environment variable name and nothing else — is exercised.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from dataclasses import asdict
from pathlib import Path
from typing import Any

from codestrata.ai.providers import doctor as doctor_module
from codestrata.ai.providers.doctor import (
    AiConfigurationReport,
    ConfigStatus,
    ProviderOverview,
)
from codestrata.config import CodestrataSettings
from verification.openai_provider_migration.contract import (
    DOCTOR_COVERED_PROVIDERS,
    OPENAI_API_KEY_ENV_DEFAULT,
)
from verification.openai_provider_migration.determinism import canonical_json
from verification.openai_provider_migration.models import CheckResult

_DOCTOR_RELATIVE_PATH = "ai/providers/doctor.py"
_SYNTHETIC_KEY_VAR = "SYNTHETIC_DOCTOR_OPENAI_KEY_VAR"


def _openai_overview(api_key_env: str = _SYNTHETIC_KEY_VAR) -> ProviderOverview:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {"provider": "openai", "openai": {"api_key_env": api_key_env}},
        }
    )
    return doctor_module._openai_overview(settings)


def _doctor_source(engine_root: Path) -> str:
    return (engine_root / "src" / "codestrata" / _DOCTOR_RELATIVE_PATH).read_text(encoding="utf-8")


def _doctor_imports(engine_root: Path) -> set[str]:
    tree = ast.parse(_doctor_source(engine_root), filename="doctor.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def check_doctor_still_covers_both_providers(engine_root: Path) -> CheckResult:
    source = _doctor_source(engine_root)
    covered = tuple(
        name for name in sorted(DOCTOR_COVERED_PROVIDERS) if f'name="{name}"' in source
    )
    return CheckResult(
        name="doctor_still_reports_on_both_bedrock_and_openai",
        category="doctor",
        ok=covered == tuple(sorted(DOCTOR_COVERED_PROVIDERS)),
        detail=f"providers_covered={list(covered)}",
    )


def check_doctor_reports_the_configured_key_variable_by_name() -> CheckResult:
    overview = _openai_overview()
    return CheckResult(
        name="doctor_reports_the_configured_api_key_variable_by_name",
        category="doctor",
        ok=_SYNTHETIC_KEY_VAR in overview.required_env,
        detail="the required_env list names the configured variable",
    )


def check_doctor_reports_a_missing_key_as_not_configured() -> CheckResult:
    overview = _openai_overview()
    ok = overview.status is ConfigStatus.NOT_CONFIGURED and overview.credential_source is None
    return CheckResult(
        name="doctor_reports_an_unset_api_key_variable_as_not_configured",
        category="doctor",
        ok=ok,
        detail=f"status={overview.status.value}",
    )


def check_doctor_guidance_never_echoes_a_value() -> CheckResult:
    overview = _openai_overview()
    serialized = canonical_json(asdict(overview))
    leaked = sorted(token for token in ("sk-", "Bearer ") if token in serialized)
    ok = not leaked and (overview.guidance or "").startswith(f"export {_SYNTHETIC_KEY_VAR}=")
    return CheckResult(
        name="doctor_guidance_names_the_variable_to_export_and_never_a_value",
        category="doctor",
        ok=ok,
        detail=f"leaked_tokens={leaked}",
    )


def check_doctor_never_constructs_a_provider(engine_root: Path) -> CheckResult:
    """Doctor is a configuration read, not an invocation path."""

    offenders = sorted(
        name
        for name in _doctor_imports(engine_root)
        if name.startswith("codestrata.ai.provider_adapters")
        or name.startswith("codestrata.ai.provider_contracts")
        or name.endswith("openai_provider")
        or name.endswith("openrouter_provider")
    )
    return CheckResult(
        name="doctor_neither_imports_the_adapter_nor_constructs_a_provider",
        category="doctor",
        ok=not offenders,
        detail=f"unexpected_imports={offenders}",
    )


def check_doctor_remains_on_the_compatibility_path(engine_root: Path) -> CheckResult:
    """Recorded as the ``doctor_uses_compatibility_path`` limitation."""

    source = _doctor_source(engine_root)
    ok = "api_key_env" in source and "provider_adapters" not in source
    return CheckResult(
        name="doctor_still_resolves_openai_configuration_itself_rather_than_via_the_adapter",
        category="doctor",
        ok=ok,
        detail="doctor duplicates the api_key_env fallback; recorded as a limitation",
    )


def check_doctor_does_not_invoke_a_model(engine_root: Path) -> CheckResult:
    source = _doctor_source(engine_root)
    offenders = sorted(
        token for token in ("chat.completions", "converse(", ".invoke(") if token in source
    )
    return CheckResult(
        name="doctor_makes_no_model_invocation",
        category="doctor",
        ok=not offenders,
        detail=f"invocation_tokens={offenders}",
    )


def check_doctor_report_shape_is_unchanged() -> CheckResult:
    expected = {
        "active_provider",
        "active_supported",
        "checks",
        "docs_url",
        "model_id",
        "openrouter_readiness",
        "providers",
        "supported_providers",
    }
    actual = {field.name for field in dataclasses.fields(AiConfigurationReport)}
    return CheckResult(
        name="the_doctor_report_shape_is_unchanged_by_this_slice",
        category="doctor",
        ok=actual == expected,
        detail=f"report_fields={sorted(actual)}",
    )


def check_doctor_default_key_variable_is_unchanged() -> CheckResult:
    signature_source = inspect.getsource(doctor_module._openai_overview)
    ok = OPENAI_API_KEY_ENV_DEFAULT in signature_source and OPENAI_API_KEY_ENV_DEFAULT in (
        _openai_overview(OPENAI_API_KEY_ENV_DEFAULT).required_env
    )
    return CheckResult(
        name="doctor_still_falls_back_to_the_unchanged_default_key_variable",
        category="doctor",
        ok=ok,
        detail=f"default_variable={OPENAI_API_KEY_ENV_DEFAULT}",
    )


def run_doctor_checks(engine_root: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_doctor_still_covers_both_providers(engine_root),
        check_doctor_reports_the_configured_key_variable_by_name(),
        check_doctor_reports_a_missing_key_as_not_configured(),
        check_doctor_guidance_never_echoes_a_value(),
        check_doctor_never_constructs_a_provider(engine_root),
        check_doctor_remains_on_the_compatibility_path(engine_root),
        check_doctor_does_not_invoke_a_model(engine_root),
        check_doctor_report_shape_is_unchanged(),
        check_doctor_default_key_variable_is_unchanged(),
    ]
    matrix: dict[str, Any] = {
        "aws_probe_exercised": False,
        "doctor_migrated": False,
        "doctor_report_fields": sorted(
            field.name for field in dataclasses.fields(AiConfigurationReport)
        ),
        "reported_providers": list(DOCTOR_COVERED_PROVIDERS),
    }
    return checks, matrix


__all__ = [
    "check_doctor_default_key_variable_is_unchanged",
    "check_doctor_does_not_invoke_a_model",
    "check_doctor_guidance_never_echoes_a_value",
    "check_doctor_never_constructs_a_provider",
    "check_doctor_remains_on_the_compatibility_path",
    "check_doctor_report_shape_is_unchanged",
    "check_doctor_reports_a_missing_key_as_not_configured",
    "check_doctor_reports_the_configured_key_variable_by_name",
    "check_doctor_still_covers_both_providers",
    "run_doctor_checks",
]
