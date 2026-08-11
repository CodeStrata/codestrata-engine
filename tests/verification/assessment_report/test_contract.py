"""SV.5 contract tests."""

from __future__ import annotations

from verification.assessment_report.contract import (
    ASSESSMENT_REPORT_VERIFICATION_ID,
    EXPECTED_SECTION_ORDER,
    default_contract,
)


def test_contract_constants() -> None:
    contract = default_contract()
    assert contract.verification_id == ASSESSMENT_REPORT_VERIFICATION_ID
    assert contract.assessment_schema_version == "1.2"
    assert "report.json" in contract.required_artifacts
    assert EXPECTED_SECTION_ORDER[0][0] == "leadership-verdict"
    assert EXPECTED_SECTION_ORDER[-1][0] == "technical-appendix"
