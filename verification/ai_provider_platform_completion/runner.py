"""Run SV.11.13 AI Provider Platform Completion Verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.ai_provider_platform_completion import checks, reporting, scenarios
from verification.ai_provider_platform_completion.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.ai_provider_platform_completion.models import CheckResult
from verification.ai_provider_platform_completion.slice_matrix import sorted_slice_matrix


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def monorepo_root(engine: Path | None = None) -> Path:
    return (engine or engine_root()).parent


def run_verification(root: Path | None = None):
    engine = root or engine_root()
    return _run_verification(engine)


def _run_verification(engine: Path):
    all_checks: list[CheckResult] = []
    extras: dict[str, Any] = {}

    sections = (
        checks.run_inventory_checks(engine),
        checks.run_slice_matrix_checks(engine, treat_self_complete=True),
        checks.run_provider_registry_checks(),
        checks.run_registry_decision_checks(),
        checks.run_policy_registry_checks(),
        checks.run_schema_registry_checks(),
        checks.run_configuration_checks(engine),
        checks.run_execution_checks(engine),
        checks.run_capability_checks(),
        checks.run_usage_checks(),
        checks.run_migration_checks(engine),
        checks.run_openrouter_checks(engine),
        checks.run_doctor_checks(engine),
        checks.run_cli_checks(engine),
        checks.run_failure_isolation_checks(engine),
        checks.run_reporting_boundary_checks(),
        checks.run_dependency_boundary_checks(engine),
        checks.run_packaging_checks(engine),
        checks.run_public_export_checks(engine),
        checks.run_documentation_checks(monorepo_root(engine)),
        checks.run_epic12_absence_checks(engine),
        checks.run_release_posture_checks(),
        checks.run_safety_checks(),
    )
    for section_checks, matrix in sections:
        all_checks.extend(section_checks)
        if matrix:
            extras.update(matrix)

    slice_matrix = sorted_slice_matrix(extras.get("slice_matrix") or [])
    det_checks, _ = checks.run_determinism_checks(slice_matrix)
    all_checks.extend(det_checks)

    privacy_placeholder, _ = checks.run_privacy_checks(None)
    all_checks.extend(privacy_placeholder)

    negative = scenarios.run_negative_scenarios(
        engine, report_payload=None, slice_matrix=slice_matrix
    )
    all_checks.append(
        CheckResult(
            name="negative_scenario_count_meets_minimum",
            category="inventory",
            ok=len(negative) >= NEGATIVE_SCENARIO_COUNT_MIN,
            detail=f"scenario_count={len(negative)}",
        )
    )

    draft = reporting.build_report(
        checks=all_checks,
        scenarios=negative,
        slice_matrix=slice_matrix,
        provider_selection=extras.get("provider_selection") or {},
        policy_registry=extras.get("policy_registry") or {},
        schema_registry=extras.get("schema_registry") or {},
        release_posture=extras.get("release_posture"),
    )

    privacy_final, _ = checks.run_privacy_checks(draft.to_dict())
    all_checks = [
        check
        for check in all_checks
        if check.name != "privacy_scan_deferred_until_report_assembled"
    ]
    all_checks.extend(privacy_final)

    # Re-run negative scenarios N/O/Q/Z against assembled report
    negative = scenarios.run_negative_scenarios(
        engine, report_payload=draft.to_dict(), slice_matrix=slice_matrix
    )

    return reporting.build_report(
        checks=all_checks,
        scenarios=negative,
        slice_matrix=slice_matrix,
        provider_selection=extras.get("provider_selection") or {},
        policy_registry=extras.get("policy_registry") or {},
        schema_registry=extras.get("schema_registry") or {},
        release_posture=extras.get("release_posture"),
    )


__all__ = ["engine_root", "monorepo_root", "run_verification"]
