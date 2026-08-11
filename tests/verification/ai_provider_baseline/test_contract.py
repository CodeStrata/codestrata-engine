"""SV.11.1 contract tests."""

from __future__ import annotations

from verification.ai_provider_baseline.contract import (
    DEFAULT_ASSESS_PROVIDER,
    ENGINE_PROVIDER_IDS,
    EXPECTED_LIMITATIONS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    VERIFICATION_ID,
    default_contract,
)


def test_contract_identity() -> None:
    contract = default_contract()
    assert contract.verification_id == VERIFICATION_ID
    assert contract.verification_version == "1.0.0"
    assert contract.schema_name == SCHEMA_NAME
    assert contract.schema_version == SCHEMA_VERSION
    assert contract.providers == ENGINE_PROVIDER_IDS
    assert contract.default_provider == DEFAULT_ASSESS_PROVIDER


def test_contract_hard_constraints_are_all_false() -> None:
    contract = default_contract()
    assert contract.start_slice_11_2 is False
    assert contract.migrate_openai_or_bedrock is False
    assert contract.add_openrouter is False
    assert contract.create_provider_platform is False
    assert contract.modify_ai_execution is False
    assert contract.modify_community_cloud_or_platform is False
    assert contract.commit_changes is False


def test_contract_allowed_verdicts_and_limitations() -> None:
    contract = default_contract()
    assert contract.allowed_verdicts == ("pass", "pass_with_limitations")
    assert set(EXPECTED_LIMITATIONS) == set(contract.expected_limitations)
    assert "no_live_provider_calls" in contract.expected_limitations
    assert "no_real_credentials" in contract.expected_limitations
    assert (
        "settings_timeout_max_retries_not_wired_to_assess_factory" in contract.expected_limitations
    )


def test_engine_provider_ids_match_ground_truth() -> None:
    assert ENGINE_PROVIDER_IDS == ("bedrock", "openai", "openrouter")
    assert DEFAULT_ASSESS_PROVIDER == "bedrock"
