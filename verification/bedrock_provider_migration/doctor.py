"""Doctor: unchanged by this slice, and still on the compatibility path.

``codestrata ai doctor`` reports whether Bedrock is configured. Slice 11.7
leaves it exactly as it was: it still probes AWS through
``aws_config.probe_aws_session_for_bedrock`` rather than through the new
adapter's credential boundary. That is a recorded limitation
(``doctor_uses_compatibility_path``), not an oversight — routing doctor
through the adapter would change what an operator sees, which is out of
scope for a migration slice.

These checks never invoke the probe, so no AWS call is made here either.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

from codestrata.ai.providers import doctor as doctor_module
from verification.bedrock_provider_migration.contract import DOCTOR_COVERED_PROVIDERS
from verification.bedrock_provider_migration.models import CheckResult

_EXPECTED_DOCTOR_SYMBOLS: tuple[str, ...] = (
    "AiCheck",
    "AiConfigurationReport",
    "ConfigStatus",
    "ProviderOverview",
    "build_ai_configuration_report",
)


def _doctor_imports() -> set[str]:
    tree = ast.parse(inspect.getsource(doctor_module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def check_the_doctor_surface_is_unchanged() -> CheckResult:
    missing = sorted(
        name for name in _EXPECTED_DOCTOR_SYMBOLS if not hasattr(doctor_module, name)
    )
    return CheckResult(
        name="the_ai_doctor_public_surface_is_unchanged",
        category="doctor",
        ok=not missing,
        detail=f"missing_symbols={missing}",
    )


def check_the_doctor_never_imports_the_adapter() -> CheckResult:
    offenders = sorted(
        name
        for name in _doctor_imports()
        if name.startswith("codestrata.ai.provider_adapters")
        or name.startswith("codestrata.ai.provider_contracts")
    )
    return CheckResult(
        name="the_ai_doctor_still_runs_on_the_compatibility_path_not_the_adapter",
        category="doctor",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_the_doctor_still_probes_through_aws_config() -> CheckResult:
    source = inspect.getsource(doctor_module)
    return CheckResult(
        name="the_ai_doctor_still_probes_aws_through_aws_config",
        category="doctor",
        ok="probe_aws_session_for_bedrock" in source,
        detail="profile/region resolution for doctor is unchanged",
    )


def check_the_doctor_still_reports_both_providers() -> CheckResult:
    source = inspect.getsource(doctor_module)
    missing = sorted(
        name for name in DOCTOR_COVERED_PROVIDERS if f'"{name}"' not in source
    )
    return CheckResult(
        name="the_ai_doctor_still_reports_an_overview_for_both_providers",
        category="doctor",
        ok=not missing,
        detail=f"missing_provider_overviews={missing}",
    )


def check_the_doctor_reports_no_credential_value() -> CheckResult:
    """Doctor names environment variables; it must never render their values."""

    source = inspect.getsource(doctor_module)
    offenders = sorted(
        token
        for token in ("AWS_SECRET_ACCESS_KEY=", "aws_secret_access_key", "session_token")
        if token in source
    )
    return CheckResult(
        name="the_ai_doctor_names_credential_variables_without_rendering_their_values",
        category="doctor",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def run_doctor_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_doctor_surface_is_unchanged(),
        check_the_doctor_never_imports_the_adapter(),
        check_the_doctor_still_probes_through_aws_config(),
        check_the_doctor_still_reports_both_providers(),
        check_the_doctor_reports_no_credential_value(),
    ]
    matrix: dict[str, Any] = {
        "doctor_changed_by_slice_11_7": False,
        "doctor_probe_owner": "codestrata.ai.aws_config.probe_aws_session_for_bedrock",
        "doctor_uses_adapter": False,
    }
    return checks, matrix


__all__ = [
    "check_the_doctor_never_imports_the_adapter",
    "check_the_doctor_reports_no_credential_value",
    "check_the_doctor_still_probes_through_aws_config",
    "check_the_doctor_still_reports_both_providers",
    "check_the_doctor_surface_is_unchanged",
    "run_doctor_checks",
]
