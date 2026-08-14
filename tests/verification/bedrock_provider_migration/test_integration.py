"""SV.11.7 integration: verdict, limitations, privacy, determinism.

HISTORICAL_FROZEN_CHARACTERIZATION: Epic 11.7 Bedrock migration slice against
pre-OpenRouter package boundaries and legacy wrapper exception types. Not an
ACTIVE 0.2.0 release gate. Collect with ``CODESTRATA_RUN_HISTORICAL_FROZEN=1``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.bedrock_provider_migration.contract import (
    EXPECTED_LIMITATIONS,
    REPORT_FILENAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
)
from verification.bedrock_provider_migration.reporting import report_directory
from verification.bedrock_provider_migration.runner import engine_root, run_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-7")
    result = run_verification(ENGINE_ROOT)
    result.write_json(out / REPORT_FILENAME)
    return result, out


def test_verdict_is_pass_with_limitations(report) -> None:
    result, _ = report
    assert result.verdict == "pass_with_limitations"


def test_no_failed_checks_or_scenarios(report) -> None:
    result, _ = report
    assert all(check.ok for check in result.checks)
    assert all(scenario.ok for scenario in result.negative_scenarios)


def test_report_identity_and_limitations(report) -> None:
    result, _ = report
    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.slice_id == SLICE_ID
    assert result.limitations == EXPECTED_LIMITATIONS
    assert result.compatibility_requirement_ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


def test_check_counts_agree(report) -> None:
    result, _ = report
    assert result.check_counts["failed"] == 0
    assert result.check_counts["passed"] == result.check_counts["total"]
    assert result.check_counts["total"] == len(result.checks)


def test_report_omits_forbidden_privacy_tokens(report) -> None:
    result, out = report
    blob = (out / REPORT_FILENAME).read_text(encoding="utf-8")
    for token in (
        "AKIA",
        "aws_secret",
        "session_token",
        "Traceback",
        "/Users/",
        "Authorization: Bearer",
        "Synthetic instruction text",
    ):
        assert token not in blob


def test_default_report_directory_is_sv11_7() -> None:
    path = report_directory(engine_root())
    assert path.as_posix().endswith("reports/verification/sv11-7")


def test_two_runs_are_byte_identical(tmp_path: Path) -> None:
    first = run_verification(ENGINE_ROOT)
    second = run_verification(ENGINE_ROOT)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
