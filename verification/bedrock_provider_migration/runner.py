"""Run every SV.11.7 check and negative scenario, then assemble the report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verification.bedrock_provider_migration import (
    authentication,
    baseline_compatibility,
    configuration,
    dependency_boundary,
    doctor,
    errors,
    execution,
    fail_soft,
    inventory,
    openai_regression,
    privacy,
    provider_registry,
    reporting,
    reporting_boundary,
    requests,
    responses,
    scenarios,
    usage,
)
from verification.bedrock_provider_migration.contract import (
    EXPECTED_LIMITATIONS,
    NEGATIVE_SCENARIO_COUNT_MIN,
    PACKAGE_RELATIVE_PATH,
    PRIOR_SLICE_IDS,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SLICE_ID,
    SLICE_TITLE,
    default_contract,
)
from verification.bedrock_provider_migration.models import (
    BedrockMigrationVerificationReport,
    CheckResult,
)


def engine_root() -> Path:
    """Return the ``engine/`` directory this package lives under."""

    return Path(__file__).resolve().parents[2]


def package_directory(root: Path | None = None) -> Path:
    return (root or engine_root()) / "src" / "codestrata" / PACKAGE_RELATIVE_PATH


def _contract_checks(scenario_count: int) -> list[CheckResult]:
    contract = default_contract()
    forbidden = {
        "activate_max_retries": contract.activate_max_retries,
        "add_openrouter": contract.add_openrouter,
        "change_aws_credential_precedence": contract.change_aws_credential_precedence,
        "change_bedrock_config_keys": contract.change_bedrock_config_keys,
        "change_cli_exit_behavior": contract.change_cli_exit_behavior,
        "change_converse_semantics": contract.change_converse_semantics,
        "change_default_provider": contract.change_default_provider,
        "change_migrated_openai_behavior": contract.change_migrated_openai_behavior,
        "change_prompt_content": contract.change_prompt_content,
        "commit_changes": contract.commit_changes,
        "modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure": (
            contract.modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure
        ),
        "stack_codestrata_retries_on_sdk_retries": (
            contract.stack_codestrata_retries_on_sdk_retries
        ),
        "start_slice_11_8": contract.start_slice_11_8,
        "use_real_network_or_credentials": contract.use_real_network_or_credentials,
    }
    asserted = sorted(name for name, value in forbidden.items() if value)
    return [
        CheckResult(
            name="every_out_of_scope_change_is_asserted_false_in_the_contract",
            category="contract",
            ok=not asserted,
            detail=f"asserted_out_of_scope_changes={asserted}",
            evidence={"out_of_scope_flag_count": len(forbidden)},
        ),
        CheckResult(
            name="the_expected_limitation_set_is_declared_in_full",
            category="contract",
            ok=tuple(contract.expected_limitations) == EXPECTED_LIMITATIONS,
            detail=f"limitations={list(EXPECTED_LIMITATIONS)}",
        ),
        CheckResult(
            name="every_compatibility_requirement_is_covered",
            category="contract",
            ok=tuple(contract.required_compatibility_requirement_ids)
            == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
            detail=f"requirement_ids={list(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS)}",
        ),
        CheckResult(
            name="the_full_negative_scenario_matrix_ran",
            category="contract",
            ok=scenario_count >= NEGATIVE_SCENARIO_COUNT_MIN,
            detail=f"scenario_count={scenario_count}",
            evidence={"minimum_scenario_count": NEGATIVE_SCENARIO_COUNT_MIN},
        ),
    ]


def run_verification(root: Path | None = None) -> BedrockMigrationVerificationReport:
    """Run every check, then assemble the deterministic report."""

    engine = root or engine_root()
    package_dir = package_directory(engine)

    checks: list[CheckResult] = []
    matrices: dict[str, Any] = {}

    for section, (section_checks, matrix) in (
        ("inventory", inventory.run_inventory_checks(engine, package_dir)),
        (
            "dependency_boundary",
            dependency_boundary.run_dependency_boundary_checks(engine, package_dir),
        ),
        ("baseline_compatibility", baseline_compatibility.run_baseline_compatibility_checks()),
        ("configuration", configuration.run_configuration_checks()),
        ("authentication", authentication.run_authentication_checks(package_dir)),
        ("requests", requests.run_request_checks()),
        ("responses", responses.run_response_checks()),
        ("usage", usage.run_usage_checks()),
        ("errors", errors.run_error_checks()),
        ("execution", execution.run_execution_checks()),
        ("fail_soft", fail_soft.run_fail_soft_checks()),
        ("provider_registry", provider_registry.run_provider_registry_checks()),
        ("doctor", doctor.run_doctor_checks()),
        (
            "reporting_boundary",
            reporting_boundary.run_reporting_boundary_checks(package_dir),
        ),
        ("privacy", privacy.run_adapter_privacy_checks()),
        ("openai_regression", openai_regression.run_openai_regression_checks(engine)),
    ):
        checks.extend(section_checks)
        matrices[section] = matrix

    scenario_results = scenarios.run_negative_scenarios(engine, package_dir)
    checks.extend(_contract_checks(len(scenario_results)))

    matrices["slice"] = {
        "epic_slice": SLICE_ID,
        "prior_slices_verified": list(PRIOR_SLICE_IDS),
        "title": SLICE_TITLE,
    }

    draft = reporting.build_report(
        checks=checks, scenarios=scenario_results, matrices=matrices
    )
    checks.extend(privacy.run_report_privacy_checks(draft.to_dict()))
    return reporting.build_report(
        checks=checks, scenarios=scenario_results, matrices=matrices
    )


__all__ = [
    "engine_root",
    "package_directory",
    "run_verification",
]
