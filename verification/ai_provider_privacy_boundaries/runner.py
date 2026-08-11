"""Run SV.11.12 AI Provider Privacy Boundary Verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from verification.ai_provider_privacy_boundaries import checks, reporting, scenarios
from verification.ai_provider_privacy_boundaries.contract import NEGATIVE_SCENARIO_COUNT_MIN
from verification.ai_provider_privacy_boundaries.fixtures import synthetic_bedrock_probe
from verification.ai_provider_privacy_boundaries.models import CheckResult


def engine_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_verification(root: Path | None = None):
    engine = root or engine_root()
    with patch(
        "codestrata.ai.providers.doctor.probe_aws_session_for_bedrock",
        synthetic_bedrock_probe,
    ):
        return _run_verification(engine)


def _run_verification(engine: Path):
    all_checks: list[CheckResult] = []
    provider_matrix: dict[str, Any] = {}

    sections = (
        checks.run_inventory_checks(engine),
        checks.run_provider_matrix_checks(),
        checks.run_registry_checks(),
        checks.run_credential_checks(),
        checks.run_request_privacy_checks(),
        checks.run_response_privacy_checks(),
        checks.run_model_privacy_checks(),
        checks.run_error_privacy_checks(),
        checks.run_diagnostics_checks(),
        checks.run_logging_checks(engine),
        checks.run_configuration_checks(),
        checks.run_configuration_path_write_checks(engine),
        checks.run_execution_checks(engine),
        checks.run_retry_checks(),
        checks.run_failure_isolation_checks(),
        checks.run_assessment_authority_checks(),
        checks.run_reporting_boundary_checks(engine),
        checks.run_doctor_boundary_checks(engine),
        checks.run_cli_boundary_checks(engine),
        checks.run_telemetry_boundary_checks(engine),
        checks.run_analytics_boundary_checks(),
        checks.run_platform_boundary_checks(engine),
        checks.run_data_lake_boundary_checks(engine),
        checks.run_vscode_boundary_checks(engine),
        checks.run_cursor_boundary_checks(engine),
        checks.run_dependency_boundary_checks(engine),
        checks.run_packaging_checks(engine),
        checks.run_public_export_checks(engine),
        checks.run_safety_checks(),
        checks.run_determinism_checks(),
    )
    for section_checks, matrix in sections:
        all_checks.extend(section_checks)
        if matrix:
            provider_matrix.update(matrix)

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

    draft = reporting.build_report(
        checks=all_checks, scenarios=negative, provider_matrix=provider_matrix
    )
    privacy_final, _ = checks.run_privacy_checks(draft.to_dict())
    all_checks = [
        check
        for check in all_checks
        if check.name != "privacy_scan_deferred_until_report_assembled"
    ]
    all_checks.extend(privacy_final)
    return reporting.build_report(
        checks=all_checks, scenarios=negative, provider_matrix=provider_matrix
    )


__all__ = ["engine_root", "run_verification"]
