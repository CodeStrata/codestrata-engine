"""SV.11.10 integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.openrouter_configuration.contract import (
    EXPECTED_LIMITATIONS,
    REPORT_FILENAME,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
)
from verification.openrouter_configuration.reporting import report_directory
from verification.openrouter_configuration.runner import engine_root, run_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-10")
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
    assert len(result.negative_scenarios) >= 26


def test_report_identity_and_limitations(report) -> None:
    result, _ = report
    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.slice_id == SLICE_ID
    assert result.limitations == EXPECTED_LIMITATIONS
    assert result.verification_id == SCHEMA_NAME


def test_privacy_tokens_absent(report) -> None:
    _, out = report
    blob = (out / REPORT_FILENAME).read_text(encoding="utf-8")
    for token in (
        "sk-",
        "https://openrouter.ai",
        "Authorization: Bearer",
        "Synthetic instruction text",
        "test-only/openrouter-model",
        "/Users/",
        "Traceback",
    ):
        assert token not in blob


def test_report_directory() -> None:
    assert report_directory(engine_root()).as_posix().endswith("reports/verification/sv11-10")


def test_determinism() -> None:
    first = run_verification(ENGINE_ROOT)
    second = run_verification(ENGINE_ROOT)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
