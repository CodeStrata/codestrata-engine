"""SV.11.6 contract constants: the pass/fail definition itself must be stable."""

from __future__ import annotations

from codestrata.config.settings import OpenAISettings
from verification.openai_provider_migration import contract


def test_schema_identity_is_pinned() -> None:
    assert contract.SCHEMA_NAME == "openai-provider-migration-verification"
    assert contract.SCHEMA_VERSION == "1.0.0"
    assert contract.VERIFICATION_ID == contract.SCHEMA_NAME
    assert contract.VERIFICATION_VERSION == "1.0.0"


def test_slice_identity_is_pinned() -> None:
    assert contract.SLICE_ID == "11.6"
    assert contract.SLICE_TITLE == "OpenAI Provider Migration"
    assert contract.EPIC == "Epic 11: AI Provider Compatibility"


def test_output_location_is_pinned() -> None:
    assert contract.OUTPUT_RELATIVE == "reports/verification/sv11-6"
    assert contract.REPORT_FILENAME == "openai-provider-migration-verification.json"


def test_expected_modules_are_the_twelve_adapter_modules() -> None:
    assert len(contract.EXPECTED_MODULES) == 12
    assert contract.EXPECTED_MODULES == tuple(sorted(contract.EXPECTED_MODULES))
    assert "adapter.py" in contract.EXPECTED_MODULES
    assert "legacy_bridge.py" in contract.EXPECTED_MODULES


def test_the_credential_boundary_is_a_single_module() -> None:
    assert contract.CREDENTIAL_BOUNDARY_MODULE == "client.py"
    assert contract.CREDENTIAL_BOUNDARY_MODULE in contract.EXPECTED_MODULES


def test_config_keys_match_the_settings_model() -> None:
    assert tuple(sorted(OpenAISettings.model_fields)) == tuple(sorted(contract.OPENAI_CONFIG_KEYS))


def test_baseline_anchors_are_pinned() -> None:
    assert contract.DEFAULT_PROVIDER == "bedrock"
    assert contract.OPENAI_DEFAULT_ANSWER_MODEL == "gpt-4o-mini"
    assert contract.OPENAI_API_KEY_ENV_DEFAULT == "OPENAI_API_KEY"
    assert contract.ASSESSMENT_SCHEMA_VERSION == "1.2"
    assert contract.EXPECTED_MAXIMUM_ATTEMPTS == 1
    assert contract.INVOKE_CALLS_PER_ASSESS_RUN == 1
    assert contract.EXPECTED_TIMEOUT_SECONDS == 60.0
    assert contract.EXPECTED_REGISTERED_PROVIDERS == ("bedrock", "openai", "openrouter")


def test_the_prompt_anchors_are_pinned() -> None:
    assert contract.STRUCTURED_JSON_INSTRUCTION == (
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )
    assert contract.DEVELOPER_PREFIX == "Developer instructions:\n"
    assert contract.JSON_RESPONSE_FORMAT == {"type": "json_object"}
    assert contract.EXPECTED_MESSAGE_ROLES == ("system", "user")


def test_the_error_category_partition_is_exhaustive_and_disjoint() -> None:
    retryable = set(contract.RETRYABLE_ERROR_CATEGORIES)
    non_retryable = set(contract.NON_RETRYABLE_ERROR_CATEGORIES)
    assert not retryable & non_retryable
    assert retryable | non_retryable == set(contract.REQUIRED_ERROR_CATEGORIES)


def test_every_sdk_exception_has_both_a_category_and_a_legacy_type() -> None:
    assert set(contract.SDK_EXCEPTION_CATEGORY_MATRIX) == set(contract.LEGACY_EXCEPTION_MATRIX)
    assert set(contract.SDK_EXCEPTION_CATEGORY_MATRIX.values()) <= set(
        contract.REQUIRED_ERROR_CATEGORIES
    )
    assert set(contract.LEGACY_EXCEPTION_MATRIX.values()) == {
        "AIProviderInvocationError",
        "AIProviderTimeoutError",
    }


def test_expected_limitations_record_the_intentional_gaps() -> None:
    for label in (
        "bedrock_remains_legacy",
        "mixed_mode_provider_architecture",
        "no_live_openai_calls",
        "operational_retry_remains_conservative",
        "doctor_uses_compatibility_path",
    ):
        assert label in contract.EXPECTED_LIMITATIONS


def test_the_contract_forbids_the_out_of_scope_changes() -> None:
    default = contract.default_contract()
    assert default.start_slice_11_7 is False
    assert default.migrate_bedrock is False
    assert default.add_openrouter is False
    assert default.change_default_provider is False
    assert default.change_openai_config_keys is False
    assert default.change_prompt_content is False
    assert default.change_cli_exit_behavior is False
    assert default.activate_max_retries is False
    assert default.use_real_network_or_credentials is False
    assert default.commit_changes is False
    assert (
        default.modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure
        is False
    )


def test_allowed_verdicts_exclude_failure() -> None:
    assert contract.ALLOWED_VERDICTS == ("pass", "pass_with_limitations")
    assert "fail" not in contract.ALLOWED_VERDICTS


def test_bedrock_token_lists_are_disjoint() -> None:
    assert not set(contract.BEDROCK_FORBIDDEN_TOKENS) & set(contract.BEDROCK_REQUIRED_TOKENS)


def test_migrated_and_legacy_path_lists_are_disjoint() -> None:
    assert not set(contract.MIGRATED_PATH_FILES) & set(contract.LEGACY_PATH_FILES)


def test_doctor_is_excluded_from_the_sdk_free_list() -> None:
    """Doctor has always probed the optional extra by importing it."""

    assert "ai/providers/doctor.py" not in contract.SDK_FREE_PATH_FILES
    assert "ai/providers/doctor.py" in contract.LEGACY_PATH_FILES
