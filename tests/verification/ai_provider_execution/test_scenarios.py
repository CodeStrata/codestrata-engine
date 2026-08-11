"""Unit tests for verification.ai_provider_execution.scenarios."""

from __future__ import annotations

from verification.ai_provider_execution.models import CheckResult
from verification.ai_provider_execution.scenarios import (
    build_negative_scenarios,
    run_value_object_negative_checks,
)


def test_run_value_object_negative_checks_all_pass() -> None:
    checks = run_value_object_negative_checks()
    assert len(checks) == 12
    assert all(check.ok for check in checks), [c for c in checks if not c.ok]


def test_build_negative_scenarios_reports_missing_check_as_failed(tmp_path) -> None:
    scenarios = build_negative_scenarios(
        package_dir=tmp_path,
        verification_dir=tmp_path,
        checks_by_name={},
        report_payload_preview={},
    )
    ids = {s.scenario_id for s in scenarios}
    assert ids == {chr(ord("A") + i) for i in range(26)}
    a_scenario = next(s for s in scenarios if s.scenario_id == "A")
    assert a_scenario.ok is False


def test_build_negative_scenarios_pass_with_all_backing_checks_ok(tmp_path) -> None:
    from verification.ai_provider_execution.contract import EXPECTED_MODULES

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    verification_dir = tmp_path / "verification"
    verification_dir.mkdir()

    all_check_names = [
        "provider_contracts_has_no_forbidden_sdk_or_product_imports",
        "provider_contracts_has_no_openrouter_adapter_or_api_key_wiring",
        "execution_modules_never_import_os_pathlib_subprocess_threading_asyncio_or_signal",
        "provider_contracts_has_no_codestrata_dependencies_outside_itself",
        "product_path_files_do_not_import_provider_contracts",
        "ai_providers_directory_has_no_new_files_from_slice_11_4",
        "slice_11_1_baseline_defines_cr1_through_cr6",
        "execution_compatibility_statements_cover_every_baseline_requirement",
        "every_execution_compatibility_statement_holds_true",
        "default_retry_policy_maximum_attempts_is_one_matching_cr1",
        "settings_representable_retry_policy_matches_real_bedrock_and_openai_max_retries",
        "execution_policy_default_timeout_seconds_matches_real_providers_default",
        "retryable_and_non_retryable_partition_covers_every_error_category_exactly_once",
        "authentication_and_authorization_failures_are_never_retryable_by_default",
        "provider_contracts_package_has_exactly_expected_modules_after_slice_11_4",
        "all_eleven_slice_11_4_execution_modules_are_present",
        "executor_never_raises_for_a_failed_provider_result",
        "executor_does_not_retry_a_non_retryable_error_category",
        "executor_stops_retrying_once_maximum_attempts_is_reached",
        "executor_converts_an_unexpected_exception_into_an_internal_failure_result",
        "executor_does_not_swallow_keyboard_interrupt",
        "executor_raises_provider_contract_validation_error_on_provider_id_mismatch",
        "diagnostic_serialization_excludes_provider_result_content",
    ]
    checks_by_name = {
        name: CheckResult(name=name, category="test", ok=True) for name in all_check_names
    }
    scenarios = build_negative_scenarios(
        package_dir=package_dir,
        verification_dir=verification_dir,
        checks_by_name=checks_by_name,
        report_payload_preview={"safe": "value"},
    )
    assert all(s.ok for s in scenarios), [(s.scenario_id, s.detail) for s in scenarios if not s.ok]
