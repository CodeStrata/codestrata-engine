"""Unit tests for verification.ai_provider_contracts.scenarios."""

from __future__ import annotations

from verification.ai_provider_contracts.models import CheckResult
from verification.ai_provider_contracts.scenarios import (
    build_negative_scenarios,
    run_value_object_negative_checks,
)


def test_run_value_object_negative_checks_all_pass() -> None:
    checks = run_value_object_negative_checks()
    assert len(checks) == 8
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
    # With no backing checks, letter-scenarios that depend on checks_by_name fail.
    a_scenario = next(s for s in scenarios if s.scenario_id == "A")
    assert a_scenario.ok is False


def test_build_negative_scenarios_pass_with_all_backing_checks_ok(tmp_path) -> None:
    from verification.ai_provider_contracts.contract import EXPECTED_MODULES

    package_dir = tmp_path / "provider_contracts"
    package_dir.mkdir()
    for name in EXPECTED_MODULES:
        (package_dir / name).write_text("", encoding="utf-8")
    verification_dir = tmp_path / "verification"
    verification_dir.mkdir()

    all_check_names = [
        "provider_contracts_has_no_forbidden_sdk_or_product_imports",
        "provider_contracts_has_no_openrouter_adapter_or_api_key_wiring",
        "provider_contracts_has_no_codestrata_dependencies_outside_itself",
        "product_path_files_do_not_import_provider_contracts",
        "ai_providers_directory_has_no_new_files_from_slice_11_2",
        "provider_id_enum_superset_of_baseline_engine_provider_ids",
        "slice_11_1_baseline_defines_cr1_through_cr6",
        "contract_compatibility_statements_cover_every_baseline_requirement",
        "every_contract_compatibility_statement_holds_true",
        "request_diagnostic_view_excludes_prompt_and_raw_model_reference",
        "result_diagnostic_view_excludes_response_text",
        "serialized_diagnostic_forms_exclude_sensitive_text",
        "error_detail_never_contains_credential_shaped_tokens",
        "provider_contracts_package_has_exactly_expected_modules",
        "provider_contracts_package_exists_at_documented_sibling_location",
        "request_rejects_capability_payload_mismatch",
        "request_rejects_unsupported_contract_version",
        "usage_rejects_inconsistent_token_total",
        "error_rejects_traceback_shaped_detail",
        "success_result_rejects_attached_error",
        "failed_result_requires_attached_error",
        "registry_rejects_duplicate_registration",
        "registry_resolve_raises_for_unknown_provider",
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
