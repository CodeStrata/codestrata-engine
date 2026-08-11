"""SV.11.6 OpenAI Provider Migration verification — orchestration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.openai_provider_migration import (
    authentication,
    baseline_compatibility,
    configuration,
    dependency_boundary,
    doctor,
    errors,
    execution,
    fail_soft,
    inventory,
    mixed_mode,
    privacy,
    reporting,
    reporting_boundary,
    requests,
    responses,
    scenarios,
    usage,
)
from verification.openai_provider_migration.contract import (
    ALLOWED_VERDICTS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    PACKAGE_RELATIVE_PATH,
    REPORT_FILENAME,
    REPORT_MD_FILENAME,
)
from verification.openai_provider_migration.models import (
    CheckResult,
    OpenAIMigrationVerificationReport,
)


def engine_root_from_package() -> Path:
    """Resolve the Engine repository root (the directory containing ``pyproject.toml``)."""

    # verification/openai_provider_migration/runner.py -> parents[2] == engine/
    return Path(__file__).resolve().parents[2]


def _default_package_dir(engine_root: Path) -> Path:
    return engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


def _default_output_dir(engine_root: Path) -> Path:
    return engine_root / "reports" / "verification" / "sv11-6"


def run_openai_provider_migration_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    write_markdown: bool = True,
) -> OpenAIMigrationVerificationReport:
    """Run the full SV.11.6 verification suite and write the report."""

    engine = (engine_root or engine_root_from_package()).resolve()
    package_dir = _default_package_dir(engine)
    out = (output_dir or _default_output_dir(engine)).resolve()

    all_checks: list[CheckResult] = []
    matrices: dict[str, Any] = {}

    def _collect(category: str, result: tuple[list[CheckResult], Any]) -> None:
        checks, matrix = result
        all_checks.extend(checks)
        matrices[category] = matrix

    _collect("inventory", inventory.run_inventory_checks(engine, package_dir))
    _collect(
        "dependency_boundary",
        dependency_boundary.run_dependency_boundary_checks(engine, package_dir),
    )
    _collect("baseline_compatibility", baseline_compatibility.run_baseline_compatibility_checks())
    _collect("configuration", configuration.run_configuration_checks())
    _collect("authentication", authentication.run_authentication_checks())
    _collect("requests", requests.run_request_checks())
    _collect("responses", responses.run_response_checks())
    _collect("usage", usage.run_usage_checks())
    _collect("errors", errors.run_error_checks())
    _collect("execution", execution.run_execution_checks())
    _collect("fail_soft", fail_soft.run_fail_soft_checks())
    _collect("mixed_mode", mixed_mode.run_mixed_mode_checks(engine))
    _collect("doctor", doctor.run_doctor_checks(engine))
    _collect("reporting_boundary", reporting_boundary.run_reporting_boundary_checks(package_dir))
    _collect("privacy", privacy.run_adapter_privacy_checks())

    negative_scenarios = scenarios.build_negative_scenarios(engine, package_dir)
    if len(negative_scenarios) < NEGATIVE_SCENARIO_COUNT_MIN:
        raise RuntimeError(
            f"expected at least {NEGATIVE_SCENARIO_COUNT_MIN} negative scenarios, "
            f"got {len(negative_scenarios)}"
        )
    matrices["scenarios"] = scenarios.scenario_matrix(negative_scenarios)

    # Report privacy is asserted against the assembled body, so it runs on a
    # preview report and its results are folded back into the final one.
    preview = reporting.assemble_report(
        all_checks=all_checks,
        matrices=matrices,
        negative_scenarios=negative_scenarios,
    )
    all_checks.extend(privacy.run_report_privacy_checks(preview.to_dict()))

    report = reporting.assemble_report(
        all_checks=all_checks,
        matrices=matrices,
        negative_scenarios=negative_scenarios,
    )

    out.mkdir(parents=True, exist_ok=True)
    json_path = out / REPORT_FILENAME
    report.write_json(json_path)
    leaks = reporting.report_contains_forbidden_leak(json_path.read_text(encoding="utf-8"))
    if leaks:
        raise RuntimeError(
            "OpenAI provider migration report contains forbidden tokens "
            f"(categories only, no values): {sorted(leaks)}"
        )
    if write_markdown:
        report.write_markdown(out / REPORT_MD_FILENAME)
    return report


def verdict_is_acceptable(verdict: str) -> bool:
    return verdict in ALLOWED_VERDICTS


__all__ = [
    "engine_root_from_package",
    "run_openai_provider_migration_verification",
    "verdict_is_acceptable",
]
