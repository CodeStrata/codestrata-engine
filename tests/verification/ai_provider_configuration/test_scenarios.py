"""Unit tests for verification.ai_provider_configuration.scenarios."""

from __future__ import annotations

from verification.ai_provider_configuration.models import CheckResult
from verification.ai_provider_configuration.scenarios import (
    build_negative_scenarios,
    run_value_object_negative_checks,
)


def test_run_value_object_negative_checks_all_pass() -> None:
    checks = run_value_object_negative_checks()
    assert len(checks) == 14
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
    from verification.ai_provider_configuration.contract import EXPECTED_MODULES

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    verification_dir = tmp_path / "verification"
    verification_dir.mkdir()

    all_check_names = [
        "provider_contracts_has_no_forbidden_sdk_or_product_imports",
        "provider_contracts_has_no_openrouter_adapter_or_api_key_wiring",
        "configuration_modules_never_import_os_pathlib_or_subprocess",
        "provider_contracts_has_no_codestrata_dependencies_outside_itself",
        "product_path_files_do_not_import_provider_contracts",
        "ai_providers_directory_has_no_new_files_from_slice_11_3",
        "provider_id_enum_superset_of_baseline_engine_provider_ids",
        "slice_11_1_baseline_defines_cr1_through_cr6",
        "configuration_compatibility_statements_cover_every_baseline_requirement",
        "every_configuration_compatibility_statement_holds_true",
        "configuration_default_provider_id_matches_baseline_default_assess_provider",
        "configuration_default_model_ids_match_baseline_default_model_ids",
        "configuration_diagnostic_view_excludes_raw_model_reference",
        "serialized_configuration_diagnostic_form_excludes_sensitive_text",
        "provider_contracts_package_has_exactly_expected_modules_after_slice_11_3",
        "all_twelve_slice_11_3_configuration_modules_are_present",
        "configuration_rejects_adapter_provider_mismatch",
        "configuration_rejects_unsupported_configuration_version",
        "configuration_rejects_empty_limitations",
        "configuration_rejects_credential_requirement_provider_mismatch",
        "openai_adapter_rejects_non_blank_url_without_configured_flag",
        "project_configuration_rejects_unsupported_provider",
        "validate_adapter_matches_provider_rejects_mismatch",
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
