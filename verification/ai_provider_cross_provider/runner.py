"""Run every SV.11.8 check and negative scenario, then assemble the report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_cross_provider import (
    boundaries,
    configuration,
    contracts_parity,
    matrix,
    provider_registry,
    reporting,
)
from verification.ai_provider_cross_provider.contract import (
    NEGATIVE_SCENARIO_COUNT_MIN,
    PRIOR_SLICE_IDS,
    SLICE_ID,
    SLICE_TITLE,
)
from verification.ai_provider_cross_provider.models import CheckResult


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_verification(root: Path | None = None) -> Any:
    engine = root or engine_root()
    checks: list[CheckResult] = []
    matrices: dict[str, Any] = {}

    for section, (section_checks, section_matrix) in (
        ("inventory", matrix.run_inventory_checks(engine)),
        ("baseline_compatibility", matrix.run_baseline_compatibility_checks()),
        ("provider_registry", provider_registry.run_provider_registry_checks()),
        ("provider_selection", provider_registry.run_provider_selection_checks(engine)),
        ("configuration", configuration.run_configuration_checks()),
        ("model_resolution", configuration.run_model_resolution_checks()),
        ("authentication", configuration.run_authentication_checks()),
        ("capabilities", configuration.run_capability_checks()),
        ("requests", contracts_parity.run_request_checks()),
        ("responses", contracts_parity.run_response_checks()),
        ("usage", contracts_parity.run_usage_checks()),
        ("errors", contracts_parity.run_error_checks()),
        ("execution", contracts_parity.run_execution_checks()),
        ("fail_soft", boundaries.run_fail_soft_checks()),
        ("doctor", boundaries.run_doctor_checks(engine)),
        ("cli", boundaries.run_cli_checks(engine)),
        ("reporting_boundary", boundaries.run_reporting_boundary_checks(engine)),
        ("dependency_boundary", boundaries.run_dependency_boundary_checks(engine)),
        ("openrouter_absent", boundaries.run_openrouter_absent_checks(engine)),
    ):
        checks.extend(section_checks)
        matrices[section] = section_matrix

    matrices["cross_provider_matrix"] = matrix.build_cross_provider_matrix()
    matrices["slice"] = {
        "epic_slice": SLICE_ID,
        "prior_slices_verified": list(PRIOR_SLICE_IDS),
        "title": SLICE_TITLE,
    }

    privacy_placeholder, _ = boundaries.run_privacy_checks(None)
    checks.extend(privacy_placeholder)

    scenarios = matrix.run_negative_scenarios(engine)
    checks.append(
        CheckResult(
            name="negative_scenario_count_meets_minimum",
            category="contract",
            ok=len(scenarios) >= NEGATIVE_SCENARIO_COUNT_MIN,
            detail=f"scenario_count={len(scenarios)}",
            evidence={"minimum_scenario_count": NEGATIVE_SCENARIO_COUNT_MIN},
        )
    )

    draft = reporting.build_report(checks=checks, scenarios=scenarios, matrices=matrices)
    privacy_final, privacy_matrix = boundaries.run_privacy_checks(draft.to_dict())
    checks = [check for check in checks if check.name != "privacy_scan_deferred_until_report_assembled"]
    checks.extend(privacy_final)
    matrices["privacy"] = privacy_matrix
    return reporting.build_report(checks=checks, scenarios=scenarios, matrices=matrices)


__all__ = ["engine_root", "run_verification"]
