"""SV.4 contract tests."""

from __future__ import annotations

from verification.repository_assessment.contract import (
    CANONICAL_ASSESS_COMMAND,
    CATALOG_RELATIVE_PATH,
    REPOSITORY_ASSESSMENT_VERIFICATION_ID,
    REPOSITORY_ASSESSMENT_VERIFICATION_VERSION,
    default_contract,
    duration_bucket,
)


def test_contract_ids() -> None:
    contract = default_contract()
    assert contract.verification_id == REPOSITORY_ASSESSMENT_VERIFICATION_ID
    assert contract.verification_version == REPOSITORY_ASSESSMENT_VERIFICATION_VERSION
    assert contract.assessment_schema_version == "1.2"
    assert contract.ai_enabled is False
    assert contract.telemetry_enabled is False


def test_canonical_command_is_assess_not_scan() -> None:
    assert CANONICAL_ASSESS_COMMAND == ("assess",)
    assert default_contract().legacy_command == ("scan",)
    assert "--no-ai" in default_contract().canonical_args


def test_catalog_path_constant() -> None:
    assert CATALOG_RELATIVE_PATH == "validation/repository-catalog/catalog.json"


def test_duration_buckets() -> None:
    assert duration_bucket(1) == "under_10s"
    assert duration_bucket(15) == "10s_to_30s"
    assert duration_bucket(60) == "30s_to_2m"
    assert duration_bucket(300) == "2m_to_10m"
    assert duration_bucket(900) == "over_10m"
