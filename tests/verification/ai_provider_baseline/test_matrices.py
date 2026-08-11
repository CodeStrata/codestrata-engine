"""SV.11.1 matrix / check unit tests.

Exercises the deterministic matrix builders and a sample of individual
characterization checks directly (not through the full runner), so failures
point at the exact module responsible.
"""

from __future__ import annotations

from pathlib import Path

from verification.ai_provider_baseline import (
    capabilities,
    configuration,
    errors,
    provider_selection,
    responses,
    retries,
    timeouts,
)
from verification.ai_provider_baseline import (
    requests as requests_module,
)

ENGINE_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ENGINE_ROOT / "src" / "codestrata"


def test_settings_defaults_matrix_shape() -> None:
    matrix = configuration.build_settings_defaults_matrix()
    assert matrix["bedrock"]["timeout_seconds"] == 60
    assert matrix["openai"]["timeout_seconds"] == 60
    assert matrix["bedrock"]["max_retries"] == 3
    assert matrix["openai"]["max_retries"] == 3
    assert matrix["ai"]["provider"] == "bedrock"


def test_model_id_resolution_matrix_covers_both_providers_and_precedence() -> None:
    matrix = provider_selection.build_model_id_resolution_matrix()
    providers = {row["provider"] for row in matrix}
    sources = {row["expected_source"] for row in matrix}
    assert providers == {"bedrock", "openai"}
    assert sources == {"hardcoded_default", "cli_argument", "codestrata_toml_setting"}
    for row in matrix:
        if row["expected_source"] == "cli_argument":
            assert row["resolved_model_id"] == "explicit-cli-model-id"


def test_timeout_matrix_records_the_wiring_gap() -> None:
    matrix = timeouts.build_timeout_matrix()
    assert matrix["assess_factory_reads_settings_timeout_seconds"] is False
    assert matrix["default_timeout_seconds_constant"] == 60.0


def test_retry_matrix_records_retry_call_is_unused() -> None:
    matrix = retries.build_retry_matrix()
    assert matrix["retry_call_referenced_by_bedrock_provider"] is False
    assert matrix["retry_call_referenced_by_openai_provider"] is False
    assert matrix["assess_max_retries_wired_to_provider_invocation"] is False
    assert matrix["invoke_calls_per_assess_run"] == 1


def test_request_matrix_covers_both_providers() -> None:
    matrix = requests_module.build_request_matrix()
    assert "bedrock" in matrix
    assert "openai" in matrix


def test_bedrock_request_shape_has_converse_fields() -> None:
    shape = requests_module.build_bedrock_request_shape()
    assert shape["top_level_keys"] == sorted(["modelId", "messages", "inferenceConfig", "system"])
    assert shape["has_inference_config"] is True


def test_openai_request_shape_has_chat_completion_fields() -> None:
    shape = requests_module.build_openai_request_shape()
    assert shape["system_message_present"] is True
    assert shape["message_roles"][-1] == "user"


def test_response_matrix_covers_both_providers() -> None:
    matrix = responses.build_response_matrix()
    assert "bedrock" in matrix
    assert "openai" in matrix


def test_capabilities_matrix_records_advisor_override() -> None:
    matrix = capabilities.build_capabilities_matrix()
    assert matrix["invocation_defaults"]["max_output_tokens"] == 8192
    assert matrix["invocation_defaults"]["temperature"] == 0.0
    assert matrix["modernization_advisor_assess_max_output_tokens"] == 5000


def test_error_mapping_matrices_are_non_empty_and_map_to_ai_provider_error() -> None:
    bedrock_matrix = errors.build_bedrock_error_mapping_matrix()
    openai_matrix = errors.build_openai_error_mapping_matrix()
    assert bedrock_matrix
    assert openai_matrix
    for row in bedrock_matrix + openai_matrix:
        assert "mapped_type" in row
        assert "scenario" in row


def test_matrices_are_json_serializable_and_deterministic_across_calls() -> None:
    from verification.ai_provider_baseline.determinism import canonical_json

    first = canonical_json(configuration.build_settings_defaults_matrix())
    second = canonical_json(configuration.build_settings_defaults_matrix())
    assert first == second

    first_ids = canonical_json(provider_selection.build_model_id_resolution_matrix())
    second_ids = canonical_json(provider_selection.build_model_id_resolution_matrix())
    assert first_ids == second_ids
