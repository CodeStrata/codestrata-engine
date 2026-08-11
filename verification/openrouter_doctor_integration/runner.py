"""Run SV.11.11 OpenRouter doctor integration verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from verification.openrouter_doctor_integration import checks, reporting, scenarios
from verification.openrouter_doctor_integration.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.openrouter_doctor_integration.fixtures import synthetic_bedrock_probe
from verification.openrouter_doctor_integration.models import CheckResult


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_verification(root: Path | None = None):
    engine = root or engine_root()
    # Doctor's Bedrock branch probes a real AWS session; stub it so verification
    # stays network-free while still exercising OpenRouter/OpenAI doctor paths.
    with patch(
        "codestrata.ai.providers.doctor.probe_aws_session_for_bedrock",
        synthetic_bedrock_probe,
    ):
        return _run_verification(engine)


def _run_verification(engine: Path):
    all_checks: list[CheckResult] = []

    for section_checks, _matrix in (
        checks.run_inventory_checks(engine),
        checks.run_doctor_policy_checks(engine),
        checks.run_readiness_checks(),
        checks.run_formatting_checks(),
        checks.run_doctor_exit_checks(),
        checks.run_integration_success_checks(),
        checks.run_integration_failure_checks(),
        checks.run_provider_selection_checks(),
        checks.run_fail_soft_checks(),
        checks.run_reporting_boundary_checks(engine),
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
            category="inventory",
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
