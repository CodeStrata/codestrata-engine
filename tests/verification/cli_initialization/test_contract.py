"""SV.3 contract tests."""

from __future__ import annotations

from verification.cli_initialization.contract import (
    CLI_INITIALIZATION_VERIFICATION_ID,
    default_contract,
)


def test_contract_identity() -> None:
    contract = default_contract()
    assert contract.verification_id == CLI_INITIALIZATION_VERIFICATION_ID
    assert contract.verification_version == "1.0.0"
    assert contract.discovers_repository_root is False
    assert contract.interactive is False
    assert contract.network_required is False
    assert contract.telemetry_enabled_by_default is False
    assert contract.ai_silently_enabled is False
    assert contract.help_command == ("--help",)
    assert "A_minimal_supported_repository" in contract.scenario_ids
    assert "codestrata.toml" in contract.required_artifacts
