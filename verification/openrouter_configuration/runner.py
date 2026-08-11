"""Run SV.11.10 OpenRouter configuration verification."""

from __future__ import annotations

from pathlib import Path

from verification.openrouter_configuration import checks, reporting, scenarios
from verification.openrouter_configuration.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.openrouter_configuration.models import CheckResult


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_verification(root: Path | None = None):
    engine = root or engine_root()
    all_checks: list[CheckResult] = []

    for section_checks, _matrix in (
        checks.run_inventory_checks(engine),
        checks.run_provider_selection_checks(),
        checks.run_configuration_checks(),
        checks.run_model_resolution_checks(),
        checks.run_credential_checks(),
        checks.run_base_url_checks(),
        checks.run_header_checks(),
        checks.run_client_construction_checks(),
        checks.run_runtime_wiring_checks(),
        checks.run_fail_soft_checks(),
        checks.run_cli_and_doctor_checks(engine),
        checks.run_regression_checks(),
        checks.run_dependency_boundary_checks(engine),
        checks.run_determinism_checks(),
    ):
        all_checks.extend(section_checks)

    privacy_placeholder, _ = checks.run_privacy_checks(None)
    all_checks.extend(privacy_placeholder)

    negative = scenarios.run_negative_scenarios(engine)
    all_checks.append(
        CheckResult(
            name="negative_scenario_count_meets_minimum",
            category="contract",
            ok=len(negative) >= NEGATIVE_SCENARIO_COUNT_MIN,
            detail=f"scenario_count={len(negative)}",
        )
    )

    draft = reporting.build_report(checks=all_checks, scenarios=negative)
    privacy_final, _ = checks.run_privacy_checks(draft.to_dict())
    all_checks = [
        check
        for check in all_checks
        if check.name != "privacy_scan_deferred_until_report_assembled"
    ]
    all_checks.extend(privacy_final)
    return reporting.build_report(checks=all_checks, scenarios=negative)


__all__ = ["engine_root", "run_verification"]
