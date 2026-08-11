"""SV.11.8 integration: verdict, limitations, privacy, determinism, registry decision."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from verification.ai_provider_cross_provider.contract import (
    EXPECTED_LIMITATIONS,
    REGISTRY_DECISION,
    REGISTRY_DECISION_LABEL,
    REPORT_FILENAME,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SLICE_ID,
)
from verification.ai_provider_cross_provider.reporting import report_directory
from verification.ai_provider_cross_provider.runner import engine_root, run_verification

ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("sv11-8")
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


def test_report_identity_limitations_and_registry_decision(report) -> None:
    result, _ = report
    assert result.schema_name == SCHEMA_NAME
    assert result.schema_version == SCHEMA_VERSION
    assert result.slice_id == SLICE_ID
    assert result.limitations == EXPECTED_LIMITATIONS
    assert result.compatibility_requirement_ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    assert result.registry_decision == REGISTRY_DECISION
    assert result.registry_decision_label == REGISTRY_DECISION_LABEL
    assert result.providers == ("bedrock", "openai", "openrouter")


def test_check_counts_agree(report) -> None:
    result, _ = report
    assert result.check_counts["failed"] == 0
    assert result.check_counts["passed"] == result.check_counts["total"]
    assert result.check_counts["total"] == len(result.checks)
    payload = result.to_dict()
    assert payload["total_checks"] == result.check_counts["total"]
    assert payload["failed_checks"] == 0
    assert payload["defects"] == []
    assert payload["blockers"] == []


def test_report_omits_forbidden_privacy_tokens(report) -> None:
    result, out = report
    blob = (out / REPORT_FILENAME).read_text(encoding="utf-8")
    for token in (
        "sk-",
        "AKIA",
        "aws_secret",
        "session_token",
        "Traceback",
        "/Users/",
        "Authorization: Bearer",
        "OPENAI_API_KEY=",
    ):
        assert token not in blob


def test_default_report_directory_is_sv11_8() -> None:
    path = report_directory(engine_root())
    assert path.as_posix().endswith("reports/verification/sv11-8")


def test_two_runs_are_byte_identical() -> None:
    first = run_verification(ENGINE_ROOT)
    second = run_verification(ENGINE_ROOT)
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
