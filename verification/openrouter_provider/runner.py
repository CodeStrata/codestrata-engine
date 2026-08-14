"""Run SV.11.9 OpenRouter provider verification."""

from __future__ import annotations

from pathlib import Path

from verification.openrouter_provider import checks, reporting, scenarios
from verification.openrouter_provider.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.openrouter_provider.models import CheckResult


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_verification(root: Path | None = None):
    engine = root or engine_root()
    from codestrata.extensions.assess_ai import reset_assess_ai_provider_registry_for_tests

    reset_assess_ai_provider_registry_for_tests()
    all_checks: list[CheckResult] = []

    for section_checks, _matrix in (
        checks.run_inventory_checks(engine),
        checks.run_provider_identity_checks(),
        checks.run_configuration_checks(),
        checks.run_capability_checks(),
        checks.run_client_boundary_checks(),
        checks.run_request_checks(),
        checks.run_response_usage_error_checks(),
        checks.run_execution_checks(),
        checks.run_registration_and_runtime_checks(engine),
        checks.run_regression_checks(),
        checks.run_dependency_boundary_checks(engine),
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
