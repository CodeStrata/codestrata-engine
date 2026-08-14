"""SV.11.13 integration tests.

HISTORICAL_FROZEN_CHARACTERIZATION: Epic 11 slice-completion matrix against
frozen ``reports/verification/sv11-*`` snapshots. Not an ACTIVE 0.2.0 release
gate. Collect with ``CODESTRATA_RUN_HISTORICAL_FROZEN=1``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.ai_provider_platform_completion.contract import (
    COMPLETED_SLICES,
    EXPECTED_LIMITATIONS,
    OUTPUT_RELATIVE,
    PRIVACY_FORBIDDEN_FRAGMENTS,
    REPORT_FILENAME,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    START_EPIC_12,
    TOTAL_SLICES,
    VERIFICATION_ID,
)
from verification.ai_provider_platform_completion.reporting import report_directory
from verification.ai_provider_platform_completion.runner import engine_root, run_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-13")
    result = run_verification(ENGINE_ROOT)
    result.write_json(out / REPORT_FILENAME)
    return result, out


def test_verdict_is_pass_with_limitations(report) -> None:
    result, _ = report
    assert result.verdict == "pass_with_limitations"


def test_no_failed_checks_or_scenarios(report) -> None:
    result, _ = report
    failed = [c.name for c in result.checks if not c.ok]
    failed_scenarios = [s.scenario_id for s in result.negative_scenarios if not s.ok]
    assert failed == [], failed
    assert failed_scenarios == [], failed_scenarios
    assert len(result.negative_scenarios) >= 26


def test_thirteen_of_thirteen_slices(report) -> None:
    result, _ = report
    assert result.completed_slices == COMPLETED_SLICES == 13
    assert result.total_slices == TOTAL_SLICES == 13
    assert sum(1 for row in result.slice_matrix if row["complete"]) == 13


def test_start_epic_12_false(report) -> None:
    result, _ = report
    assert result.start_epic_12 is False
    assert START_EPIC_12 is False
    assert result.release_posture["start_epic_12"] is False


def test_report_identity_and_limitations(report) -> None:
    result, _ = report
    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.verification_id == VERIFICATION_ID == SCHEMA_NAME
    assert result.limitations == EXPECTED_LIMITATIONS
    assert result.epic == 11
    assert result.release == "0.2.0"


def test_privacy_tokens_absent(report) -> None:
    _, out = report
    payload = json.loads((out / REPORT_FILENAME).read_text(encoding="utf-8"))
    scan_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"checks", "negative_scenarios", "defects", "notes", "warnings"}
    }
    blob = json.dumps(scan_payload, sort_keys=True)
    for token in PRIVACY_FORBIDDEN_FRAGMENTS:
        assert token not in blob, token
    # Broad path / credential shapes must not appear in public fields.
    assert "/Users/" not in blob
    assert "Authorization: Bearer" not in blob
    assert "Traceback (most recent call last)" not in blob


def test_report_directory() -> None:
    path = report_directory(engine_root())
    assert path.as_posix().endswith(OUTPUT_RELATIVE)
    assert "sv11-13" in path.as_posix()


def test_determinism() -> None:
    first = run_verification(ENGINE_ROOT)
    second = run_verification(ENGINE_ROOT)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
