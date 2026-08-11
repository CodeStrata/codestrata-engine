"""Contract tests for SV.11."""

from __future__ import annotations

from verification.assessment_consistency.contract import (
    RELEASE_VALIDATION_TARGET,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    default_contract,
)


def test_contract_defaults() -> None:
    c = default_contract()
    assert c.schema_name == SCHEMA_NAME
    assert c.schema_version == SCHEMA_VERSION
    assert c.target_repository_count == RELEASE_VALIDATION_TARGET == 22
    assert c.reassess_by_default is False
    assert c.clone_by_default is False
    assert c.start_sv12 is False
    assert c.assessment_schema_version == "1.2"
